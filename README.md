# CRM Job Agent

Narzędzie do automatycznego wyszukiwania polskich firm AI i śledzenia aplikacji o pracę. Agent szuka firm w Google, klasyfikuje je przez Claude Haiku, a wyniki trafiają do wbudowanego CRM z widokiem kanban i statystykami.

---

## Spis treści

- [Opis i motywacja](#opis-i-motywacja)
- [Wymagania](#wymagania)
- [Instalacja krok po kroku](#instalacja-krok-po-kroku)
- [Przykłady użycia](#przykłady-użycia)
- [Struktura projektu](#struktura-projektu)
- [Technologie i wersje](#technologie-i-wersje)
- [Deployment produkcyjny](#deployment-produkcyjny)
- [FAQ i rozwiązywanie problemów](#faq-i-rozwiązywanie-problemów)
- [Licencja](#licencja)

---

## Opis i motywacja

**Problem:** Ręczne szukanie firm AI przez ChatGPT daje złe linki, angielskie strony i ciągłe powtórki. Notatnik z firmami nie ma linków, dat, stanowisk ani statusów — łatwo się zgubić we własnych aplikacjach.

**Rozwiązanie:** Jedno kliknięcie → agent wyszukuje jedną polską firmę z obszaru AI, której jeszcze nie odwiedziłeś → otwierasz link, decydujesz czy aplikujesz → dane trafiają do CRM → agent szuka kolejnej.

**Jak to działa pod spodem:**

1. Losuje zapytanie z puli 24 fraz branżowych (automatyzacja, ML, NLP, fintech AI…)
2. Wyszukuje przez SerpAPI (Google) — do 5 wyników
3. Filtruje heurystycznie: blokuje portale, artykuły rankingowe, strony `.edu`, domeny anglojęzyczne
4. Weryfikuje przez Claude Haiku — czy firma jest polska i czy sprzedaje AI
5. Normalizuje domenę i sprawdza dedup w bazie
6. Zwraca firmę lub po wyczerpaniu prób zwraca 404

Cały flow trwa 5–25 sekund. Pętla jest w Pythonie — LLM robi tylko klasyfikację.

---

## Wymagania

### Konta zewnętrzne (wymagane)

| Usługa | Do czego | Link |
|---|---|---|
| [Anthropic](https://console.anthropic.com) | Claude Haiku — klasyfikacja firm | `ANTHROPIC_API_KEY` |
| [SerpAPI](https://serpapi.com) | Google Search — wyszukiwanie firm | `SERPAPI_KEY` |
| [Supabase](https://supabase.com) | PostgreSQL — baza danych | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` |

### Konta zewnętrzne (opcjonalne)

| Usługa | Do czego |
|---|---|
| [LangSmith](https://smith.langchain.com) | Monitoring wywołań LLM |
| [Railway](https://railway.app) | Hosting backendu |
| [Vercel](https://vercel.com) | Hosting frontendu |

### Środowisko lokalne

- **Python 3.12+**
- **Node.js 20+** i **npm**
- **Git**

---

## Instalacja krok po kroku

### 1. Sklonuj repozytorium

```bash
git clone <url-repozytorium>
cd crm-job-agent
```

### 2. Utwórz plik `.env`

```bash
cp .env.example .env
```

Uzupełnij wartości w `.env`:

```env
# Backend
ANTHROPIC_API_KEY=sk-ant-...
SERPAPI_KEY=...
SUPABASE_URL=https://twoj-projekt.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
API_SECRET=losowy-tajny-klucz-min-32-znaki
FRONTEND_URL=http://localhost:3000

# Monitoring (opcjonalne)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=ls__...
LANGSMITH_PROJECT=crm-job-agent

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_SECRET=ten-sam-co-API_SECRET
```

> **Uwaga:** `SUPABASE_URL` to tylko domena — `https://xxx.supabase.co` — bez `/rest/v1/`. SDK dodaje ścieżkę samo.
> `SUPABASE_SERVICE_ROLE_KEY` to klucz z zakładki **API → Legacy** w Supabase (nie `anon`).

### 3. Utwórz tabelę w Supabase

W SQL Editor w panelu Supabase wykonaj:

```sql
create table companies (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  url text,
  domain text unique,
  what_they_do text,
  source text not null default 'agent',
  status text not null default 'presented',
  position text,
  salary_expectation text,
  contact_email text,
  notes text,
  reply_received text,
  reply_status text,
  created_at timestamptz not null default now(),
  applied_at timestamptz,
  updated_at timestamptz not null default now()
);
```

> Kolumna `domain` ma `UNIQUE` — zapobiega duplikatom na poziomie bazy.

### 4. Uruchom backend

```bash
cd backend
pip install -r ../requirements.txt
uvicorn main:app --reload --port 8000
```

Backend działa na `http://localhost:8000`. Sprawdź: `http://localhost:8000/` → `{"status": "ok"}`.

### 5. Uruchom frontend

W nowym terminalu:

```bash
cd frontend
npm install
npm run dev
```

Frontend działa na `http://localhost:3000`.

---

## Przykłady użycia

### Przykład 1 — Znalezienie i ocena nowej firmy (podstawowy)

1. Otwórz `http://localhost:3000`
2. Kliknij **"Znajdź firmę"** — przycisk blokuje się na czas wyszukiwania (5–25 sek)
3. Agent zwraca kartę firmy z nazwą, domeną i linkiem do strony głównej
4. Kliknij link → zweryfikuj firmę w przeglądarce
5. Zdecyduj:
   - **"Pomiń"** → firma trafia do `skipped`, agent szuka kolejnej przy następnym kliknięciu
   - **"Wysłałem CV"** → otwiera formularz aplikacji

Bezpośrednio przez API:

```bash
curl -X POST http://localhost:8000/find \
  -H "X-Api-Key: twoj-api-secret"
```

Przykładowa odpowiedź:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Addepto",
  "url": "https://addepto.com",
  "domain": "addepto.com",
  "status": "presented",
  "source": "agent",
  "created_at": "2026-05-17T12:30:00Z"
}
```

---

### Przykład 2 — Pełny cykl aplikacji z zapisem danych (złożony)

**Scenariusz:** Znalazłeś firmę, wysłałeś CV, a tydzień później dostałeś odpowiedź z zaproszeniem na rozmowę.

**Krok 1 — Wyślij CV i zapisz szczegóły:**

```bash
# ID firmy z poprzedniego /find
COMPANY_ID="550e8400-e29b-41d4-a716-446655440000"

curl -X POST "http://localhost:8000/companies/${COMPANY_ID}/apply" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: twoj-api-secret" \
  -d '{
    "position": "ML Engineer",
    "salary_expectation": "18000-22000 PLN",
    "contact_email": "hr@addepto.com",
    "notes": "Rozmawiałem z Tomkiem na LinkedIn przed aplikacją"
  }'
```

W interfejsie: kliknij **"Wysłałem CV"** → wypełnij formularz → kliknij **"Zapisz i szukaj dalej"** — agent automatycznie wyszuka kolejną firmę bez dodatkowego kliknięcia.

**Krok 2 — Zapisz odpowiedź na aplikację:**

```bash
curl -X PATCH "http://localhost:8000/companies/${COMPANY_ID}" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: twoj-api-secret" \
  -d '{
    "reply_status": "interview",
    "reply_received": "2026-05-24"
  }'
```

W interfejsie (CRM Dashboard): znajdź firmę w tabeli → kliknij **"Odpowiedź"** → wybierz status i datę.

**Krok 3 — Podgląd statystyk:**

```bash
curl http://localhost:8000/companies/stats \
  -H "X-Api-Key: twoj-api-secret"
```

```json
{
  "applied": 12,
  "skipped": 47,
  "presented": 1,
  "replied": 3
}
```

**Krok 4 — Ręczne dodanie firmy z OLX/Pracuj.pl:**

Gdy znajdziesz firmę poza agentem — w CRM Dashboard kliknij **"+ Dodaj ręcznie"** lub przez API:

```bash
curl -X POST http://localhost:8000/companies/manual \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: twoj-api-secret" \
  -d '{
    "name": "SoftwareMill",
    "url": "https://softwaremill.com",
    "position": "Senior Scala Developer",
    "notes": "Znaleziona na Pracuj.pl"
  }'
```

---

## Struktura projektu

```
crm-job-agent/
│
├── .env                          # Sekrety lokalne — NIE commitować (jest w .gitignore)
├── .env.example                  # Szablon zmiennych — commitować
├── requirements.txt              # Zależności Pythona
├── Procfile                      # Start command dla Railway
│
├── backend/
│   ├── main.py                   # FastAPI app: CORS, auth middleware, rejestracja routerów
│   │
│   ├── routers/
│   │   ├── discovery.py          # POST /find, /companies/{id}/skip, /companies/{id}/apply
│   │   └── companies.py          # GET /companies, GET /stats, POST /manual, PATCH, DELETE
│   │
│   ├── core/
│   │   ├── discovery_loop.py     # Główna pętla: SerpAPI → filtry heurystyczne → Haiku → dedup → zapis
│   │   ├── query_generator.py    # Losuje jedno z 24 zapytań branżowych (nie używa LLM)
│   │   └── page_verifier.py      # Haiku klasyfikuje: is_polish + is_ai_company (structured output)
│   │
│   ├── db/
│   │   └── client.py             # Supabase async client: wszystkie zapytania SQL, safe_db_call()
│   │
│   └── models/
│       └── schemas.py            # Pydantic modele: CompanyOut, ApplyRequest, PatchCompanyRequest…
│
└── frontend/
    ├── package.json
    ├── next.config.ts            # Turbopack config
    │
    ├── lib/
    │   └── api.ts                # Klient HTTP: apiFetch() z X-Api-Key header, wszystkie endpointy
    │
    ├── app/
    │   ├── layout.tsx            # Root layout: nawigacja Odkrywanie / CRM, font Geist
    │   ├── page.tsx              # Widok Discovery: przycisk Znajdź firmę, karta, formularz
    │   └── crm/
    │       └── page.tsx          # CRM Dashboard: tabela, filtry, stats, modale
    │
    └── components/
        ├── CompanyCard.tsx       # Karta znalezionej firmy + przyciski Pomiń / Wysłałem CV
        ├── ApplicationForm.tsx   # Formularz: stanowisko, oczekiwania, email, notatki
        ├── CRMTable.tsx          # Tabela z paginacją (20/strona), sortowaniem, linkami
        ├── ManualEntryModal.tsx  # Modal ręcznego dodawania firmy z OLX/Pracuj.pl
        ├── ReplyModal.tsx        # Modal zapisu odpowiedzi: status + data
        └── CompanyEditModal.tsx  # Modal edycji i usuwania firmy z CRM
```

---

## Technologie i wersje

### Backend

| Technologia | Wersja | Rola |
|---|---|---|
| Python | 3.12 | Runtime |
| FastAPI | ≥0.111.0 | HTTP framework, walidacja, CORS |
| Uvicorn | ≥0.30.0 | ASGI server |
| LangChain | ≥0.2.0 | Orkiestracja wywołań LLM |
| langchain-anthropic | ≥0.1.0 | Wrapper Claude Haiku (structured output) |
| Claude Haiku 4.5 | `claude-haiku-4-5-20251001` | Klasyfikacja firm (is_polish, is_ai_company) |
| google-search-results | ≥2.4.2 | SerpAPI — wyszukiwarka Google |
| httpx | ≥0.27.0 | Async HTTP — pobieranie treści stron |
| BeautifulSoup4 | ≥4.12.0 | Parsowanie HTML |
| supabase-py | ≥2.5.0 | Async klient Supabase/PostgreSQL |
| Pydantic | ≥2.0.0 | Walidacja danych |
| python-dotenv | ≥1.0.0 | Ładowanie `.env` |

### Frontend

| Technologia | Wersja | Rola |
|---|---|---|
| Next.js | 16.2.6 | Framework (App Router, Turbopack) |
| React | 19.2.4 | UI |
| TypeScript | ^5 | Typowanie |
| Tailwind CSS | ^4 | Style |

### Infrastruktura

| Usługa | Rola |
|---|---|
| Railway | Hosting backendu (Python/FastAPI) |
| Vercel | Hosting frontendu (Next.js) |
| Supabase | PostgreSQL (managed) |
| SerpAPI | Google Search API |
| Anthropic API | Claude Haiku |
| LangSmith | Monitoring LLM (opcjonalne) |

---

## Deployment produkcyjny

### Backend na Railway

1. Utwórz nowy projekt na [railway.app](https://railway.app) i połącz z repozytorium.

2. Railway automatycznie wykryje `Procfile`:
   ```
   web: cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

3. W panelu Railway → **Variables** dodaj wszystkie zmienne:
   ```
   ANTHROPIC_API_KEY=...
   SERPAPI_KEY=...
   SUPABASE_URL=https://xxx.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=eyJ...
   API_SECRET=losowy-tajny-klucz
   FRONTEND_URL=https://crm-job-agent.vercel.app
   ```

4. Po deploymencie sprawdź zdrowie: `https://<twoj-projekt>.up.railway.app/`

### Frontend na Vercel

1. Zaimportuj repozytorium na [vercel.com](https://vercel.com).

2. Ustaw **Root Directory** na `frontend`.

3. W **Environment Variables** dodaj:
   ```
   NEXT_PUBLIC_API_URL=https://<twoj-projekt>.up.railway.app
   NEXT_PUBLIC_API_SECRET=ten-sam-co-API_SECRET-na-Railway
   ```

4. Deploy — Vercel automatycznie buduje Next.js.

### Kolejność deploymentu

```
Supabase (schema) → Railway (backend) → Vercel (frontend)
```

Najpierw baza, potem backend, na końcu frontend — bo frontend potrzebuje URL backendu.

---

## FAQ i rozwiązywanie problemów

### Agent zwraca 404 "Nie znaleziono nowych firm"

Agent zużył jeden attempt (MAX_ATTEMPTS=1) i nie znalazł firmy spełniającej kryteria. Przyczyny:

- Losowe zapytanie trafiło na artykuły rankingowe — kliknij ponownie
- SerpAPI osiągnął limit miesięcznych zapytań — sprawdź dashboard SerpAPI
- Wszystkie wyniki z danej niszy są już w bazie (`skipped`/`presented`) — przy kolejnym kliknięciu agent wylosuje inną niszę

**Fix:** Kliknij "Znajdź firmę" jeszcze raz. Zapytania są losowane, następne może zwrócić inną niszę.

---

### Backend zwraca 503 "Problem z bazą danych"

```
HTTP 503 — Problem z bazą danych. Spróbuj ponownie.
```

Supabase jest chwilowo niedostępny lub klucze są błędne.

**Sprawdź:**
1. `SUPABASE_URL` — tylko domena `https://xxx.supabase.co`, bez `/rest/v1/`
2. `SUPABASE_SERVICE_ROLE_KEY` — klucz `service_role` z zakładki **API → Legacy** (nie `anon`)
3. Status Supabase: [status.supabase.com](https://status.supabase.com)

---

### Backend zwraca 503 "Wyszukiwanie trwa za długo"

Discovery loop ma timeout 55 sekund. Jeśli przekroczy — Railway zabija request.

**Przyczyny:**
- SerpAPI odpowiada bardzo wolno
- Fetch strony (httpx) zawiesił się na złym hoście

**Fix:** Kliknij ponownie. Jeśli problem powtarza się — sprawdź logi w Railway (zakładka Logs).

---

### CORS error w przeglądarce

```
Access to fetch at 'http://localhost:8000' has been blocked by CORS policy
```

Backend nie ma skonfigurowanego `FRONTEND_URL`.

**Fix lokalny:** Upewnij się, że w `.env` masz:
```
FRONTEND_URL=http://localhost:3000
```
i zrestartuj backend.

**Fix produkcyjny:** W Railway → Variables dodaj:
```
FRONTEND_URL=https://twoja-domena.vercel.app
```

---

### Firma pojawia się ponownie po "Pomiń"

Dedup działa po znormalizowanej domenie. Firma może wracać jeśli:
- Domena ma subdomeny (`www.firma.pl` vs `firma.pl`) — po poprawce kodu to nie powinno się zdarzać
- Firma była w statusie `presented` starszym niż 24h — po następnym `/find` zostanie automatycznie przeniesiona do `skipped`

---

### Klucz API jest odrzucany (401)

```
HTTP 401 — Nieprawidłowy lub brakujący klucz API.
```

Frontend wysyła inny `X-Api-Key` niż backend oczekuje.

**Sprawdź:**
- `API_SECRET` w Railway i `NEXT_PUBLIC_API_SECRET` w Vercel muszą być **identyczne**
- Po zmianie zmiennych na Vercel wymagany jest redeploy

---

### `SUPABASE_SERVICE_KEY` vs `SUPABASE_SERVICE_ROLE_KEY`

Zmienna nazywa się **`SUPABASE_SERVICE_ROLE_KEY`** (z `_ROLE_`). Bez `_ROLE_` backend nie połączy się z bazą.

---

### Frontend nie widzi nowych zmiennych środowiskowych

Zmienne `NEXT_PUBLIC_*` są wbudowywane w bundle podczas budowania. Sama zmiana zmiennej w Vercel nie wystarczy — wymagany jest **nowy deployment** (Vercel → Redeploy).

---

### Haiku klasyfikuje polską firmę AI jako `is_ai_company: false`

Model ocenia tylko pierwsze 2000 znaków treści strony. Jeśli firma ma landing page z samymi zdjęciami i mało tekstu — snippet z Google może być za krótki do klasyfikacji.

**Workaround:** Dodaj firmę ręcznie przez "Dodaj ręcznie" w CRM Dashboard.

---

## Licencja

**All Rights Reserved.**

Copyright © 2026 Konrad Pochwała. Wszelkie prawa zastrzeżone.

Kod źródłowy tego projektu jest prywatny. Zakazuje się kopiowania, modyfikowania, dystrybucji, sublicencjonowania lub sprzedaży całości lub części kodu bez pisemnej zgody autora.
