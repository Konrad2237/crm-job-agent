# CLAUDE.md — CRM Job Agent

Plik instrukcji dla Claude Code. Czytaj przed każdą sesją kodowania.

---

## Czym jest ten projekt

Narzędzie do szukania polskich firm AI w internecie i śledzenia aplikacji o pracę.

**Problem który rozwiązuje:** Ręczne szukanie firm przez ChatGPT daje złe linki, angielskie strony i ciągłe powtórki. Notatnik z firmami nie ma linków, dat, stanowisk ani statusów — użytkownik gubi się we własnych aplikacjach.

**Jak działa:** Użytkownik klika "Znajdź firmę" → agent wyszukuje jedną polską firmę z obszaru AI której jeszcze nie odwiedził → użytkownik otwiera link, decyduje czy aplikuje → dane trafiają do CRM → agent szuka kolejnej.

**Jeden użytkownik. Nie budujemy SaaS-a.**

---

## Stack technologiczny

| Warstwa | Technologia | Hosting |
|---|---|---|
| Frontend | Next.js (App Router) + Tailwind CSS | Vercel |
| Backend | Python 3.12 + FastAPI | Railway |
| Baza danych | PostgreSQL | Supabase |
| LLM framework | LangChain (`langchain`, `langchain-anthropic`) | — |
| LLM model | Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) | Anthropic API |
| Wyszukiwanie | SerpAPI (Google Search) przez `google-search-results` | zewnętrzne |
| Monitoring | LangSmith (natywna integracja z LangChain) | zewnętrzne |

---

## Struktura folderów

```
crm-job-agent/
├── CLAUDE.md                        ← ten plik
├── backend/
│   ├── main.py                      # FastAPI app, CORS, rejestracja routerów
│   ├── routers/
│   │   ├── discovery.py             # POST /find, POST /companies/{id}/skip, POST /companies/{id}/apply
│   │   └── companies.py             # GET /companies, POST /companies/manual, PATCH /companies/{id}
│   ├── core/
│   │   ├── discovery_loop.py        # główna pętla szukania (Python, nie LLM)
│   │   ├── query_generator.py       # generuje zapytanie Tavily (Haiku)
│   │   └── page_verifier.py         # klasyfikuje stronę: polska + AI? (Haiku)
│   ├── db/
│   │   └── client.py                # Supabase client + wszystkie zapytania SQL
│   └── models/
│       └── schemas.py               # Pydantic modele request/response
├── frontend/
│   ├── app/
│   │   ├── page.tsx                 # widok Discovery (główny)
│   │   └── crm/
│   │       └── page.tsx             # CRM Dashboard
│   └── components/
│       ├── CompanyCard.tsx          # karta znalezionej firmy + przyciski decyzji
│       ├── ApplicationForm.tsx      # formularz po "wysłałem CV"
│       ├── CRMTable.tsx             # tabela wszystkich firm z paginacją
│       └── ManualEntryModal.tsx     # modal ręcznego dodawania (faza 3)
├── .env                             # NIE commitować — jest w .gitignore
├── .env.example                     # szablon bez sekretów — commitować
└── requirements.txt
```

---

## Zasady których przestrzegamy

### Architektura

- **LLM robi TYLKO dwie rzeczy:** generuje zapytanie i klasyfikuje stronę. Cała logika pętli jest w Pythonie. Żadnych agentic loops gdzie LLM decyduje kiedy kończyć — to droga do 800k tokenów (poprzednie podejście które się nie sprawdziło).
- **Jeden komponent, jedna odpowiedzialność.** `query_generator.py` tylko generuje zapytania. `page_verifier.py` tylko klasyfikuje. `discovery_loop.py` tylko orkiestruje.
- **Fail fast, fail loud.** Błąd zewnętrznego API = retry 2×, potem czytelny komunikat dla użytkownika. Nigdy cichy fail.

### Kod

- **Zawsze normalizuj domenę** przed zapisem i dedup checkiem:
  ```python
  from urllib.parse import urlparse
  def normalize_domain(url: str) -> str:
      return urlparse(url).netloc.lower().removeprefix("www.")
  ```
