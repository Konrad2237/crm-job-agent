# ADR Dzień 5 — Post-MWS: jakość discovery, widoczność danych, UX, bugfixy

Data: 2026-05-10
Branch: `main` (bezpośrednie pushe — jeden użytkownik, zmiany testowane lokalnie)
Status: ukończony, na produkcji

---

## Część I — Dokumentacja techniczna (dla Claude Code)

### Co zostało zbudowane

Sesja skupiona na czterech obszarach: jakość wyszukiwania firm, widoczność danych w CRM, UX tabeli, bugfixy wykryte w trakcie testowania.

### Schemat zmienionych plików

```
backend/
│
├── core/
│   ├── page_verifier.py
│   │   ├── is_ai_company: rozluźniony — TAK dla firm IT/tech z AI jako jednym z obszarów usług
│   │   ├── is_ai_company: NIE dla kursów/szkoleń/akademii AI (false positive)
│   │   └── what_they_do: str = ""  ← FIX: Haiku czasem pomija pole → ValidationError 500
│   │
│   ├── discovery_loop.py
│   │   ├── _POLISH_CHARS + _is_likely_polish(domain, text) → bool
│   │   │   └── pre-filter przed Haiku: domena .pl LUB polskie znaki w snippecie
│   │   ├── _query_history: list[str] = []  ← rolling window 10 ostatnich zapytań
│   │   ├── QUERY_HISTORY_MAX = 10
│   │   ├── snippet = result.get("content", "") przeniesiony przed pre-filter
│   │   └── verify_page: retries=1 (było 2) + try/except → continue przy błędzie parsowania
│   │
│   └── query_generator.py
│       ├── Przywrócona oryginalna lista usług (chatboty, agenci AI, LLM, RAG...)
│       ├── Rotacja: branże + typ firmy (usunięto miasta — szukamy zdalnej pracy)
│       └── Dodano: "usługi", "oferta", "rozwiązania" → zapytania celują w strony firmowe nie artykuły
│
├── db/client.py
│   ├── get_companies() rozszerzony: search, sort, order params
│   │   ├── search: ILIKE na name i domain (sanitized input)
│   │   └── sort: name | created_at | applied_at | status (whitelist)
│   └── get_stats() → {applied, skipped, presented, replied}
│       └── 4 osobne COUNT queries z limit(0) — zero fetching danych
│
└── routers/companies.py
    ├── GET /companies/stats  ← nowy endpoint
    └── GET /companies: +search, +sort, +order params

frontend/
│
├── lib/api.ts
│   ├── getCompanies: +search, +sort, +order params
│   └── getStats: () → Stats
│
├── components/
│   ├── CRMTable.tsx
│   │   ├── Kolumny: +Notatki, +Wynagrodzenie, +Email (były w bazie, niewidoczne)
│   │   ├── Source badge: "agent" (szary) / "ręcznie" (fioletowy) pod domeną
│   │   ├── Sortowalne nagłówki: Firma, Status, Data (SortHeader component)
│   │   ├── Copy email: przycisk "Kopiuj" → "✓ Skopiowano" (1.5s), fallback execCommand
│   │   └── Ciemniejszy tekst: gray-700/800/900 zamiast gray-400/500
│   │
│   └── ManualEntryModal.tsx
│       ├── Usunięta walidacja required (name + url nie są już wymagane)
│       └── Etykiety: gray-700 font-medium zamiast gray-600
│
└── app/crm/page.tsx
    ├── Stats bar: "X aplikacji · Y odpowiedzi (Z%)"
    ├── Status pills z licznikami zamiast dropdowna
    │   └── [Wszystkie] [Aplikacje (12)] [Pominięte (34)] [Pokazane (2)]
    ├── Search input z debounce 350ms → reset page=1
    ├── Sort state: field + "asc"|"desc", reset page=1 przy zmianie
    └── fetchStats() wywoływane: on mount + po manual add + po delete
```

### Decyzje architektoniczne podjęte w Dniu 5

| Decyzja | Wybór | Alternatywa odrzucona | Powód |
|---|---|---|---|
| Rolling window w pamięci procesu | moduł-level `_query_history` | persystencja w DB | Railway trzyma proces tygodniami; przy restarcie reset akceptowalny; zero schematu DB |
| QUERY_HISTORY_MAX = 10 | 10 | 20 | 20 było zbyt duże — agent ma dobrą dywersyfikację przy 10, mniejszy prompt |
| Bez miast w rotacji zapytań | branże + typ firmy | branże + typ firmy + miasta | użytkownik szuka pracy zdalnej — miasto nie ma znaczenia |
| verify_page retries=1 | 1 | 2 (było) | przy błędzie parsowania Haiku ponowienie zazwyczaj daje ten sam wynik; 2 retry = 3× koszt za nic |
| try/except przy verify_page → continue | catch + skip URL | propagacja wyjątku | bez catch: błąd jednego URL kończy cały request; z catch: loop idzie dalej |
| Stats jako osobny endpoint | GET /companies/stats | COUNT w GET /companies | rozdzielenie odpowiedzialności; stats ładowane raz on mount, lista per page-change |
| Search + sort backendowy | backend query params | frontend filter/sort | frontend widzi tylko 20 rekordów (1 strona) — filter/sort na tym byłby bezużyteczny |
| `what_they_do: str = ""` | default empty string | str (required) | Haiku pomija pole gdy któreś kryterium False; Pydantic rzucał ValidationError → 500 |

