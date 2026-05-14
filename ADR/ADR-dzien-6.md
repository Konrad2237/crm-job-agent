# ADR Dzień 6 — Discovery quality: debugging, przebudowa filtrów, query strategy

Data: 2026-05-14
Branch: `fix/discovery-quality` (utworzony, potem merge do main)
Status: ukończony, na produkcji

---

## Część I — Dokumentacja techniczna (dla Claude Code)

### Co się stało

Sesja diagnostyczna i naprawcza. Punkt startowy: system miał `max_tokens=50` w page_verifier (ustawione w poprzedniej sesji jako "optymalizacja kosztów") — powodowało to truncację outputu Haiku i ValidationError przy każdym wywołaniu. System de facto nie działał.

W trakcie naprawy tego jednego problemu nawarstwiło się wiele zmian, które łącznie pogorszyły jakość wyników zanim zostały właściwie ustrojone. Sesja zakończyła się stanem: system działa, quality jest akceptowalna, kilka false positives (obcy company / blog) się zdarza.

### Schemat zmienionych plików

```
backend/
│
├── core/
│   ├── page_verifier.py
│   │   ├── max_tokens: 50 → 200  ← GŁÓWNY BUG SESJI
│   │   ├── Prompt is_ai_company: usunięto wymóg słowa "AI"
│   │   │   → akceptuje ML, NLP, computer vision, machine vision, automatyzację algorytmiczną
│   │   ├── Prompt is_polish: usunięto hardkodowane nazwy firm (SAP, GFT etc.) → reguły cech
│   │   └── verify_page(content, domain="", title="") ← domain + tytuł jako dodatkowy kontekst
│   │
│   ├── discovery_loop.py
│   │   ├── MAX_RESULTS: 3 → 5
│   │   ├── asyncio.timeout: 25 → 55  ← Extract homepage wolniejszy niż snippet
│   │   ├── _BLOCKED_DOMAINS: +portale newsowe (rp.pl, pb.pl, infor.pl, itwiz.pl, etc.)
│   │   ├── _is_blocked(): +subdomain detection (cyfrowa.rp.pl blokowane gdy rp.pl na liście)
│   │   ├── _is_edu_or_news_domain() → _is_edu_domain() ← uproszczenie, fix literówki
│   │   ├── _TITLE_NUMBER_START_RE: nowy filtr — tytuły zaczynające się od liczby = artykuły
│   │   ├── _ARTICLE_TITLE_PATTERNS: +companies in, +top ai, +sposobów, +zaskakując
│   │   ├── _is_likely_article(): +check .pdf extension
│   │   ├── Krok 4 content: .pl → Extract homepage; non-.pl → snippet z Tavily
│   │   │   (Extract na .pl bo pełna treść potrzebna do klasyfikacji;
│   │   │    snippet na non-.pl bo Extract angielskiego homepage → fałszywe pl=False)
│   │   ├── Tavily: +search_depth="advanced"
│   │   ├── verify_page: +domain, +title jako argumenty
│   │   ├── _name_from_title(): kolejność sep: " | " najpierw (standard PL: "Opis | Firma")
│   │   │   +_is_junk(): odrzuca listy miast "Gdańsk, Poznań, Warszawa" jako nazwę firmy
│   │   └── _query_history / QUERY_HISTORY_MAX: USUNIĘTE
│   │       (dedup domen przez get_seen_domains() wystarczy; historia blokowała dobre tematy)
│   │
│   └── query_generator.py
│       ├── Każde zapytanie MUSI zawierać słowo firmowe: oferta/SaaS/demo/B2B/platforma/wdrożenia
│       │   → shift Tavily od artykułów w kierunku stron komercyjnych
│       ├── Przykłady: mniej chatbot-heavy, więcej ML/CV/healthcare/produkcja
│       ├── generate_query(): usunięto parametr previous_queries
│       └── HumanMessage: uproszczony do "Generuj zapytanie:" bez historii
│
└── db/client.py
    └── save_company(): usunięto parametr what_they_do (zawsze był "")
        discovery_loop.py: save_company(name, url, domain) — bez what_they_do
```

### Decyzje architektoniczne podjęte w Dniu 6

| Decyzja | Wybór | Alternatywa odrzucona | Powód |
|---|---|---|---|
| max_tokens page_verifier | 200 | 50/100 | Structured output przez tool_use ma ~80-100 tokenów overhead; 50/100 ucinało output przed `is_ai_company` |
| Extract vs snippet dla klasyfikacji | .pl → Extract; non-.pl → snippet | Snippet dla wszystkich / Extract dla wszystkich | Snippet: false positives (Randstad, guidewire). Extract non-.pl: angielski homepage → pl=False dla polskich firm z .com |
| Historia zapytań | USUNIĘTA | Rolling window 5/10 | Historia blokowała tematy które były dobre (np. HR AI) — użytkownik stracił możliwość wyszukiwania firm w tych branżach po aplikacji do jednej z nich |
| Słowa firmowe w zapytaniach | Obowiązkowe (oferta/SaaS/demo/B2B) | Topical queries bez słów firmowych | Topical queries ("AI w medycynie Polska") → artykuły; firmowe słowa → strony z ofertą |
| Subdomain blocking | domain.endswith(f".{blocked}") | Exact match | "cyfrowa.rp.pl" != "rp.pl" — subdomeny przechodziły |
| Nazwy firm w promptach | NIE — reguły opisują cechy | Hardkodowane przykłady (SAP, GFT) | Kruche: Accenture, Capgemini nie byłyby blokowane; reguła cech jest generalizowalna |
| search_depth Tavily | "advanced" | "basic" (domyślne) | Advanced indeksuje głębiej — trafia w mniej-popularne strony małych polskich firm |
| Miasta w zapytaniach | Odrzucone | Rotacja zapytań z miastami | Miast jest tysiące, nie 20; wiele firm nie ma miasta na stronie; użytkownik odrzucił pomysł |

