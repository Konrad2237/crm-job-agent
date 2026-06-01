# ADR Dzień 2 — Discovery Loop + API Endpoints

Data: 2026-05-08
Branch: `feature/day-2-discovery-loop`
Status: ukończony, zmergowany do main

---

## Część I — Dokumentacja techniczna (dla Claude Code)

### Co zostało zbudowane

Kompletna logika discovery: klasyfikator stron, pętla wyszukiwania, wszystkie endpointy HTTP. Po Dniu 2 backend jest w pełni funkcjonalny — można przez curl/Postman znaleźć firmę, pominąć ją, zaaplikować.

### Schemat nowych plików i zależności

```
backend/
│
├── core/
│   ├── page_verifier.py              # LLM call #2 — klasyfikacja strony
│   │   ├── PageVerification(BaseModel)
│   │   │   ├── is_polish: bool
│   │   │   ├── is_ai_company: bool
│   │   │   └── what_they_do: str
│   │   ├── _model = ChatAnthropic(
│   │   │       model="claude-haiku-4-5-20251001",
│   │   │       max_tokens=150,
│   │   │       temperature=0.0           ← determinizm, nie kreatywność
│   │   │   ).with_structured_output(PageVerification)
│   │   └── verify_page(content: str) → PageVerification
│   │
│   └── discovery_loop.py             # pętla Python — serce systemu
│       ├── call_with_retry(fn, retries=2, delay=2.0)
│       │   └── fn = callable → coroutine  (nie coroutine wprost — patrz decyzje)
│       ├── _get_tavily() → AsyncTavilyClient  [singleton]
│       ├── _extract_content(tavily, url, snippet) → str
│       │   ├── tavily.extract([url]) → raw_content
│       │   ├── fallback: snippet jeśli len(content) < 300
│       │   └── truncate: content[:6_000]
│       └── find_company() → dict | None
│           ├── asyncio.timeout(25) → HTTPException(503) przy przekroczeniu
│           ├── get_recent_presented() → zwróć pending lub None
│           ├── cleanup_stale_presented()
│           └── for attempt in range(3):
│               └── generate_query → tavily.search(max_results=5)
│                   └── for url in results:
│                       ├── normalize_domain + is_domain_seen → skip
│                       ├── _extract_content
│                       ├── verify_page → skip jeśli not polish/ai
│                       └── save_company → return
│
├── routers/
│   ├── discovery.py
│   │   ├── POST /find → find_company() → CompanyOut | 404
│   │   ├── POST /companies/{id}/skip → update_company_status("skipped")
│   │   └── POST /companies/{id}/apply → update_company_status("applied") + applied_at
│   │
│   └── companies.py
│       ├── GET /companies?page=1&limit=20&status=X → get_companies(...)
│       └── PATCH /companies/{id} → patch_company_fields(payload)
│
├── db/client.py                      # zmiany względem Dnia 1
│   ├── + patch_company_fields(company_id, payload) → dict
│   └── safe_db_call: Exception → print(f"[DB ERROR]...") + HTTPException(503)
│
└── main.py                           # zmiany względem Dnia 1
    ├── load_dotenv(Path(__file__).parent.parent / ".env")  ← bezwzględna ścieżka
    └── app.include_router(discovery.router)
        app.include_router(companies.router)
```

### Pełny przepływ POST /find