### Błędy napotkane w Dniu 5

**B1 — ValidationError: what_they_do Field required**
- Przyczyna: Haiku zwrócił `{'is_polish': True, 'is_ai_company': True, 'is_company_page': True}` bez `what_they_do`. Pydantic wymagał pola → 500.
- Objaw: 3 błędy ×3500 tokenów na tej samej stronie — `call_with_retry` próbował 3 razy, za każdym razem ten sam ValidationError
- Fix: `what_they_do: str = ""`; retries=1; try/except → continue
- Wniosek: pola w structured output Haiku muszą mieć default — model nieregularnie pomija opcjonalne pola mimo promptu

**B2 — Timeout przy samych artykułach**
- Przyczyna: Tavily zwracał artykuły i poradniki (np. "Automatyzacja AI w polskich MSP — przewodnik") zamiast stron firmowych. `is_company_page=False` dla wszystkich → loop kończył 25s bez wyniku
- Fix: w query_generator dodano wskazówkę żeby używać "usługi", "oferta", "rozwiązania dla firm"
- Wniosek: zapytania muszą zawierać słowa które trafiają na strony z ofertą, nie na content marketing

**B3 — Ta sama strona pojawiała się w kolejnych sesjach**
- Przyczyna: gdy verify_page rzuca wyjątek, domena nigdy nie trafia do bazy → `is_domain_seen` zwraca False → Tavily znowu ją zwraca
- Mitygacja (nie pełny fix): retries=1 + catch→continue ogranicza koszt z 3×3500 do 1-2×3500; domena wciąż może wrócić w kolejnej sesji
- Pełny fix: zapisywać domeny które failują weryfikację jako "skipped" (do zrobienia)

**B4 — Kursy AI jako false positive**
- Przyczyna: poluzowanie `is_ai_company` pozwoliło przejść firmom sprzedającym kursy AI
- Fix: dodanie "kursy i szkolenia z AI, edukacja, akademia, bootcamp" do listy NIE

### Stan po Dniu 5

Aplikacja dojrzała do codziennego użytku. Discovery jest dokładniejsze, CRM jest czytelny, bugi które kosztowały tokeny naprawione.

---

## Część II — Podsumowanie dla Konrada

### Co zbudowaliśmy

**Lepsza jakość wyszukiwania firm:**
Agent teraz wie żeby szukać "usług" i "oferty" a nie artykułów. Pre-filter odrzuca angielskie strony zanim zapyta Haiku (oszczędność tokenów). Agent pamięta 10 ostatnich zapytań żeby nie kręcić się w kółko. Firmy sprzedające kursy AI są odfiltrowane.

**Więcej danych w tabeli CRM:**
Wcześniej wynagrodzenie, email i notatki można było wpisać przez modal ale tabela ich nie pokazywała. Teraz są widoczne. Przy każdej firmie widać też czy znalazł ją agent czy dodałeś ją ręcznie (badge "agent"/"ręcznie").

**Nowy UX tabeli:**
- Zamiast dropdowna statusów — przyciski z liczbami: "Aplikacje (12)", "Pominięte (34)"
- Pasek statystyk nad tabelą: "12 aplikacji · 3 odpowiedzi (25%)"
- Szukanie po nazwie lub domenie (działa na całej bazie, nie tylko na aktualnej stronie)
- Sortowanie po kolumnach Firma / Status / Data — klik zmienia kierunek
- Przycisk "Kopiuj" przy emailu — zmienia się na "✓ Skopiowano" po kliknięciu

**Bugfixy:**
Trzy błędy po 3500 tokenów każdy na tej samej stronie — Haiku znalazł firmę ale pominął jedno pole w JSONie. Teraz pole ma wartość domyślną i błąd nie wystąpi.

### Do zrobienia

**Zaległe (z poprzednich sesji):**
- `print` w `safe_db_call` → właściwy logger (niska priorytetowość — logi idą do Railway stdout i działają)

**Nowe (odkryte w tej sesji):**
- Domeny które failują weryfikację (błąd Haiku, nie dlatego że nie-AI) wciąż mogą wracać w kolejnych sesjach — można je zapisywać jako "skipped" żeby Tavily nie zwracał ich ponownie
- Tavily `search_depth="advanced"` — lepsze wyniki kosztem większego zużycia kredytów (1 kredyt → 2 kredyty na zapytanie); warto przetestować czy poprawia jakość
