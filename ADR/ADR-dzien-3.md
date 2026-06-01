# ADR Dzień 3 — Frontend + Deployment

Data: 2026-05-09
Branch: `feature/day-3-frontend` → zmergowany do `main`
Status: ukończony, aplikacja na produkcji

---

## Część I — Dokumentacja techniczna (dla Claude Code)

### Co zostało zbudowane

Kompletny frontend Next.js 16 + deployment na Railway (backend) i Vercel (frontend). Po Dniu 3 aplikacja działa na produkcji pod adresem https://crm-job-agent.vercel.app.

### Schemat nowych plików i zależności

```
frontend/
│
├── lib/
│   └── api.ts                        # typowany klient HTTP
│       ├── type Company { ... }       # odpowiada CompanyOut z backend/models/schemas.py
│       ├── apiFetch<T>(path, init)    # wspólny wrapper — throw Error z body.detail
│       └── api.{findCompany, skipCompany, applyCompany, getCompanies}
│
├── app/
│   ├── layout.tsx                    # root layout — Geist font, nav (Odkrywanie / CRM)
│   ├── globals.css                   # Tailwind 4 — @import "tailwindcss"
│   │
│   ├── page.tsx                      # Discovery view — główna strona
│   │   ├── type Phase = "idle" | "found" | "applying"
│   │   ├── state: phase, company, loading, error
│   │   ├── findCompany() → api.findCompany() → setCompany + setPhase("found")
│   │   ├── handleSkip() → api.skipCompany() → reset do idle
│   │   └── handleApply(data) → api.applyCompany() → api.findCompany() [auto-trigger]
│   │
│   └── crm/
│       └── page.tsx                  # CRM Dashboard
│           ├── state: companies, page, status, loading, error
│           ├── fetchPage(p, s) → api.getCompanies({page, limit:20, status})
│           └── useEffect: fetchPage przy zmianie page lub status
│
└── components/
    ├── CompanyCard.tsx               # karta firmy
    │   ├── props: company, onSkip, onApply, loading
    │   └── disabled={loading} na obu przyciskach — zapobiega race condition [K1]
    │
    ├── ApplicationForm.tsx           # formularz aplikacji
    │   ├── props: onSubmit, onCancel, loading
    │   └── fields: position, salary_expectation, contact_email, notes
    │
    └── CRMTable.tsx                  # tabela z paginacją
        ├── props: companies, page, hasMore, onPrev, onNext
        ├── hasMore = companies.length === LIMIT (20) — brak count query do bazy
        └── STATUS_LABELS + STATUS_STYLES — tłumaczenia i kolory statusów
```

### Stack frontendu

| Biblioteka | Wersja | Uwaga |
|---|---|---|
| Next.js | 16.2.6 | App Router, Turbopack dev server |
| React | 19.2.4 | |
| Tailwind CSS | 4.x | `@import "tailwindcss"` zamiast `@tailwind base/components/utilities` |
| TypeScript | 5.x | strict mode |

### Konfiguracja deploymentu

```
crm-job-agent/
├── Procfile          web: cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
├── railway.toml      builder = "nixpacks" (ignorowany — Railway używa railpack)
└── .python-version   3.12
```

**Railway env vars:**
```
ANTHROPIC_API_KEY, TAVILY_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
FRONTEND_URL=https://crm-job-agent.vercel.app   ← CORS allowlist
LANGSMITH_TRACING, LANGSMITH_API_KEY, LANGSMITH_PROJECT
```

**Vercel env vars:**
```
NEXT_PUBLIC_API_URL=https://crm-job-agent-production.up.railway.app
```

### Przepływ stanu w Discovery view

```
[idle]
  │ kliknięcie "Znajdź firmę"
  ▼
[loading=true] → POST /find
  │ sukces
  ▼
[found] → CompanyCard widoczna
  │                    │
  │ "Pomiń"            │ "Wysłałem CV"
  ▼                    ▼
POST /skip          [applying] → ApplicationForm widoczna
  │                    │ submit
  ▼                    ▼
[idle]              POST /apply → POST /find [auto-trigger, bez kliknięcia]
                       │
                       ▼
                    [found] → nowa firma
```

### Fix: is_company_page w page_verifier