- **Zawsze truncuj treść strony** przed wysłaniem do Haiku — max 2,000 znaków:
  ```python
  content = raw_content[:2_000]
  ```
- **Zawsze używaj `call_with_retry()`** dla wywołań Tavily i Anthropic API (retry 2×, delay 2 sek).
- **Zawsze używaj `safe_db_call()`** dla wywołań Supabase (łapie wyjątki, zwraca 503).
- **Zawsze używaj `asyncio.timeout(55)`** na całą funkcję `find_company()` — Extract homepage dodaje 3-8s/kandydat.
- **INSERT zawsze z `ON CONFLICT (domain) DO NOTHING`** — nigdy czysty INSERT do tabeli `companies`.
- **Brak komentarzy do oczywistego kodu.** Komentarz tylko gdy WHY jest nieoczywiste.
- **Brak nadmiarowej obsługi błędów** dla sytuacji które nie mogą wystąpić.

### Frontend

- **Disable przycisku "Znajdź firmę"** podczas trwającego requesta — zapobiega race condition.
- **Po zapisaniu aplikacji** (`POST /apply`) automatycznie wywołaj kolejne `POST /find` bez dodatkowego kliknięcia użytkownika.
- **Paginacja w CRM Dashboard** — nigdy nie pobieraj wszystkich rekordów naraz.

### Baza danych

- **Tabela `companies` ma `UNIQUE (domain)`** — egzekwowane na poziomie DB, nie tylko aplikacji.
- **Dedup sprawdzamy po znormalizowanej domenie**, nie po pełnym URL.
- Status `presented` starszy niż 24h czyszczony automatycznie do `skipped` przy każdym `POST /find`.

### Git

- **Bezpośrednie pushe na `main`** — jeden użytkownik, każda zmiana testowana lokalnie przed pushem. Branche tylko przy dużych/ryzykownych zmianach.
- **Nigdy `git push --force` na `main`.**
- **`.env` jest w `.gitignore`** — sprawdź zanim zrobisz pierwszy commit.

---

## Czego NIE robimy

| Czego nie robimy | Dlaczego |
|---|---|
| **Nie używamy agentic loop z LangChain** (gdzie LLM sam decyduje kiedy skończyć) | Poprzednie podejście = 800k tokenów, zero odpowiedzi. Pętla jest w Pythonie, LangChain używamy tylko do wywołań LLM i Tavily. |
| **Nie robimy agentic loop** (LLM decyduje kiedy skończyć) | Brak kontroli nad tokenami. Loop jest w Pythonie, LLM tylko klasyfikuje. |
| **Nie używamy n8n jako orchestratora** | Poprzednie podejście się nie sprawdziło. Backend w Pythonie. |
| **Nie robimy mikroserwisów** | Jeden użytkownik, jeden monolit na Railway. Mikroserwisy rozwiązują problemy skali których nie mamy. |
| **Nie używamy serverless** | Discovery loop trwa 10–25 sek, przekracza limity timeout Vercel Functions. |
| **Nie pobieramy wszystkich rekordów naraz** | Przy 500+ rekordach frontend crashnie. Zawsze paginacja. |
| **Nie wysyłamy pełnej treści strony do LLM** | Max 2,000 znaków. Reszta to blog i artykuły — niepotrzebne do klasyfikacji. |
| **Nie oceniamy dopasowania kandydata** | Agent tylko weryfikuje: polska strona + usługi AI. Ocena należy do użytkownika. |
| **Nie szukamy ofert pracy ani wymagań** | Szukamy firm. Użytkownik sam ocenia czy aplikować. |
| **Nie budujemy multi-user** | Jeden użytkownik, brak auth, brak izolacji danych między kontami. |
| **Nie używamy historii zapytań w query_generator** | Historia blokowała dobre tematy — jeśli użytkownik zaaplikował do firmy HR AI, agent przestawał szukać w HR AI. Dedup domen (`get_seen_domains`) wystarczy do unikania powtórek. |
| **Nie wpisujemy nazw konkretnych firm do promptów Haiku** | Hardkodowanie "SAP, GFT, Randstad" jako przykładów jest kruche — Accenture czy Capgemini nie byłyby blokowane. Prompty muszą opisywać CECHY (globalna korporacja, strona po angielsku), nie konkretne firmy. |
| **Nie ustawiamy max_tokens < 200 dla page_verifier** | Structured output przez Anthropic tool_use ma ~80-100 tokenów overhead na nagłówek narzędzia. Przy 50 lub 100 tokenach Haiku urywa output po pierwszym polu (`is_polish`) i nigdy nie wypełnia `is_ai_company`. |

