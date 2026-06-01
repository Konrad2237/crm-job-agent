# Architektura techniczna — CRM Job Agent

---

## Stack technologiczny

| Warstwa | Technologia | Hosting |
|---|---|---|
| Frontend | Next.js (App Router) + Tailwind CSS | Vercel |
| Backend | Python 3.12 + FastAPI | Railway |
| Baza danych | PostgreSQL (Supabase) | Supabase |
| LLM framework | LangChain (`langchain`, `langchain-anthropic`, `langchain-community`) | — |
| LLM model | Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) | Anthropic API |
| Wyszukiwanie | Tavily przez `TavilySearchResults` (langchain-community) | zewnętrzne |
| Monitoring | LangSmith (natywna integracja z LangChain) | zewnętrzne |

**Dlaczego LangChain:**
- `TavilySearchResults` — gotowa integracja z Tavily, zero konfiguracji
- `.with_structured_output(PydanticModel)` — page verifier zwraca typowany obiekt bez ręcznego parsowania JSON
- LangSmith działa automatycznie — każde wywołanie LLM pojawia się w dashboardzie bez żadnego extra kodu
- Jedna biblioteka zamiast osobnych SDK dla każdego serwisu

**Dlaczego nie agentic loop z LangChain:**
Poprzedni projekt skończył się 800k tokenów — to efekt pętli gdzie LLM sam decydował kiedy skończyć (AgentExecutor bez limitu). Problem był w architekturze, nie w LangChain.
Tutaj LLM robi TYLKO dwie rzeczy: generuje zapytanie i klasyfikuje stronę. Cała logika pętli `for attempt in range(3)` jest w Pythonie — LangChain to tylko wygodne opakowanie na wywołanie modelu.

---

## Struktura katalogów

```
crm-job-agent/
├── backend/
│   ├── main.py                     # FastAPI app, CORS, router registration
│   ├── routers/
│   │   ├── discovery.py            # POST /find, POST /companies/{id}/skip, POST /companies/{id}/apply
│   │   └── companies.py            # GET /companies, POST /companies/manual, PATCH /companies/{id}
│   ├── core/
│   │   ├── discovery_loop.py       # główna pętla szukania (Python, nie LLM)
│   │   ├── query_generator.py      # generuje zapytanie Tavily (Haiku)
│   │   └── page_verifier.py        # klasyfikuje stronę: polska + AI? (Haiku)
│   ├── db/
│   │   └── client.py               # Supabase client + wszystkie zapytania SQL
│   └── models/
│       └── schemas.py              # Pydantic modele request/response
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx                # widok Discovery (główny)
│   │   └── crm/
│   │       └── page.tsx            # CRM Dashboard
│   └── components/
│       ├── CompanyCard.tsx         # karta znalezionej firmy + przyciski decyzji
│       ├── ApplicationForm.tsx     # formularz danych po kliknięciu "wysłałem CV"
│       ├── CRMTable.tsx            # tabela wszystkich firm
│       └── ManualEntryModal.tsx    # modal ręcznego dodawania
│
├── .env                            # lokalne zmienne środowiskowe
├── .env.example                    # szablon bez sekretów
└── requirements.txt
```

---

## API — endpointy

### Discovery

| Metoda | Endpoint | Opis |
|---|---|---|
| `POST` | `/find` | Odpala discovery loop, zwraca jedną firmę |
| `POST` | `/companies/{id}/skip` | Oznacza firmę jako pominięta |
| `POST` | `/companies/{id}/apply` | Zapisuje dane aplikacji |

### CRM

| Metoda | Endpoint | Opis |
|---|---|---|
| `GET` | `/companies` | Lista firm, opcjonalny param `?status=applied` |
| `POST` | `/companies/manual` | Ręczne dodanie firmy (OLX, Pracuj.pl) |
| `PATCH` | `/companies/{id}` | Aktualizacja dowolnego pola (status, notatki, odpowiedź) |

---

## Discovery Loop — szczegółowy przepływ

Kluczowy mechanizm systemu. Cała logika w Pythonie — LLM wywoływany tylko 2 razy na znalezioną firmę.