Dodane podczas Dnia 3 po tym jak agent zwrócił stronę "top chatbot companies in Poland".

```python
# przed
class PageVerification(BaseModel):
    is_polish: bool
    is_ai_company: bool
    what_they_do: str

# po
class PageVerification(BaseModel):
    is_polish: bool
    is_ai_company: bool
    is_company_page: bool  # False dla list, rankingów, artykułów, katalogów
    what_they_do: str

# discovery_loop.py
if not verification.is_polish or not verification.is_ai_company or not verification.is_company_page:
    continue
```

Koszt: +~50 tokenów/wywołanie (dodatkowe pole w structured output). Benefit: eliminuje cały typ false positive.

### Decyzje architektoniczne podjęte w Dniu 3

| Decyzja | Wybór | Alternatywa odrzucona | Powód |
|---|---|---|---|
| Stan discovery jako enum Phase | `"idle" \| "found" \| "applying"` | boolean flagi `showCard`, `showForm` | enum jest exhaustive — niemożliwy stan `showCard=false, showForm=true` |
| hasMore bez count query | `companies.length === LIMIT` | `GET /companies/count` | dodatkowy request do bazy tylko po to żeby wiedzieć czy jest następna strona; false negative (ostatnia strona = dokładnie 20 rekordów) akceptowalny |
| apiFetch rzuca Error z body.detail | `throw new Error(body?.detail?.message ?? ...)` | zwracanie `{ok, data, error}` | komponenty nie muszą sprawdzać `if (!result.ok)` — try/catch w page.tsx obsługuje wszystko |
| Procfile zamiast railway.toml startCommand | `Procfile` | tylko `railway.toml` | Railway railpack ignoruje `builder = "nixpacks"` w railway.toml i nie wykrywa startCommand bez Procfile |

### Błędy napotkane w Dniu 3

**B1 — create-next-app odmawia scaffoldowania do istniejącego katalogu**
- Przyczyna: `frontend/app/` i `frontend/components/` już istniały (puste katalogi z Dnia 1)
- Fix: scaffold do `frontend-tmp/`, skopiowanie plików konfiguracyjnych, usunięcie tempa
- Wniosek: `create-next-app` nie przyjmuje katalogu z jakimikolwiek podfolderami

**B2 — Railway używa railpack zamiast nixpacks**
- Przyczyna: Railway przeszedł na railpack jako domyślny builder; `builder = "nixpacks"` w railway.toml ignorowany
- Objaw: `✖ No start command detected`
- Fix: dodanie `Procfile` z `web: cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
- Wniosek: Procfile jest rozumiany przez oba buildery; railway.toml startCommand działa tylko z nixpacks

**B3 — Vercel próbuje buildować backend zamiast frontendu**
- Przyczyna: Root Directory nie ustawiony — Vercel wykrył `main.py` w rocie i próbował deployować FastAPI
- Objaw: `Error: No FastAPI entrypoint found`
- Fix: ustawienie Root Directory = `frontend` w Vercel dashboard
- Wniosek: przy monorepo Root Directory MUSI być ustawiony ręcznie w Vercel UI

**B4 — Frontend odpytuje localhost:8000 na produkcji**
- Przyczyna: `NEXT_PUBLIC_API_URL` nie był ustawiony w Vercel; fallback w `lib/api.ts` to `localhost:8000`
- Objaw: `ERR_CONNECTION_REFUSED` w konsoli przeglądarki
- Fix: dodanie `NEXT_PUBLIC_API_URL=https://crm-job-agent-production.up.railway.app` w Vercel + redeploy
- Wniosek: zmienne `NEXT_PUBLIC_*` są wbudowywane w kod podczas builda — samo dodanie zmiennej bez redeployu nie działa

**B5 — Agent zwracał stronę z listą firm zamiast strony konkretnej firmy**
- Przyczyna: `page_verifier.py` nie miał kryterium odróżniającego stronę firmy od artykułu/rankingu
- Objaw: wynik `/find` = "Top 10 chatbot companies in Poland"
- Fix: dodanie `is_company_page: bool` do `PageVerification` + kryterium 3 w prompcie
- Wniosek: Haiku potrzebuje explicite kryterium dla każdego przypadku który chcemy wykluczyć