---

## Aktualny status projektu

**Faza: MWS ukończony — aplikacja na produkcji**
*(aktualizuj przy każdej sesji)*

Ukończone:
- [x] Discovery phase — zrozumienie problemu
- [x] Dekompozycja systemu na komponenty
- [x] Architektura techniczna
- [x] Schemat bazy danych
- [x] MWS plan (3 dni)
- [x] Stress test architektury
- [x] Testy scenariuszowe (5 przypadków)
- [x] Identyfikacja luk i poprawek
- [x] Dzień 1: Supabase setup + backend foundation
- [x] Dzień 2: Discovery loop + endpointy
  - [x] `core/page_verifier.py` — Haiku klasyfikuje stronę (structured output)
  - [x] `core/discovery_loop.py` — pętla Python z timeout(25), call_with_retry, snippet fallback
  - [x] `routers/discovery.py` — POST /find, /skip, /apply
  - [x] `routers/companies.py` — GET /companies, PATCH /companies/{id}
  - [x] Test end-to-end: POST /find zwraca prawdziwą firmę, dedup działa
- [x] Dzień 3: Frontend + deployment
  - [x] `lib/api.ts` — klient HTTP dla wszystkich endpointów
  - [x] `app/page.tsx` — Discovery view z przyciskiem disable + auto-find po apply
  - [x] `app/crm/page.tsx` — CRM Dashboard z filtrem statusu
  - [x] `components/CompanyCard.tsx` — karta firmy + przyciski Pomiń/Wysłałem CV
  - [x] `components/ApplicationForm.tsx` — formularz zapisywania aplikacji
  - [x] `components/CRMTable.tsx` — tabela z paginacją
  - [x] `Procfile` — start command dla Railway railpack
  - [x] Backend na Railway: `https://crm-job-agent-production.up.railway.app`
  - [x] Frontend na Vercel: `https://crm-job-agent.vercel.app`
  - [x] Fix: `is_company_page` w page_verifier — odrzuca listy rankingowe

Po MWS — ukończone:
- [x] **[U3]** Shared secret header `X-API-Key` między frontendem a backendem
- [x] Heurystyczny pre-filter (.pl / polskie znaki) przed wywołaniem Haiku
- [x] Manual Entry Form z OLX/Pracuj.pl
- [x] Śledzenie odpowiedzi (reply_status / reply_received)
- [x] Edycja i usuwanie firm z CRM
- [x] Search + sort w CRM (backendowy, działa na całej bazie)
- [x] Stats bar z licznikami statusów
- [x] Domeny failujące `verify_page` zapisywane jako `skipped` — nie wracają w kolejnych sesjach
- [x] `MAX_CONTENT_CHARS` 6000 → 2000 — ~66% mniej tokenów input dla page_verifier
- [x] Batch dedup domen — 1 zapytanie DB per attempt zamiast 5

Dzień 6 — naprawy discovery:
- [x] `max_tokens` page_verifier: 50 → 200 (structured output wymaga min. ~150 tokenów)
- [x] `what_they_do` usunięty z `save_company` i `page_verifier` — zawsze był pusty
- [x] Portale newsowe (rp.pl, pb.pl, infor.pl, itwiz.pl…) dodane do `_BLOCKED_DOMAINS`
- [x] `_is_blocked()` blokuje teraz subdomeny (cyfrowa.rp.pl gdy rp.pl na liście)
- [x] Filtr tytułów zaczynających się od liczby (`_TITLE_NUMBER_START_RE`) — artykuły
- [x] Filtr URLi kończących się `.pdf`
- [x] `page_verifier` prompt: nie wymaga słowa "AI" — akceptuje ML, NLP, computer vision, automatyzację
- [x] `verify_page()` dostaje domenę i tytuł jako dodatkowy kontekst
- [x] `.pl` domeny → Extract homepage; non-`.pl` → snippet z Tavily
- [x] `search_depth="advanced"` w Tavily — głębsze indeksowanie, lepsze wyniki dla małych firm
- [x] `MAX_RESULTS` 3 → 5
- [x] Historia zapytań (`_query_history`) usunięta — blokowała dobre tematy
- [x] Zapytania Haiku muszą zawierać słowo firmowe (oferta/SaaS/demo/B2B/wdrożenia)
- [x] `_name_from_title()` naprawiony — nie zwraca list miast jako nazwy firmy