```
POST /find
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  discovery_loop.py                                          │
│                                                             │
│  max_attempts = 3  (max ile razy generujemy nowe zapytanie) │
│                                                             │
│  for attempt in range(max_attempts):                        │
│      │                                                      │
│      ▼                                                      │
│  [1] query_generator.py (Haiku ~100 tokenów)                │
│      → generuje polskie zapytanie do Tavily                 │
│      → dostaje kontekst: poprzednie zapytania (żeby się     │
│        nie powtarzać)                                       │
│      │                                                      │
│      ▼                                                      │
│  [2] Tavily Search API (max_results=5)                      │
│      → zwraca listę URL-i z tytułami i snippetami           │
│      │                                                      │
│      for url in results:                                    │
│          │                                                  │
│          ▼                                                  │
│      [3] Dedup check (zapytanie SQL, zero AI)               │
│          → SELECT EXISTS(SELECT 1 FROM companies            │
│            WHERE domain = $1)                               │
│          → jeśli tak: continue (następny URL)               │
│          │                                                  │
│          ▼ (nowy URL)                                       │
│      [4] Tavily Extract API                                 │
│          → pobiera treść strony                             │
│          │                                                  │
│          ▼                                                  │
│      [5] page_verifier.py (Haiku ~800 tokenów)              │
│          → czy strona po polsku? (tak/nie)                  │
│          → czy firma zajmuje się AI? (tak/nie)              │
│          → jeśli tak: krótki opis (chatboty, agenci itp)    │
│          → jeśli nie: continue (następny URL)               │
│          │                                                  │
│          ▼ (pass)                                           │
│      [6] Zapisz do DB ze statusem "presented"               │
│          → return {id, name, url, what_they_do}             │
│                                                             │
│  return None  ← jeśli po 3 zapytaniach nic nie znaleziono  │
└─────────────────────────────────────────────────────────────┘
```

**Szacunek kosztów tokenów na jedno kliknięcie "Znajdź firmę":**

| Operacja | Tokeny | Koszt (Haiku 4.5) |
|---|---|---|
| 3× generowanie zapytania | ~300 tokenów | ~$0.0003 |
| maks. 15× weryfikacja strony | ~12,000 tokenów | ~$0.012 |
| **Worst case łącznie** | **~12,300 tokenów** | **~$0.012** |

Przy 100 kliknięciach/miesiąc = ~$1.20. Tavily: ~15-45 wywołań/kliknięcie × 100 = maks. 4500 kredytów/miesiąc (plan Starter = 10,000/mies za $30 lub Free = 1000/mies).

---

## Schemat bazy danych

### Tabela: `companies`

```sql
CREATE TABLE companies (
    id               UUID        DEFAULT gen_random_uuid() PRIMARY KEY,

    -- dane podstawowe (zawsze wypełniane przez agenta lub ręcznie)
    name             TEXT        NOT NULL,
    url              TEXT        NOT NULL,
    domain           TEXT        NOT NULL,   -- wyekstrahowana domena, używana do dedup

    -- opis działalności (wypełnia agent przy znalezieniu)
    what_they_do     TEXT,                   -- np. "chatboty, agenci AI, automatyzacje"

    -- źródło i status
    source           TEXT        NOT NULL DEFAULT 'agent',
    -- wartości source: 'agent' | 'manual'

    status           TEXT        NOT NULL DEFAULT 'presented',
    -- wartości status:
    --   'presented'  → agent znalazł, użytkownik jeszcze nie zdecydował
    --   'skipped'    → użytkownik pominął (nie wysłał CV)
    --   'applied'    → użytkownik wysłał CV
    --   'manual'     → dodane ręcznie z OLX/Pracuj.pl

    -- dane aplikacji (wypełnia użytkownik po kliknięciu "wysłałem CV")
    position         TEXT,                   -- stanowisko lub 'talent_pool'
    salary_expectation TEXT,                 -- oczekiwane wynagrodzenie które podał
    contact_email    TEXT,                   -- email do którego pisał
    notes            TEXT,                   -- wolne notatki

    -- follow-up
    reply_received   TEXT,                   -- co odpisali (treść lub streszczenie)
    reply_status     TEXT,                   -- 'no_reply' | 'positive' | 'negative' | 'interview'

    -- timestampy
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    applied_at       TIMESTAMPTZ,            -- kiedy wysłał CV
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);
```

