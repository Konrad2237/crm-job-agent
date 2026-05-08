# CRM Job Agent

Narzędzie do znajdowania polskich firm AI i śledzenia aplikacji o pracę.

## Problem

Ręczne szukanie firm przez ChatGPT daje złe linki, angielskie strony i ciągłe powtórki. Notatnik z firmami nie ma linków, dat, stanowisk ani statusów.

## Jak działa

1. Klikasz **"Znajdź firmę"**
2. Agent wyszukuje jedną polską firmę z obszaru AI, której jeszcze nie odwiedziłeś
3. Otwierasz link, decydujesz czy aplikujesz
4. Dane trafiają do CRM
5. Agent automatycznie szuka kolejnej

## Stack

| Warstwa | Technologia |
|---|---|
| Frontend | Next.js + Tailwind CSS → Vercel |
| Backend | Python 3.12 + FastAPI → Railway |
| Baza danych | PostgreSQL → Supabase |
| LLM | Claude Haiku 4.5 (Anthropic) |
| Wyszukiwanie | Tavily API |
| LLM Framework | LangChain |

## Architektura

LLM robi **tylko dwie rzeczy**: generuje zapytanie wyszukiwania i klasyfikuje stronę (polska + AI?). Cała logika pętli jest w Pythonie — zero agentic loops, pełna kontrola nad tokenami.

```
POST /find
  → generuj zapytanie (Haiku)
  → szukaj w Tavily (max 5 wyników)
  → dla każdego URL: sprawdź dedup → pobierz treść → klasyfikuj (Haiku)
  → zapisz do DB i zwróć firmę
```

## Struktura projektu

```
crm-job-agent/
├── backend/
│   ├── main.py                 # FastAPI app
│   ├── routers/
│   │   ├── discovery.py        # POST /find, /skip, /apply
│   │   └── companies.py        # GET /companies, POST /manual, PATCH /{id}
│   ├── core/
│   │   ├── discovery_loop.py   # główna pętla (Python)
│   │   ├── query_generator.py  # generowanie zapytań (Haiku)
│   │   └── page_verifier.py    # klasyfikacja strony (Haiku)
│   ├── db/
│   │   └── client.py           # Supabase + zapytania SQL
│   └── models/
│       └── schemas.py          # Pydantic modele
├── frontend/
│   ├── app/
│   │   ├── page.tsx            # Discovery view
│   │   └── crm/page.tsx        # CRM Dashboard
│   └── components/
│       ├── CompanyCard.tsx
│       ├── ApplicationForm.tsx
│       └── CRMTable.tsx
├── .env.example                # szablon zmiennych środowiskowych
└── requirements.txt
```

## Setup lokalny

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp ../.env.example .env       # uzupełnij klucze API
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Zmienne środowiskowe

Skopiuj `.env.example` do `.env` i uzupełnij:

```
ANTHROPIC_API_KEY=     # Anthropic Console
TAVILY_API_KEY=        # Tavily Dashboard
SUPABASE_URL=          # Supabase Project Settings
SUPABASE_SERVICE_KEY=  # Supabase Project Settings → Service Role
```