---

## Znane problemy i rzeczy do zrobienia

### Krytyczne (przed pierwszą linią kodu)

- [x] **[K1]** Dodać `UNIQUE (domain)` do tabeli `companies` w Supabase
- [x] **[K1]** Używać `ON CONFLICT (domain) DO NOTHING` przy każdym INSERT (`db/client.py`)
- [x] **[K1]** Disable przycisku w `CompanyCard.tsx` podczas requesta — zaimplementowane
- [x] **[K2]** Truncacja treści do 6,000 znaków (`discovery_loop.py`)
- [x] Plik `.env` w `.gitignore`

### Poważne (w trakcie MWS)

- [x] **[P1]** `asyncio.timeout(25)` w `discovery_loop.py`
- [x] **[P2]** `safe_db_call()` wrapper w `db/client.py`
- [x] **[P3]** `call_with_retry()` dla Tavily i Anthropic
- [x] **[P4]** Sprawdzenie pending `presented` na starcie każdego `/find` (`get_recent_presented`)
- [x] **[P4]** Cleanup `presented` > 24h → `skipped` (`cleanup_stale_presented`)
- [x] **[P5]** Auto-trigger kolejnego `/find` po zapisaniu aplikacji — zaimplementowane w `app/page.tsx`

### Umiarkowane (po MWS)

- [x] **[U1]** Fallback na snippet gdy Tavily Extract zwraca < 300 znaków (`discovery_loop.py`)
- [x] **[U2]** `normalize_domain()` — stripuje `www.` (`db/client.py`)
- [x] **[U3]** CORS — `FRONTEND_URL` ustawiony w Railway
- [x] **[U3]** Shared secret header `X-API-Key` między frontendem a backendem
- [x] **[U4]** Paginacja `GET /companies` — `?page=1&limit=20&status=applied`
- [x] CRM Dashboard — `app/crm/page.tsx` + `components/CRMTable.tsx`
- [x] Manual Entry Form z OLX/Pracuj.pl
- [x] LangSmith tracing — env vars ustawione w Railway

---

## Zmienne środowiskowe

```env
# Backend (Railway)
ANTHROPIC_API_KEY=
TAVILY_API_KEY=
SUPABASE_URL=                        # tylko domena: https://xxx.supabase.co (BEZ /rest/v1/)
SUPABASE_SERVICE_ROLE_KEY=           # z zakładki Legacy w Supabase → service_role
API_SECRET=                          # shared secret z frontendem
LANGSMITH_TRACING=true               # opcjonalne
LANGSMITH_API_KEY=                   # opcjonalne
LANGSMITH_PROJECT=crm-job-agent      # opcjonalne
FRONTEND_URL=                        # URL frontendu Vercel (do CORS)

# Frontend (Vercel)
NEXT_PUBLIC_API_URL=                 # URL Railway backend
NEXT_PUBLIC_API_SECRET=              # ten sam co API_SECRET w backendzie
```

### Uwagi do setupu (nauczone na błędach)

- `SUPABASE_URL` — tylko domena bez ścieżki. SDK sam dodaje `/rest/v1/`
- `SUPABASE_SERVICE_ROLE_KEY` — nie `SUPABASE_SERVICE_KEY`. Klucz z zakładki **Legacy** w Supabase → service_role (nie anon)
- `.env` leży w głównym folderze projektu (`crm-job-agent/.env`), nie w `backend/`