### Indeksy

```sql
-- dedup lookup (często wywoływane w discovery loop)
CREATE INDEX idx_companies_domain ON companies(domain);

-- filtrowanie w dashboardzie po statusie
CREATE INDEX idx_companies_status ON companies(status);

-- sortowanie po dacie
CREATE INDEX idx_companies_created_at ON companies(created_at DESC);
```

### Auto-update `updated_at`

```sql
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER companies_updated_at
BEFORE UPDATE ON companies
FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

### Diagram tabeli

```
┌──────────────────────────────────────────────────┐
│                    companies                      │
├──────────────────┬───────────┬───────────────────┤
│ id               │ uuid      │ PK                 │
│ name             │ text      │ NOT NULL           │
│ url              │ text      │ NOT NULL           │
│ domain           │ text      │ NOT NULL, indexed  │
│ what_they_do     │ text      │                    │
├──────────────────┼───────────┼───────────────────┤
│ source           │ text      │ agent | manual     │
│ status           │ text      │ indexed            │
│                  │           │ presented          │
│                  │           │ skipped            │
│                  │           │ applied            │
│                  │           │ manual             │
├──────────────────┼───────────┼───────────────────┤
│ position         │ text      │ nullable           │
│ salary_expectation│ text     │ nullable           │
│ contact_email    │ text      │ nullable           │
│ notes            │ text      │ nullable           │
├──────────────────┼───────────┼───────────────────┤
│ reply_received   │ text      │ nullable           │
│ reply_status     │ text      │ nullable           │
├──────────────────┼───────────┼───────────────────┤
│ created_at       │ timestamptz│ DEFAULT NOW()     │
│ applied_at       │ timestamptz│ nullable          │
│ updated_at       │ timestamptz│ auto-trigger      │
└──────────────────┴───────────┴───────────────────┘
```

---

## Widoki frontendu

### Widok 1: Discovery (strona główna `/`)

```
┌─────────────────────────────────────────┐
│  CRM Job Agent              [CRM →]     │
├─────────────────────────────────────────┤
│                                         │
│         [  Znajdź firmę  ]              │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  Nazwa firmy                     │  │
│  │  🔗 link do strony               │  │
│  │  Czym się zajmuje: chatboty,     │  │
│  │  agenci AI, automatyzacje        │  │
│  └──────────────────────────────────┘  │
│                                         │
│  [ Wysłałem CV ]    [ Pomiń ]           │
│                                         │
│  ▼ po kliknięciu "Wysłałem CV"          │
│  ┌──────────────────────────────────┐  │
│  │  Stanowisko: ____________        │  │
│  │  Wynagrodzenie: __________       │  │
│  │  Email: __________________       │  │
│  │  Notatki: ________________       │  │
│  │                  [ Zapisz ]      │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### Widok 2: CRM Dashboard (`/crm`)

```
┌──────────────────────────────────────────────────────────────┐
│  CRM Dashboard             [+ Dodaj ręcznie]   [← Discovery] │
├──────────────────────────────────────────────────────────────┤
│  Filtr: [Wszystkie ▼]  [applied ▼]  [skipped ▼]             │
├──────────┬──────────┬──────────┬────────────┬───────────────┤
│ Firma    │ Link     │ Usługi   │ Stanowisko │ Status        │
├──────────┼──────────┼──────────┼────────────┼───────────────┤
│ Acme AI  │ 🔗       │ agenci   │ AI Dev     │ [applied ▼]   │
│ Bot Corp │ 🔗       │ chatboty │ talent pool│ [interview ▼] │
│ RAG Sp.  │ 🔗       │ RAG, LLM │ —          │ [skipped ▼]   │
└──────────┴──────────┴──────────┴────────────┴───────────────┘
```

---

## Zmienne środowiskowe

```env
# LLM
ANTHROPIC_API_KEY=

# Wyszukiwanie
TAVILY_API_KEY=

# Baza danych
SUPABASE_URL=
SUPABASE_SERVICE_KEY=

# Monitoring (opcjonalne na MVP)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=crm-job-agent

# Frontend (Vercel)
NEXT_PUBLIC_API_URL=https://twoj-backend.railway.app
```

---

## Kolejność budowania (MVP → rozszerzenia)