### Błędy napotkane w Dniu 6

**B1 — max_tokens=50 → ValidationError `is_ai_company Field required`**
- Przyczyna: poprzednia sesja ustawiła max_tokens=50 jako "optymalizację". Structured output przez Anthropic tool_use ma overhead ~80 tokenów na nagłówek narzędzia — Haiku ucinał output po `is_polish`, nigdy nie docierając do `is_ai_company`.
- Objaw: wszystkie wywołania Haiku kończyły się `[SKIP:haiku-err]` lub `Output parser received max_tokens stop reason`
- Fix: max_tokens 50 → 200
- Wniosek: dla structured output z 2+ polami minimum to ~150-200 tokenów; nigdy nie schodzić poniżej

**B2 — `_is_edu_or_news_domain` miała literówkę — nigdy nie działała**
- `"pulsbizneu.pl"` zamiast `"pb.pl"` (które już było gdzie indziej)
- Reguła od momentu napisania nie blokowała niczego
- Fix: usunięcie literówki, uproszczenie funkcji do samego `.edu.pl`

**B3 — `_is_blocked()` nie blokowało subdomen**
- `"cyfrowa.rp.pl" in _BLOCKED_DOMAINS` → False (choć `"rp.pl"` było na liście)
- Artykuły z subdomen portali newsowych przechodziły przez filtr
- Fix: `domain.endswith(f".{blocked}")` dla każdej zablokowanej domeny

**B4 — `_name_from_title()` zwracał listę miast jako nazwę firmy**
- "Automatyzacja procesów | AI - Gdańsk, Poznań, Warszawa" → split na " - " → "Gdańsk, Poznań, Warszawa"
- Fix: `_is_junk()` odrzuca tekst gdzie 2+ części po przecinku zaczynają się z dużej litery; zmiana kolejności separatorów (najpierw " | ")

**B5 — Rolling query history blokowała dobre tematy wyszukiwań**
- Historia 5-10 zapytań zabraniała Haiku wracać do tematów gdzie były dobre firmy
- Jeśli użytkownik zaaplikował do firmy HR AI → temat HR AI znikał z możliwych zapytań
- Fix: usunięcie historii. Różnorodność zapewniona przez temperature=0.9; dedup domenowy eliminuje powtórki firm

**B6 — Nawarstwianie zmian bez planu → net regression w jakości**
- Zbyt wiele małych zmian bez analizy skutków ubocznych
- Extract na homepage (wolniejszy) + agresywniejsze filtry + historia = mniej firm znajdowanych
- Lekcja: planować zmiany przed kodowaniem; testować po każdej zmianie, nie po kilku

### Stan po Dniu 6

System działa, znalazł firmy: ccig.pl, tarosystems.pl, feedyou.ai, visionplatform.ai, czatbot.ai, linkway.pl, ai4msp.pl w jednej sesji testowej. Jakość akceptowalna — czasem anglojęzyczna firma lub blog.

Pozostałe known issues:
- Non-.pl firmy z anglojęzycznym homepage i polskim snippetem: snippet może mylić Haiku
- Niektóre blogi przechodzą przez filtry (brak /blog/ w URL, tytuł nie zaczyna od liczby)
- Wyniki chatbot-heavy — natura polskiego rynku AI w wyszukiwarkach

---

## Część II — Podsumowanie dla Konrada

### Co się stało

Sesja naprawcza po tym jak poprzednie "optymalizacje kosztów" zbyt mocno skróciły max_tokens w Haiku (50 to za mało — model urywał odpowiedź w połowie). Naprawiliśmy główny bug, a przy okazji przepisaliśmy sporą część logiki filtrowania i wyszukiwania.

### Co się poprawiło

- **Haiku znowu klasyfikuje poprawnie** — max_tokens 50→200, koniec z błędami parsowania
- **Haiku akceptuje firmy bez słowa "AI"** — machine vision, computer vision, automatyzacja ML teraz przechodzą
- **Portale newsowe blokowane przez Tavily** — rp.pl, pb.pl, infor.pl nigdy nie wrócą w wynikach
- **Subdomeny blokowane poprawnie** — cyfrowa.rp.pl blokowane gdy rp.pl na liście
- **Nazwy firm poprawne** — koniec z "Gdańsk, Poznań, Warszawa" jako nazwa firmy
- **Historia zapytań usunięta** — agent nie blokuje tematów gdzie były dobre firmy
- **Zapytania celują w strony firmowe** — słowa "oferta", "SaaS", "demo" w każdym zapytaniu

### Czego nie robimy (lekcje z tej sesji)

- Nie zmniejszamy max_tokens poniżej 200 dla page_verifier — structured output ma narzut tokenny
- Nie wpisujemy nazw konkretnych firm do promptów — reguły opisują cechy, nie przykłady
- Nie używamy historii zapytań w query_generator — to nie jest problem który trzeba rozwiązywać
- Nie robimy wielu zmian naraz bez testowania każdej — prowadzi do net regression