```
HTTP POST /find
    │
    └── find_company()
            │
            asyncio.timeout(25)
            │
            ├── get_recent_presented()        [Supabase SELECT]
            │   └── jeśli pending → return pending (nie szukaj nowej)
            │
            ├── cleanup_stale_presented()     [Supabase UPDATE]
            │
            └── for attempt in range(3):
                    │
                    ├── call_with_retry(λ: generate_query(previous_queries))
                    │       └── ChatAnthropic.ainvoke → string zapytania
                    │
                    ├── call_with_retry(λ q=query: tavily.search(q, max_results=5))
                    │       └── {"results": [{"url", "title", "content"}, ...]}
                    │
                    └── for result in results:
                            │
                            ├── normalize_domain(url) → "firma.pl"
                            ├── is_domain_seen(domain) → skip jeśli True
                            │
                            ├── _extract_content(tavily, url, snippet)
                            │   ├── call_with_retry(λ: tavily.extract([url]))
                            │   ├── fallback na snippet jeśli < 300 znaków
                            │   └── truncate do 6_000 znaków
                            │
                            ├── call_with_retry(λ c=content: verify_page(c))
                            │   └── ChatAnthropic + structured_output → PageVerification
                            │       └── skip jeśli not is_polish or not is_ai_company
                            │
                            └── save_company(name, url, domain, what_they_do)
                                    └── UPSERT ON CONFLICT DO NOTHING
                                    └── return dict → HTTP 200
```

### Decyzje architektoniczne podjęte w Dniu 2

| Decyzja | Wybór | Alternatywa odrzucona | Powód |
|---|---|---|---|
| `call_with_retry` przyjmuje callable, nie coroutine | `fn()` przy każdym retry | przekazanie gotowej coroutine | zużyta coroutine nie może być awaited drugi raz — nowa musi powstać przy każdym retry |
| `lambda q=query:` w pętli | default argument | `lambda: fn(query)` | bez `q=query` wszystkie lambdy używałyby ostatniej wartości `query` z pętli (Python late binding) |
| `temperature=0.0` w page_verifier | 0.0 | >0 | klasyfikacja binarna (tak/nie) wymaga deterministycznych odpowiedzi |
| `with_structured_output(PageVerification)` | structured output | ręczny JSON parsing | automatyczna walidacja Pydantic, zero kodu parsującego, retry przy błędzie formatu |
| Tavily extract z listą `[url]` | `[url]` | string `url` | explicite lista — lepsza zgodność z API niezależnie od wersji biblioteki |
| `load_dotenv` z bezwzględną ścieżką | `Path(__file__).parent.parent / ".env"` | `load_dotenv()` bez argumentów | pewność że serwer znajdzie `.env` niezależnie od CWD przy starcie |

### Błędy napotkane w Dniu 2

**B1 — KeyError: SUPABASE_SERVICE_KEY**
- Przyczyna: `.env` użytkownika miał klucz `SUPABASE_SERVICE_ROLE_KEY`, kod szukał `SUPABASE_SERVICE_KEY`
- Fix: zmiana nazwy w `db/client.py` i `.env.example` na `SUPABASE_SERVICE_ROLE_KEY`
- Wniosek: zawsze sprawdzaj dokładne nazwy kluczy w `.env` przed deploymentem

**B2 — load_dotenv nie ładował zmiennych przy starcie serwera**
- Przyczyna: `.env` jest w `crm-job-agent/`, serwer startuje z `crm-job-agent/backend/` — `load_dotenv()` bez argumentów nie szukał w katalogu wyżej
- Fix: `load_dotenv(Path(__file__).parent.parent / ".env")`
- Wniosek: test_query_generator.py działał (bo też staruje z `backend/`) — ale uvicorn mógł startować z innego CWD

**B3 — PGRST125: Invalid path specified in request URL**
- Przyczyna: `SUPABASE_URL` miał `/rest/v1/` na końcu (`https://xxx.supabase.co/rest/v1/`). SDK dodaje ten fragment automatycznie — powstało `/rest/v1/rest/v1/`
- Fix: skrócenie URL do samej domeny `https://xxx.supabase.co`
- Wniosek: dodać do onboardingu — SUPABASE_URL to tylko domena, bez ścieżki

**B4 — safe_db_call pochłaniał szczegóły błędów**
- Przyczyna: `except Exception: raise HTTPException(503)` — oryginalny wyjątek ginął
- Fix: `print(f"[DB ERROR] {type(e).__name__}: {e}")` przed re-raise
- Wniosek: wrapper musi logować przed połknięciem wyjątku; na produkcji zastąpić `print` loggerem

### Wyniki testów end-to-end