### Faza 1 — rdzeń (ścieżka krytyczna)
1. Supabase: utwórz tabelę `companies`
2. Backend: `db/client.py` — zapytania dedup + zapis
3. Backend: `query_generator.py` — generowanie zapytań (Haiku)
4. Backend: `page_verifier.py` — klasyfikacja strony (Haiku)
5. Backend: `discovery_loop.py` — pętla Python
6. Backend: endpoint `POST /find` + `POST /companies/{id}/skip` + `POST /companies/{id}/apply`
7. Frontend: widok Discovery z przyciskiem i kartą firmy

### Faza 2 — CRM
8. Backend: `GET /companies` + `PATCH /companies/{id}`
9. Frontend: CRM Dashboard z tabelą i filtrowaniem

### Faza 3 — rozszerzenia
10. Backend + Frontend: `POST /companies/manual` + modal ręcznego dodawania
11. LangSmith tracing (tylko env var + sprawdzenie dashboardu)

---

## Znane luki i wymagane poprawki

Sekcja dodana po stress teście i testach scenariuszowych. Każda luka ma priorytet i konkretny fix.

---

### KRYTYCZNE — zrobić przed pierwszą linią kodu produkcyjnego

**[K1] Race condition przy podwójnym kliknięciu → duplikaty w bazie**

Źródło: Scenariusz SC2. Dwa równoległe `POST /find` sprawdzają dedup jednocześnie, oba widzą domain jako nową, oba zapisują ten sam rekord.

Fix 1 — baza danych:
```sql
-- Dodać do CREATE TABLE companies:
CONSTRAINT unique_domain UNIQUE (domain)

-- W db/client.py używać:
INSERT INTO companies (...) ON CONFLICT (domain) DO NOTHING
RETURNING *
-- Jeśli zwróci pusty wynik → pobierz istniejący rekord
```

Fix 2 — frontend:
```typescript
// CompanyCard.tsx — wyłącz przycisk podczas trwającego requesta
const [isLoading, setIsLoading] = useState(false)
const handleFind = async () => {
  if (isLoading) return
  setIsLoading(true)
  await postFind()
  setIsLoading(false)
}
```

---

**[K2] Eksplozja tokenów przy dużych stronach**

Źródło: Scenariusz SC4. Strona z blogiem (87k tokenów) kosztuje $0.056 vs normalne $0.001 — 56× drożej. Kilka takich stron = przekroczenie miesięcznego budżetu.

Fix — truncacja w `page_verifier.py` przed wywołaniem Haiku:
```python
MAX_CONTENT_CHARS = 6_000

def prepare_content(raw_content: str) -> str:
    if len(raw_content) > MAX_CONTENT_CHARS:
        return raw_content[:MAX_CONTENT_CHARS]
    return raw_content
```

Pierwsze 6,000 znaków zawiera hero, usługi i "o nas" — wszystko potrzebne do klasyfikacji. Blog i artykuły są za tym progiem.

---

### POWAŻNE — zrobić w trakcie MWS (dni 2–3)

**[P1] Brak globalnego timeout na discovery loop**

Źródło: Stress test. Przy Anthropic API down: 15 URL-i × retry 2× × 2 sek = 60 sekund spinnera. Railway zerwie połączenie po 30 sek i tak → błąd 502.

Fix w `discovery_loop.py`:
```python
import asyncio

async def find_company():
    try:
        async with asyncio.timeout(25):  # twardy limit 25 sekund
            # ... cała logika pętli
    except asyncio.TimeoutError:
        raise HTTPException(503, "Wyszukiwanie trwa za długo. Spróbuj ponownie.")
```

---

**[P2] Brak obsługi błędów bazy danych**

Źródło: Stress test. Żaden błąd Supabase nie jest obsługiwany — każdy rzuca Python traceback jako HTTP 500.

Fix — wrapper w `db/client.py`:
```python
from fastapi import HTTPException

async def safe_db_call(coro):
    try:
        return await coro
    except Exception as e:
        # zaloguj szczegóły wewnętrznie
        raise HTTPException(503, "Problem z bazą danych. Spróbuj ponownie.")

# Użycie:
result = await safe_db_call(supabase.table("companies").select(...).execute())
```

---