### Stan po Dniu 3

MWS ukończony. Aplikacja działa na produkcji.

Pozostałe rzeczy do zrobienia po MWS:
- `X-API-Key` shared secret (backend nie jest chroniony — każdy zna URL Railway może wysyłać requesty)
- Optymalizacja kosztów tokenów: skrócić MAX_CONTENT_CHARS z 6000 → 2000-3000
- Heurystyczny pre-filter z ADR-003 (polskie znaki / domena .pl) przed wywołaniem Haiku
- Manual Entry Form (faza 3)

---

## Część II — Podsumowanie dla Konrada

### Co zbudowaliśmy

Zbudowaliśmy **twarz agenta** — interfejs przez który możesz go używać — i wysłaliśmy całość na serwery. Po Dniach 1 i 2 mieliśmy działający silnik który można było uruchomić tylko przez terminal. Po Dniu 3 masz stronę internetową pod adresem https://crm-job-agent.vercel.app.

### Konkretnie co powstało

**Strona Discovery** — wchodzisz, klikasz jeden przycisk, agent szuka firmy i ją pokazuje. Masz dwa przyciski: "Pomiń" (agent szuka kolejnej) i "Wysłałem CV" (otwiera formularz). Po wypełnieniu formularza agent automatycznie szuka następnej firmy bez dodatkowego kliknięcia. Przycisk blokuje się podczas wyszukiwania żeby przypadkowe podwójne kliknięcie nie wywołało dwóch requestów naraz.

**Strona CRM** — tabela wszystkich firm które agent znalazł. Możesz filtrować po statusie: wszystkie, tylko gdzie wysłałeś CV, pominięte, pokazane. Tabela ładuje po 20 rekordów — nie pobiera wszystkiego naraz.

**Deployment** — backend siedzi na Railway (serwer w chmurze w USA), frontend na Vercel (globalny CDN). Obydwa są połączone i rozmawiają ze sobą.

### Jeden bug który naprawiliśmy po drodze

Agent zwrócił stronę "Top 10 polskich firm chatbotowych" zamiast strony konkretnej firmy. Dodaliśmy Haiku trzecie pytanie: "czy to strona jednej firmy, czy lista/artykuł/ranking?" — teraz takie strony są odrzucane automatycznie.

### 4 problemy techniczne które rozwiązaliśmy

1. **Railway nie wiedział jak uruchomić aplikację** — dodaliśmy plik `Procfile` który mówi: "uruchom backend z tego folderu tą komendą"
2. **Vercel próbował deployować backend zamiast frontendu** — musieliśmy mu powiedzieć żeby patrzył do folderu `frontend/`
3. **Frontend szukał backendu na twoim laptopie** zamiast na Railway — brakowało zmiennej środowiskowej z adresem URL
4. **Dwa adresy URL do skonfigurowania** — Railway musi znać adres Vercel (żeby przepuścić requesty), Vercel musi znać adres Railway (żeby wiedzieć gdzie wysyłać). Chicken-and-egg problem — rozwiązany przez odpowiednią kolejność deployu

### Ile to kosztuje

- Railway: ~$5/mies (najtańszy plan z zawsze-działającym serwerem)
- Vercel: $0 (Hobby plan wystarczy)
- Supabase: $0 (Free tier wystarczy na setki rekordów)
- Anthropic (Haiku): ~$1-2/mies przy regularnym używaniu
- Tavily: $0 na starcie (darmowy tier = 1000 wyszukiwań/mies)

Łącznie: ~$5-7/mies

### Co zostało do zrobienia

Aplikacja jest w pełni użyteczna teraz. Rzeczy na później:
- **Zabezpieczenie** — URL backendu jest publiczny, każdy kto go zna może go odpytywać. Nie jest to pilne (nikt go nie zna), ale warto dodać prostą ochronę hasłem między frontendem a backendem
- **Tańsze wyszukiwanie** — jedno kliknięcie kosztuje ~3000 tokenów. Można to obciąć do ~1000-1500 bez utraty jakości klasyfikacji
- **Ręczne dodawanie firm** — żebyś mógł dodać firmę którą znalazłeś sam (np. z OLX/Pracuj.pl) bez agenta
