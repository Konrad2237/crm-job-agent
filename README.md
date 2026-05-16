# CRM Job Agent

**[→ Otwórz aplikację](https://crm-job-agent.vercel.app)**

Narzędzie do automatycznego znajdowania polskich firm AI i śledzenia aplikacji o pracę.

Agent wyszukuje polskie firmy zajmujące się sztuczną inteligencją, prezentuje je jedną po drugiej i pozwala śledzić cały proces aplikowania — od pierwszego kontaktu po otrzymanie odpowiedzi. Eliminuje ręczne szukanie firm przez ChatGPT (złe linki, powtórki, brak kontekstu) i zastępuje chaotyczny notatnik CRM-em z datami, statusami i historią.

---

## Spis treści

- [Funkcjonalności](#funkcjonalności)
- [Wymagania](#wymagania)
- [Instalacja](#instalacja)
- [Użycie](#użycie)
- [Struktura projektu](#struktura-projektu)
- [Technologie](#technologie)
- [Deployment](#deployment)

---

## Funkcjonalności

- **Automatyczne znajdowanie firm** — jeden klik, agent wyszukuje polską firmę AI której jeszcze nie odwiedziłeś
- **Filtrowanie śmieci** — odrzuca artykuły, portale newsowe, firmy zagraniczne i agencje marketingowe zanim trafią do klasyfikacji LLM
- **Weryfikacja przez Haiku** — Claude Haiku ocenia czy firma naprawdę jest polska i czy sprzedaje AI (nie tylko "używa AI wewnętrznie")
- **Decyzje przy każdej firmie** — Pomiń lub Wysłałem CV, z możliwością zapisania stanowiska, widełek i emaila kontaktowego
- **CRM Dashboard** — tabela wszystkich firm z filtrowaniem po statusie, wyszukiwaniem i sortowaniem
- **Śledzenie odpowiedzi** — oznaczanie czy firma odpisała i z jakim wynikiem
- **Ręczne dodawanie** — wpisz firmę z OLX/Pracuj.pl ręcznie do CRM
- **Statystyki** — liczniki applied / skipped / presented / replied

---

## Wymagania

- Python 3.12+
- Node.js 18+
- Konta i klucze API:
  - [Anthropic](https://console.anthropic.com) — klucz do Claude Haiku
  - [SerpAPI](https://serpapi.com) — klucz do wyszukiwania Google (250 zapytań/mies. za darmo = ~250 kliknięć "Znajdź firmę"; wystarczy na codzienny użytek)
  - [Supabase](https://supabase.com) — projekt z bazą PostgreSQL (darmowy tier wystarczy)

---

## Instalacja

### 1. Sklonuj repozytorium

```bash
git clone https://github.com/Konrad2237/crm-job-agent.git
cd crm-job-agent
```

### 2. Skonfiguruj zmienne środowiskowe

```bash
cp .env.example .env
```

Uzupełnij `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
SERPAPI_KEY=...
SUPABASE_URL=https://twoj-projekt.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
API_SECRET=dowolny-losowy-string
```

### 3. Backend (FastAPI)

```bash
pip install -r requirements.txt
cd backend
uvicorn main:app --reload
```

Backend działa na `http://localhost:8000`.

### 4. Frontend (Next.js)

```bash
cd frontend
npm install
```

Utwórz `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_SECRET=ten-sam-co-API_SECRET-w-backend
```

```bash
npm run dev
```

Frontend działa na `http://localhost:3000`.

### 5. Baza danych

W Supabase wykonaj migrację:

```sql
CREATE TABLE companies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  url TEXT,
  domain TEXT UNIQUE NOT NULL,
  source TEXT DEFAULT 'agent',
  status TEXT DEFAULT 'presented',
  position TEXT,
  salary_expectation TEXT,
  contact_email TEXT,
  notes TEXT,
  reply_received BOOLEAN DEFAULT FALSE,
  reply_status TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  applied_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trigger aktualizujący updated_at przy każdym UPDATE
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER companies_updated_at
BEFORE UPDATE ON companies
FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

---

## Użycie

### Znajdowanie firm

1. Otwórz `http://localhost:3000`
2. Kliknij **Znajdź firmę** — agent wyszukuje jedną polską firmę AI
3. Przejrzyj firmę:
   - **Pomiń** — firma nie pasuje; zostaje zapisana jako "widziana" i nie wróci w kolejnych wyszukaniach. Kliknij "Znajdź firmę" ponownie żeby szukać dalej.
   - **Wysłałem CV** — otwiera formularz z polami na stanowisko, widełki, email, notatki. Po zapisaniu agent **automatycznie** szuka kolejnej firmy.

> Jeśli agent nie znajdzie firmy spełniającej kryteria, wyświetli komunikat "Nie znaleziono". Kliknij "Znajdź firmę" ponownie — każde wyszukanie losuje inne zapytanie.

### CRM Dashboard

Wejdź w zakładkę **CRM** żeby zobaczyć wszystkie firmy z filtrowaniem po statusie (`applied`, `skipped`, `presented`) i wyszukiwarką po nazwie/domenie.

---

## Struktura projektu

```
crm-job-agent/
├── backend/
│   ├── main.py                  # FastAPI app, CORS, auth middleware
│   ├── routers/
│   │   ├── discovery.py         # POST /find, /skip, /apply
│   │   └── companies.py         # GET /companies, PATCH, DELETE
│   ├── core/
│   │   ├── discovery_loop.py    # główna pętla: SerpAPI → filtry → Haiku → DB
│   │   ├── query_generator.py   # generuje zapytanie do SerpAPI (Python, bez LLM)
│   │   └── page_verifier.py     # Haiku klasyfikuje stronę: polska firma AI?
│   ├── db/
│   │   └── client.py            # Supabase client, wszystkie zapytania SQL
│   └── models/
│       └── schemas.py           # Pydantic modele request/response
├── frontend/
│   ├── app/
│   │   ├── page.tsx             # Discovery view
│   │   └── crm/page.tsx         # CRM Dashboard
│   └── components/
│       ├── CompanyCard.tsx      # karta firmy + przyciski decyzji
│       ├── ApplicationForm.tsx  # formularz zapisywania aplikacji
│       ├── CRMTable.tsx         # tabela z paginacją
│       └── ManualEntryModal.tsx # modal ręcznego dodawania
├── .env.example
├── requirements.txt
└── Procfile                     # start command dla Railway
```

---

## Technologie

| Warstwa | Technologia | Wersja |
|---|---|---|
| Frontend | Next.js (App Router) | 14+ |
| Styling | Tailwind CSS | 3+ |
| Backend | FastAPI | 0.111+ |
| Runtime | Python | 3.12 |
| LLM | Claude Haiku (`claude-haiku-4-5-20251001`) | — |
| LLM framework | LangChain + langchain-anthropic | 0.2+ |
| Wyszukiwanie | SerpAPI (Google Search) | — |
| Baza danych | PostgreSQL przez Supabase | — |
| HTTP client | httpx + BeautifulSoup4 | — |
| Hosting backend | Railway | — |
| Hosting frontend | Vercel | — |

---

## Deployment

### Backend → Railway

1. Połącz repozytorium z Railway
2. Dodaj zmienne środowiskowe w dashboardzie Railway:
   ```
   ANTHROPIC_API_KEY
   SERPAPI_KEY
   SUPABASE_URL
   SUPABASE_SERVICE_ROLE_KEY
   API_SECRET
   FRONTEND_URL   ← URL frontendu na Vercel (dla CORS)
   ```
3. Railway wykrywa `Procfile` i deployuje automatycznie przy każdym pushu na `main`

### Frontend → Vercel

1. Połącz repozytorium z Vercel, ustaw **Root Directory** na `frontend`
2. Dodaj zmienne środowiskowe:
   ```
   NEXT_PUBLIC_API_URL      ← URL backendu z Railway
   NEXT_PUBLIC_API_SECRET   ← ten sam co API_SECRET w backendzie
   ```
3. Vercel deployuje automatycznie przy każdym pushu na `main`