**[P3] Brak retry dla Tavily API**

Źródło: Stress test. ADR-003 definiuje retry tylko dla Anthropic. Tavily error = nieobsłużony wyjątek.

Fix — wspólna funkcja retry dla wszystkich zewnętrznych wywołań:
```python
import asyncio

async def call_with_retry(coro_fn, retries=2, delay=2.0):
    for attempt in range(retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt == retries:
                raise
            await asyncio.sleep(delay)

# Użycie dla Tavily i Anthropic jednakowo
result = await call_with_retry(lambda: tavily.search(query))
```

---

**[P4] Status `presented` nigdy nie wygasa**

Źródło: Scenariusz SC5. Zamknięcie przeglądarki przed decyzją zostawia firmę w statusie `presented` na zawsze. Dedup traktuje ją jak "już widzianą" — firma znika bez śladu.

Skala: 3–4 przerwania dziennie × 20 dni = 60–80 firm straconych miesięcznie.

Fix w `discovery_loop.py` — sprawdź pending przed szukaniem nowej:
```python
async def find_company():
    # Najpierw: czy jest firma z niepodjętą decyzją z ostatnich 24h?
    pending = await db.get_recent_presented()  # WHERE status='presented' AND created_at > NOW()-24h
    if pending:
        return pending  # pokaż ją ponownie zamiast szukać nowej

    # Wyczyść stare presented (> 24h) → zmień na skipped
    await db.cleanup_stale_presented()  # WHERE status='presented' AND created_at < NOW()-24h → UPDATE status='skipped'

    # Normalny discovery flow
    for attempt in range(MAX_ATTEMPTS):
        ...
```

---

**[P5] Niezdefiniowany flow po zapisaniu aplikacji**

Źródło: Scenariusz SC1. Po `POST /apply` + kliknięciu "Zapisz" frontend nie wie co zrobić.

Decyzja: po udanym zapisie automatycznie wywołaj kolejne `POST /find` — naturalny rytm pracy bez dodatkowego kliknięcia.

```typescript
// ApplicationForm.tsx
const handleSave = async () => {
  await postApply(companyId, formData)
  // nie czekaj na potwierdzenie — od razu szukaj kolejnej
  onSaveComplete()  // callback do Company Presenter → triggeruje POST /find
}
```

---

### UMIARKOWANE — można zrobić po MWS

**[U1] Brak fallbacku na snippet gdy Extract zawodzi**

Źródło: Scenariusz SC3. Strony SPA (React/Vue) zwracają pusty HTML. Firma jest odrzucana mimo że snippet z Tavily Search mógłby wystarczyć do klasyfikacji.

Fix w `discovery_loop.py`:
```python
extracted = await tavily.extract(url)

# Fallback: jeśli extract za krótki, użyj snippetu z wyników search
if len(extracted) < 300:
    extracted = search_result.snippet  # zawsze dostępny, 200-400 słów

if len(extracted) < 50:
    continue  # naprawdę nic nie ma → skip
```

---

**[U2] Normalizacja domeny dla dedup**

Źródło: Stress test. `www.firma.pl` i `firma.pl` to różne stringi → ta sama firma przejdzie dedup dwa razy.

Fix — funkcja normalizacji wywoływana przy każdym zapisie i każdym dedup checku:
```python
from urllib.parse import urlparse

def normalize_domain(url: str) -> str:
    domain = urlparse(url).netloc.lower()
    return domain.removeprefix("www.")

# Używać wszędzie zamiast surowego domain
```

---

**[U3] CORS i podstawowe zabezpieczenie backendu**

Źródło: Stress test. Dwa problemy:

Problem A — CORS: bez konfiguracji backend albo blokuje frontend albo akceptuje requesty z każdej domeny.
```python
# main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://twoj-frontend.vercel.app",
        "http://localhost:3000",  # dev
    ],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)
```

Problem B — Railway URL widoczny w DevTools przez `NEXT_PUBLIC_API_URL`. Prosty shared secret:
```typescript
// Frontend — każdy request
headers: { "X-API-Key": process.env.NEXT_PUBLIC_API_SECRET }
```
```python
# Backend — middleware weryfikuje
API_SECRET = os.getenv("API_SECRET")
if request.headers.get("X-API-Key") != API_SECRET:
    raise HTTPException(401)
```

