# ADR Dzień 1 — Backend Foundation

Data: 2026-05-08
Branch: `feature/day-1-backend-foundation`
Status: ukończony, zmergowany do main

---

## Część I — Dokumentacja techniczna (dla Claude Code)

### Co zostało zbudowane

Fundament backendu: struktura projektu, zależności, FastAPI app, warstwa bazy danych, generator zapytań LLM. Żadnych endpointów HTTP jeszcze — to Dzień 2.

### Schemat plików i zależności

```
crm-job-agent/
│
├── requirements.txt                  # deklaracja zależności Python
├── .gitignore                        # blokuje .env, .venv/, .claude/
├── .env.example                      # szablon zmiennych bez sekretów
├── README.md                         # dokumentacja projektu na GitHub
│
└── backend/
    ├── main.py                       # punkt wejścia FastAPI
    │   └── load_dotenv()
    │   └── CORSMiddleware → allow_origins: [FRONTEND_URL, localhost:3000]
    │   └── GET / → health_check()
    │
    ├── models/
    │   └── schemas.py                # Pydantic modele request/response
    │       ├── CompanyOut            # kształt firmy zwracanej do frontendu
    │       ├── ApplyRequest          # dane po kliknięciu "Wysłałem CV"
    │       ├── ManualCompanyRequest  # ręczne dodanie firmy (faza 3)
    │       └── PatchCompanyRequest   # edycja pól w CRM Dashboard
    │
    ├── db/
    │   └── client.py                 # jedyne miejsce które dotyka bazy
    │       ├── normalize_domain(url) → str
    │       │   └── urlparse → netloc.lower().removeprefix("www.")
    │       ├── _get_client() → AsyncClient   [lazy init, singleton]
    │       │   └── create_async_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    │       ├── safe_db_call(coro) → Any      [wrapper na każde zapytanie]
    │       │   └── Exception → HTTPException(503)
    │       ├── is_domain_seen(domain) → bool
    │       │   └── SELECT id FROM companies WHERE domain=? LIMIT 1
    │       ├── save_company(...) → dict
    │       │   └── UPSERT ON CONFLICT (domain) DO NOTHING → fetch existing
    │       ├── get_recent_presented() → dict | None
    │       │   └── WHERE status='presented' AND created_at > NOW()-24h
    │       ├── cleanup_stale_presented() → None
    │       │   └── UPDATE status='skipped' WHERE status='presented' AND created_at < NOW()-24h
    │       ├── update_company_status(id, status, extra) → dict
    │       └── get_companies(status, limit, offset) → list[dict]
    │           └── .range(offset, offset+limit-1)   [zawsze paginacja]
    │
    ├── core/
    │   └── query_generator.py        # LLM call #1 z 2 na cały discovery
    │       ├── _model = ChatAnthropic(
    │       │       model="claude-haiku-4-5-20251001",
    │       │       max_tokens=100,
    │       │       temperature=0.9
    │       │   )
    │       └── generate_query(previous_queries: list[str]) → str
    │           ├── SystemMessage: instrukcja szukania polskich firm AI
    │           └── HumanMessage: lista poprzednich zapytań do uniknięcia
    │
    └── test_query_generator.py       # skrypt do ręcznego testowania (nie prod)
        └── asyncio.run(main())
            └── generate_query([]) → q1
            └── generate_query([q1]) → q2
            └── generate_query([q1, q2]) → q3
```

### Przepływ danych — query_generator

```
test_query_generator.py
    │
    └── generate_query(previous_queries)
            │
            ├── SystemMessage (SYSTEM_PROMPT)
            ├── HumanMessage (lista poprzednich)
            │
            └── ChatAnthropic.ainvoke()
                    │
                    └── Anthropic API (Haiku)
                            │
                            └── response.content.strip() → zapytanie string
```

### Przepływ danych — Supabase client

```
dowolny caller (discovery_loop — Dzień 2)
    │
    └── safe_db_call( supabase_query.execute() )
            │
            ├── OK → zwróć result
            └── Exception → HTTPException(503)

normalize_domain("https://www.firma.pl/page")
    │
    └── urlparse → netloc="www.firma.pl"
    └── .lower().removeprefix("www.") → "firma.pl"
```

### Decyzje architektoniczne podjęte w Dniu 1