```
POST /find
→ {"id": "1e53fc39...", "name": "dasx.pl", "domain": "dasx.pl",
   "what_they_do": "chatboty AI dla e-commerce...", "status": "presented"}

POST /companies/1e53fc39.../skip
→ {"status": "skipped", "updated_at": "2026-05-08T18:01:43..."}

POST /find (drugi raz)
→ {"name": "InteliWISE", "domain": "inteliwise.com", ...}  ← dedup działa, dasx.pl nie wraca
```

LangSmith: page_verifier ~800-3000 tokenów (zależnie od długości strony), query_generator ~300-400 tokenów.

### Stan po Dniu 2

Backend kompletny. Wszystkie krytyczne i poważne fixy z architektury wdrożone poza:
- `CompanyCard.tsx` disable button — Dzień 3
- Auto-trigger `/find` po apply — Dzień 3

---

## Część II — Podsumowanie dla Konrada

### Co zbudowaliśmy

Zbudowaliśmy **mózg agenta** — tę część która faktycznie szuka firm i podejmuje decyzje. Po Dniu 1 mieliśmy fundamenty (baza, połączenia). Po Dniu 2 mamy działający silnik: wpisz `/find` → agent szuka, ocenia, zapisuje i zwraca firmę.

### Konkretnie co powstało

**Klasyfikator stron** (`page_verifier.py`) — drugi kontakt z Claude Haiku. Dostaję treść strony i pytam Haiku: "czy to polska firma? czy zajmuje się AI?" Haiku odpowiada strukturalnie — tak/nie + krótki opis. Temperatura 0.0, bo przy ocenianiu chcemy zawsze tę samą decyzję dla tej samej strony, nie losowości.

**Pętla wyszukiwania** (`discovery_loop.py`) — serce systemu. Python kontroluje kiedy kończyć, nie AI. Schemat: wygeneruj zapytanie → szukaj w Tavily → dla każdego wyniku sprawdź czy już widziany → pobierz treść strony → oceń przez Haiku → zapisz i zwróć. Jeśli strona jest pusta (nowoczesne aplikacje React) — używamy snippetu z wyników wyszukiwania jako zapasowego. Twardy limit 25 sekund na całość.

**Endpointy HTTP** — trzy dla agenta (znajdź, pomiń, zaaplikuj) i dwa dla CRM (lista firm, edycja). Po tej sesji możesz przez terminal wywołać `/find` i dostać prawdziwą firmę.

### Gdzie jesteśmy na mapie projektu

```
[Dzień 1 - DONE] Fundamenty: baza, połączenia, generator zapytań
[Dzień 2 - DONE] Silnik: klasyfikator, pętla wyszukiwania, API
[Dzień 3 - NEXT] Twarz: frontend Next.js + deployment Railway/Vercel
```

### Co sprawdziliśmy i co działa

- Agent znalazł **dasx.pl** — polska firma robiąca chatboty AI
- Pominięcie zadziałało — status zmieniony na `skipped`
- Dedup zadziałał — przy drugim `/find` agent zwrócił **InteliWISE**, nie znowu dasx.pl
- Widoczne w LangSmith — każde wywołanie Haiku z tokenami i latencją

### 3 bugi które naprawiliśmy po drodze

1. **Zła nazwa klucza** — w `.env` było `SUPABASE_SERVICE_ROLE_KEY`, w kodzie szukałem `SUPABASE_SERVICE_KEY`. Fix: ujednolicenie nazwy.
2. **Zły URL Supabase** — miałeś `/rest/v1/` na końcu URL. SDK dodaje to samo. Fix: skrócić do samej domeny.
3. **Zaginione logi błędów** — `safe_db_call` łapał wyjątki ale ich nie logował, więc widać było tylko "503" bez powodu. Fix: dodanie `print` przed złapaniem.

### Koszt tokenów po Dniu 2

- Query generator: ~300-400 tokenów / zapytanie
- Page verifier: ~800-3000 tokenów / strona (zależnie od treści)
- Worst case jedno kliknięcie: ~12k tokenów = ~$0.012
- Przy 100 kliknięciach miesięcznie: ~$1.20