---

**[U4] Paginacja `GET /companies`**

Źródło: Stress test. Bez paginacji przy 500+ rekordach frontend crashnie.

Fix — endpoint i SQL:
```python
# GET /companies?page=1&limit=20&status=applied
@router.get("/companies")
async def list_companies(page: int = 1, limit: int = 20, status: str = None):
    offset = (page - 1) * limit
    return await db.get_companies(status=status, limit=limit, offset=offset)
```

---

### Zaktualizowany schemat bazy danych

Poprawiony względem pierwotnej wersji — dodany UNIQUE constraint:

```sql
CREATE TABLE companies (
    id                  UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    name                TEXT        NOT NULL,
    url                 TEXT        NOT NULL,
    domain              TEXT        NOT NULL,
    what_they_do        TEXT,
    source              TEXT        NOT NULL DEFAULT 'agent',
    status              TEXT        NOT NULL DEFAULT 'presented',
    position            TEXT,
    salary_expectation  TEXT,
    contact_email       TEXT,
    notes               TEXT,
    reply_received      TEXT,
    reply_status        TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    applied_at          TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    -- DODANE po stress teście i testach scenariuszowych:
    CONSTRAINT unique_domain UNIQUE (domain)  -- fix [K1]: race condition
);

CREATE INDEX idx_companies_domain     ON companies(domain);
CREATE INDEX idx_companies_status     ON companies(status);
CREATE INDEX idx_companies_created_at ON companies(created_at DESC);
```

---

### Zaktualizowany discovery loop (z wszystkimi fixami)

```
POST /find
    │
    ▼
[0] Sprawdź pending (fix P4)
    SELECT * FROM companies WHERE status='presented' AND created_at > NOW()-24h
    Jeśli jest → zwróć ją, nie szukaj nowej
    Wyczyść stale presented > 24h → status='skipped'
    │
    ▼
asyncio.timeout(25) ← fix P1
    │
    ▼
for attempt in range(3):
    │
    ▼
    [1] Query Generator (Haiku)
    │
    ▼
    [2] call_with_retry(tavily.search) ← fix P3
    │
    for url in results:
        │
        ▼
        [3] normalize_domain(url) ← fix U2
        [4] Dedup check (safe_db_call) ← fix P2
            → seen: continue
        │
        ▼
        [5] call_with_retry(tavily.extract) ← fix P3
            → fallback na snippet jeśli < 300 znaków ← fix U1
        │
        ▼
        [6] prepare_content(truncate 6000 znaków) ← fix K2
        [7] Page Verifier (Haiku)
            → fail: continue
        │
        ▼
        [8] safe_db_call(INSERT ON CONFLICT DO NOTHING) ← fix K1, P2
        [9] return company
    │
    ▼
return 404 {"found": false, "message": "Nie znaleziono nowych firm. Spróbuj za chwilę."}
```

---

### Podsumowanie: co zmienia się względem pierwotnej architektury

| Zmiana | Plik | Priorytet |
|---|---|---|
| `UNIQUE (domain)` w tabeli | Supabase SQL | Krytyczny |
| `ON CONFLICT DO NOTHING` przy INSERT | `db/client.py` | Krytyczny |
| Truncacja treści do 6,000 znaków | `page_verifier.py` | Krytyczny |
| `asyncio.timeout(25)` na loop | `discovery_loop.py` | Poważny |
| `safe_db_call()` wrapper | `db/client.py` | Poważny |
| `call_with_retry()` dla Tavily i Anthropic | `discovery_loop.py` | Poważny |
| Sprawdzenie pending presented na starcie | `discovery_loop.py` | Poważny |
| Auto-find po zapisaniu aplikacji | `ApplicationForm.tsx` | Poważny |
| Disable przycisku podczas requesta | `CompanyCard.tsx` | Poważny |
| Fallback na snippet | `discovery_loop.py` | Umiarkowany |
| `normalize_domain()` | `db/client.py` | Umiarkowany |
| CORS konfiguracja | `main.py` | Umiarkowany |
| Shared secret header | `main.py` + frontend | Umiarkowany |
| Paginacja `GET /companies` | `routers/companies.py` | Umiarkowany |