| Decyzja | Wybór | Alternatywa odrzucona | Powód |
|---|---|---|---|
| Klient Supabase | async (`create_async_client`) | sync | FastAPI jest async — sync klient blokowałby event loop |
| Init klienta | lazy (przy pierwszym użyciu) | przy starcie serwera | serwer startuje nawet gdy Supabase chwilowo down |
| INSERT strategy | UPSERT + `ignore_duplicates=True` | czysty INSERT | race condition przy równoległych requestach → duplikaty |
| Haiku temperature | 0.9 | 0.0–0.5 | niska temperatura = powtarzające się zapytania Tavily |
| Haiku max_tokens | 100 | domyślne 1024+ | zapytanie to 5–10 słów, wyższy limit = przepłacanie |
| Supabase klucz | `service_role` | `anon` | `anon` respektuje RLS — za słabe uprawnienia dla backendu |
| Jedna tabela | `companies` | osobne tabele | jeden użytkownik, prosta domena — normalizacja bez sensu |

### Błędy napotkane w Dniu 1

**B1 — ModuleNotFoundError: langchain_anthropic przy pierwszym teście**
- Przyczyna: `pip install` uruchomiony w tle, test odpaliłem zanim instalacja się skończyła
- Fix: poczekać na zakończenie instalacji, drugi run testu przeszedł poprawnie
- Wpływ: zero — środowisko produkcyjne instaluje synchronicznie

**B2 — UnicodeEncodeError: znak `→` w terminalu Windows**
- Przyczyna: terminal Windows używa kodowania cp1250, które nie obsługuje U+2192
- Fix: zamiana `→` na `>>` w `test_query_generator.py`
- Wpływ: zero — tylko plik testowy, nie kod produkcyjny

### Stan Supabase po Dniu 1

Tabela `companies` z pełnym schematem (UUID PK, UNIQUE domain, wszystkie pola CRM, timestampy, trigger `update_updated_at`). Trzy indeksy: `domain`, `status`, `created_at DESC`.

### Co NIE zostało zbudowane w Dniu 1 (celowo)

- Endpointy HTTP (`/find`, `/skip`, `/apply`) → Dzień 2
- `page_verifier.py` → Dzień 2
- `discovery_loop.py` → Dzień 2
- Frontend → Dzień 3

---

## Część II — Podsumowanie dla Konrada

### Co zbudowaliśmy

Zbudowaliśmy **fundamenty backendu** — wszystko to co musi istnieć zanim agent w ogóle zacznie szukać firm. Żadnej widocznej strony jeszcze — to był "dzień kopania fundamentów pod dom".

### Konkretnie co powstało

**Baza danych w Supabase** — tabela `companies` gdzie będą lądować wszystkie firmy znalezione przez agenta. Jeden rekord = jedna firma + wszystko o niej: link, opis, status (czy wysłałeś CV, czy pominąłeś), Twoje notatki, wynagrodzenie które podałeś, odpowiedź od firmy. Jedna tabela na wszystko — nie cztery jak w poprzednim projekcie.

**Backend — szkielet** (`main.py`) — uruchamia serwer, konfiguruje kto może się z nim łączyć (tylko Twój frontend, nie ktoś przypadkowy z internetu).

**Warstwa bazy danych** (`db/client.py`) — wszystkie zapytania do bazy w jednym miejscu. Najważniejsza rzecz: jeśli Supabase padnie lub będzie wolny, użytkownik dostanie czytelny komunikat zamiast brzydkiego błędu technicznego. Plus normalizacja domen — `www.firma.pl` i `firma.pl` to ta sama firma, nie dwie różne.

**Generator zapytań** (`query_generator.py`) — pierwszy kontakt z Claude Haiku. Haiku dostaje listę zapytań których już użyliśmy i generuje nowe, inne. To co widziałeś w LangSmith — 1 sekunda, 300–400 tokenów, ~$0.0003 za jedno zapytanie.

### Co sprawdziliśmy i co działa

Uruchomiłeś test i widziałeś w LangSmith trzy różne, sensowne zapytania po polsku. Haiku działa. Klucze API działają. LangSmith monitoruje bez żadnej dodatkowej konfiguracji.

### Co NIE działa jeszcze (celowo)

Nie masz jeszcze żadnej strony do otwarcia w przeglądarce — to normalne. Backend nie szuka jeszcze firm — to Dzień 2. Nie możesz kliknąć "Znajdź firmę" — to Dzień 3. Dzisiaj zrobiliśmy to co niewidoczne ale konieczne.

### Gdzie jesteśmy na mapie projektu

```
[Dzień 1 - DONE] Fundamenty backendu + baza danych
[Dzień 2 - NEXT] Agent szuka firm, endpointy HTTP
[Dzień 3        ] Frontend + deployment na Railway/Vercel
```

Po Dniu 2 będziesz mógł przez terminal wywołać agenta i dostać prawdziwą polską firmę AI — bez frontendu, ale core systemu będzie działał.
