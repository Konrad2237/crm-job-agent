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
| LLM framework | LangChain (`langchain`, `langchain-anthropic`, `langchain-community`) | — |
| LLM model | Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) | Anthropic API |
| Wyszukiwanie | Tavily API przez `langchain-community` | zewnętrzne |
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
- **Zawsze truncuj treść strony** przed wysłaniem do Haiku — max 6,000 znaków:
  ```python
  content = raw_content[:6_000]
  ```
- **Zawsze używaj `call_with_retry()`** dla wywołań Tavily i Anthropic API (retry 2×, delay 2 sek).
- **Zawsze używaj `safe_db_call()`** dla wywołań Supabase (łapie wyjątki, zwraca 503).
- **Zawsze używaj `asyncio.timeout(25)`** na całą funkcję `find_company()`.
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

- **Każda zmiana idzie na nowy branch**, nigdy bezpośrednio na `main`.
- **Schemat nazewnictwa branchy:** `feature/nazwa`, `fix/nazwa`, `refactor/nazwa`.
- **Na `main` tylko po review** — użytkownik sprawdza, akceptuje, dopiero wtedy merge.
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
| **Nie wysyłamy pełnej treści strony do LLM** | Max 6,000 znaków. Reszta to blog i artykuły — niepotrzebne do klasyfikacji. |
| **Nie oceniamy dopasowania kandydata** | Agent tylko weryfikuje: polska strona + usługi AI. Ocena należy do użytkownika. |
| **Nie szukamy ofert pracy ani wymagań** | Szukamy firm. Użytkownik sam ocenia czy aplikować. |
| **Nie budujemy multi-user** | Jeden użytkownik, brak auth, brak izolacji danych między kontami. |

---

## Aktualny status projektu

**Faza: MWS w toku — Dzień 2 ukończony, Dzień 3 w toku**
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

W toku:
- [ ] Dzień 3: Frontend + deployment

---

## Znane problemy i rzeczy do zrobienia

### Krytyczne (przed pierwszą linią kodu)

- [x] **[K1]** Dodać `UNIQUE (domain)` do tabeli `companies` w Supabase
- [x] **[K1]** Używać `ON CONFLICT (domain) DO NOTHING` przy każdym INSERT (`db/client.py`)
- [ ] **[K1]** Disable przycisku w `CompanyCard.tsx` podczas requesta — Dzień 3
- [x] **[K2]** Truncacja treści do 6,000 znaków (`discovery_loop.py`)
- [x] Plik `.env` w `.gitignore`

### Poważne (w trakcie MWS)

- [x] **[P1]** `asyncio.timeout(25)` w `discovery_loop.py`
- [x] **[P2]** `safe_db_call()` wrapper w `db/client.py`
- [x] **[P3]** `call_with_retry()` dla Tavily i Anthropic
- [x] **[P4]** Sprawdzenie pending `presented` na starcie każdego `/find` (`get_recent_presented`)
- [x] **[P4]** Cleanup `presented` > 24h → `skipped` (`cleanup_stale_presented`)
- [ ] **[P5]** Auto-trigger kolejnego `/find` po zapisaniu aplikacji — Dzień 3

### Umiarkowane (po MWS)

- [ ] **[U1]** Fallback na snippet gdy Tavily Extract zwraca < 300 znaków (SPA strony)
- [ ] **[U2]** `normalize_domain()` — stripować `www.` wszędzie
- [ ] **[U3]** CORS konfiguracja w `main.py` (tylko Vercel domain + localhost:3000)
- [ ] **[U3]** Shared secret header `X-API-Key` między frontendem a backendem
- [ ] **[U4]** Paginacja `GET /companies` — `?page=1&limit=20&status=applied`
- [ ] CRM Dashboard (faza 2)
- [ ] Manual Entry Form z OLX/Pracuj.pl (faza 3)
- [ ] LangSmith tracing (env var + weryfikacja)

---

## Zmienne środowiskowe

```env
# Backend (Railway)
ANTHROPIC_API_KEY=
TAVILY_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
API_SECRET=                          # shared secret z frontendem
LANGSMITH_TRACING=true               # opcjonalne
LANGSMITH_API_KEY=                   # opcjonalne
LANGSMITH_PROJECT=crm-job-agent      # opcjonalne

# Frontend (Vercel)
NEXT_PUBLIC_API_URL=                 # URL Railway backend
NEXT_PUBLIC_API_SECRET=              # ten sam co API_SECRET w backendzie
```
