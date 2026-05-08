# Stress Test — CRM Job Agent
**Data:** 2026-05-08

---

## SKALOWALNOŚĆ

### Co się stanie gdy baza firm urośnie do tysięcy rekordów?

**Dedup check (`WHERE domain = $1`)** — indeks na kolumnie `domain` sprawia że to zapytanie O(log n). Przy 100,000 rekordach nadal <1ms. Nie jest wąskim gardłem.

**`GET /companies` bez paginacji** — tu jest problem.

| Rekordów | Rozmiar odpowiedzi | Co się dzieje |
|---|---|---|
| 100 | ~50KB | OK |
| 500 | ~250KB | Wolno ale działa |
| 1,000 | ~500KB | Zauważalne opóźnienie |
| 5,000 | ~2.5MB | Frontend próbuje wyrenderować 5,000 wierszy tabeli → przeglądarka freezuje |
| 10,000 | ~5MB | Timeout Railway, crash przeglądarki |

Przy aktualnym tempie (kilkadziesiąt firm tygodniowo + ręczne z OLX) **próg 500 rekordów osiągniesz w ciągu 1-2 miesięcy.**

**Renderowanie tabeli CRM** — React renderujący 5,000 `<tr>` bez wirtualizacji zamrozi kartę przeglądarki na kilka sekund.

**Egress Supabase Free tier** — limit 2GB/mies. Przy pobieraniu 10,000 rekordów × 1KB × kilka razy dziennie = ~1GB/mies. Ryzyko przekroczenia limitu.

### Które komponenty stają się wąskim gardłem?

1. **`GET /companies`** — brak LIMIT/OFFSET → pobiera całą tabelę za każdym razem
2. **`CRMTable.tsx`** — brak wirtualizacji → renderuje cały DOM naraz
3. **Filtrowanie** — jeśli zrobione po stronie frontendu (JavaScript) zamiast w SQL `WHERE status = $1`, to i tak pobieramy wszystko z bazy

### Co trzeba zmienić?

```
GET /companies?page=1&limit=20&status=applied
→ SELECT * FROM companies WHERE status = $1
  ORDER BY created_at DESC
  LIMIT 20 OFFSET 0
```

Zmiana w 3 miejscach: endpoint, SQL query, komponent tabeli (dodać przyciski Poprzednia/Następna). Koszt: pół dnia.

---

## AWARIE

### Scenariusz 1: Anthropic API niedostępne

Per ADR-003: retry 2× z 2-sekundowym opóźnieniem. Brzmi dobrze — ale policzmy pesymistyczny scenariusz:

```
15 URL-i × (2 sekundy czekania × 2 retry) = 60 sekund spinnera
```

Przez minutę użytkownik widzi "ładowanie..." bez żadnego feedbacku. Potem dostaje 503.

**Brakuje: globalny timeout na cały discovery loop.** Bez niego loop może wisieć i Railway zerwie połączenie po ~30 sek i tak, zwracając nieczytelny błąd 502.

**Graceful degradation: CZĘŚCIOWO** — system ostatecznie zwróci błąd, ale bez sensownego komunikatu i z długim czekaniem.

### Scenariusz 2: Agent nie znajdzie wyników

Trzy możliwe przyczyny, jedna obsługa:

| Przyczyna | Co się dzieje |
|---|---|
| Tavily zwraca 0 wyników | Loop przechodzi do kolejnego attempt, po 3 attempts → return None |
| Wszystkie 15 URL-i jest już w DB | Jak wyżej |
| Wszystkie 15 URL-i odpada weryfikację | Jak wyżej |

Po 3 attempts backend zwraca... co? **Brak zdefiniowanej odpowiedzi dla tego przypadku.** Endpoint zwróci `None` → FastAPI domyślnie przekonwertuje to na `null` w JSON. Frontend dostanie `{company: null}` i crashnie jeśli nie obsługuje tego stanu.

**Brakuje: zdefiniowanego kodu odpowiedzi i komunikatu dla "nie znaleziono firmy"** (np. 200 z `{found: false, message: "Nie znaleziono nowych firm. Spróbuj za chwilę."}`)

**Graceful degradation: CZĘŚCIOWO** — loop się nie zapętli, ale frontend nie wie co pokazać.

### Scenariusz 3: Baza danych przestaje odpowiadać

To najpoważniejszy gap w architekturze. Brak jakiegokolwiek try/except w `db/client.py`.

```python
# Aktualnie (zakładamy):
async def is_domain_seen(domain: str) -> bool:
    result = await supabase.table("companies").select("id")...
    return result.data  # ← jeśli Supabase jest down: nieobsłużony wyjątek

# FastAPI zwróci: HTTP 500 Internal Server Error
# Z pełnym Python traceback w body — w tym potencjalnie fragmenty connection string
```

**Supabase Free tier ma znany problem: po 7 dniach braku aktywności baza "zasypia".** Pierwsze zapytanie po uśpieniu trwa 10-30 sekund. Brak timeout → FastAPI czeka, Railway zerwie połączenie po 30 sek → błąd 502 bez informacji dla użytkownika.

**Graceful degradation: NIE** — każdy błąd DB = crash endpointu.

### Scenariusz 4: Tavily API niedostępne

ADR-003 definiuje retry tylko dla Anthropic API. Dla Tavily: **brak retry, brak obsługi błędów.**

Gdy Tavily zwróci 429 (rate limit) lub 500:
- Search call rzuca wyjątek → nieobsłużony → 500 z traceback
- Extract call rzuca wyjątek → to samo

**Graceful degradation: NIE** — nie odróżniliśmy Tavily od reszty w strategii błędów.

### Podsumowanie graceful degradation

| Awaria | Graceful degradation? | Co się dzieje |
|---|---|---|
| Anthropic API down | CZĘŚCIOWO | 60 sek czekania, potem 503 |
| Brak wyników Tavily | CZĘŚCIOWO | Poprawny exit, ale frontend nie wie co pokazać |
| Supabase down | NIE | Python traceback jako 500 |
| Supabase cold start | NIE | 30 sek timeout → błąd 502 |
| Tavily down | NIE | Nieobsłużony wyjątek → 500 |

---

## BEZPIECZEŃSTWO

### Klucze API — gdzie są i czy są bezpieczne?

| Klucz | Lokalizacja dev | Lokalizacja prod | Poziom dostępu | Ryzyko wycieku |
|---|---|---|---|---|
| `ANTHROPIC_API_KEY` | `.env` | Railway env vars | Twój billing | Średnie |
| `TAVILY_API_KEY` | `.env` | Railway env vars | Twój billing | Średnie |
| `SUPABASE_SERVICE_KEY` | `.env` | Railway env vars | Pełny dostęp do DB (bypass RLS) | **Wysokie** |
| `LANGSMITH_API_KEY` | `.env` | Railway env vars | Twoje logi/traces | Niskie |
| `NEXT_PUBLIC_API_URL` | `.env` | Vercel env vars | URL backendu | **Patrz niżej** |

**Problem 1: `SUPABASE_SERVICE_KEY`**
Service key omija Row Level Security. Jeśli wycieknie, ktoś ma pełny dostęp do wszystkich Twoich danych aplikacyjnych (firmy, stanowiska, oczekiwane wynagrodzenia, emaile kontaktowe). To są wrażliwe dane kariery.

**Problem 2: `NEXT_PUBLIC_API_URL` eksponuje URL backendu**
Wszystkie zmienne z prefiksem `NEXT_PUBLIC_` są wbudowane w JavaScript który trafia do przeglądarki. Każdy kto otworzy DevTools → Sources widzi Twój Railway URL. Teraz może:
- Wywołać `POST /find` w pętli → spalić limit Tavily i Anthropic
- Odczytać `GET /companies` → zobaczyć całą historię Twoich aplikacji

**Problem 3: CORS nie jest skonfigurowany**
Architektura wymienia CORS w `main.py` ale nie definiuje allowed origins. FastAPI bez konfiguracji CORS blokuje cross-origin requesty w ogóle (co złamie frontend). Albo ktoś doda `origins=["*"]` żeby "działało" → wtedy każda strona w sieci może wywoływać Twój backend.

**Problem 4: Brak `.gitignore` w architekturze**
Architektura wymienia `.env` i `.env.example` ale nie wspomina o `.gitignore`. Jeśli przypadkowo zrobisz `git add .` bez `.gitignore`, wszystkie klucze trafią do repozytorium.

### Dane przy hostingu

- Supabase: dane na AWS (region EU West), szyfrowanie at-rest, SSL w transporcie ✓
- Railway: kod i env vars szyfrowane ✓
- Vercel: tylko frontend, żadnych sekretów w kodzie ✓
- **Lokalna `.env`**: na Twoim dysku, niezaszyfrowana — ryzyko jeśli laptop skradziony lub współdzielony

Dla jednego użytkownika z niepublicznym URL: akceptowalny poziom ryzyka. Ale Railway URL jest przewidywalny (`*.up.railway.app`) — ktoś zgadujący nazwy mógłby trafić.

---

## EDGE CASES

| # | Sytuacja | Jak system powinien zareagować | Czy architektura to obsługuje? |
|---|---|---|---|
| 1 | `www.firma.pl` vs `firma.pl` — ta sama firma, dwie domeny | Funkcja normalizacji domeny powinna stripować `www.` przed zapisem i dedup checkiem | **NIE** — normalizacja domeny nie jest zdefiniowana. Bez niej `firma.pl` i `www.firma.pl` przejdą dedup jako dwie różne firmy |
| 2 | Podwójne kliknięcie "Znajdź firmę" — dwa równoległe POST /find | Drugi request powinien być ignorowany lub poczekać na wynik pierwszego | **NIE** — race condition. Oba requesty sprawdzają dedup jednocześnie, oba uznają URL za nowy, oba zapisują ten sam rekord → duplikat w bazie |
| 3 | Tavily zwraca link do LinkedIn/Clutch zamiast strony firmowej | Pre-filter: domena `.com` bez polskich znaków → odrzucić. Jeśli przejdzie: Haiku zobaczy interfejs LinkedIn/angielski opis → odrzuci | **CZĘŚCIOWO** — pre-filter pomaga, ale linkedin.com nie jest wprost na blackliście |
| 4 | Strona firmowa to SPA (React/Vue/Angular) — Tavily Extract zwraca pusty HTML | Treść pusta → pre-filter (pusta treść = skip). Firma jest stracona, nawet jeśli to dobra polska firma AI | **CZĘŚCIOWO** — pre-filter złapie pusty content, ale nie ma fallbacku (np. snippet z search jako substytut) |
| 5 | Strona "w budowie" — 1 zdanie treści | Treść niepusta → przechodzi pre-filter. Haiku klasyfikuje na podstawie 1 zdania ("Wróć wkrótce") → is_valid: false (poprawnie). Ale firma jest zapisana jako pominięta i nie wróci nigdy | **CZĘŚCIOWO** — klasyfikacja będzie poprawna, ale firma jest bezpowrotnie stracona mimo że może za miesiąc mieć pełną stronę |
| 6 | Bardzo długa strona — blog firmowy z 200 artykułami, Tavily Extract zwraca 80,000 tokenów | 80,000 tokenów × $0.0008 = $0.064 za JEDNO wywołanie. Przy normalnym koszcie $0.001 to 64× drożej | **NIE** — brak truncacji treści przed wysłaniem do Haiku. Jedna taka strona to prawie tygodniowy budżet LLM |
| 7 | Formularz aplikacji wysłany z pustymi polami | Rekord zapisany z status=applied ale bez position, notes. Użytkownik nie wie na co aplikował | **TECHNICZNIE TAK** (nullable pola), ale **UX NIE** — brak walidacji w formularzu, brak komunikatu |
| 8 | Agent znajdzie firmę która zmieniła domenę na nową | Stara domena jest w DB → nowa domena przejdzie dedup → użytkownik zobaczy tę samą firmę pod nowym URL | **AKCEPTOWALNE** — to normalne zachowanie, nie błąd |
| 9 | Supabase cold start po tygodniu nieaktywności (Free tier) | Pierwsze zapytanie wisí 10-30 sek. Brak timeout = Railway zerwie po 30 sek → błąd 502 bez info dla użytkownika | **NIE** — brak obsługi cold start, brak timeout na połączenie DB |
| 10 | Użytkownik kliknie "Wysłałem CV" ale zamknie przeglądarkę przed zapisaniem formularza | Firma ma status `presented` w DB. Nigdy nie wróci (dedup ją złapie). Aplikacja "przepadła" | **NIE** — status `presented` powinien wygasać po pewnym czasie lub być czyszczony przy starcie sesji |

---

## OCENA KOŃCOWA

### Lista problemów od najpoważniejszych

**KRYTYCZNE — naprawić przed pierwszym użyciem produkcyjnym:**

| Problem | Sugerowane rozwiązanie |
|---|---|
| **Brak paginacji `GET /companies`** — przy 500+ rekordach frontend crashnie | Dodaj `?page=1&limit=20` do endpointu, `LIMIT/OFFSET` do SQL, przyciski stronic w tabeli |
| **Brak obsługi błędów bazy danych** — każdy błąd Supabase = Python traceback jako HTTP 500 | Owinąć wszystkie wywołania `db/client.py` w `try/except`, zwracać 503 z czytelnym komunikatem |
| **Race condition przy podwójnym kliknięciu** — duplikaty w bazie | Dodać `UNIQUE` constraint na kolumnie `domain` + użyć `INSERT ... ON CONFLICT DO NOTHING` |

**POWAŻNE — naprawić w pierwszym tygodniu po MWS:**

| Problem | Sugerowane rozwiązanie |
|---|---|
| **Discovery loop może wisieć 60 sekund** gdy Anthropic down | Dodać globalny `asyncio.timeout(20)` na cały loop, natychmiastowy 503 po przekroczeniu |
| **Brak retry dla Tavily API** | Taka sama logika retry (2× z 2-sek opóźnieniem) jak dla Anthropic — wyciągnąć do wspólnej funkcji `call_with_retry()` |
| **Brak truncacji treści strony** — długi blog = 64× normalny koszt | Truncować content do pierwszych 6,000 znaków przed wysłaniem do Haiku |
| **`NEXT_PUBLIC_API_URL` eksponuje Railway URL** | Dodać prosty shared secret: header `X-API-Key` w każdym requeście frontendowym, backend weryfikuje |

**UMIARKOWANE — można odkładać ale warto zrobić:**

| Problem | Sugerowane rozwiązanie |
|---|---|
| **CORS nie skonfigurowany** | `allow_origins=["https://twoj-frontend.vercel.app"]` w FastAPI CORSMiddleware |
| **Normalizacja domeny dla dedup** — `www.firma.pl` ≠ `firma.pl` | Funkcja `normalize_domain(url)` stripująca `www.`, `http(s)://`, trailing slash |
| **Status `presented` nie wygasa** — zamknięcie przeglądarki traci firmę | Przy starcie sesji (load strony) wyczyść stare rekordy `presented` starsze niż 24h z powrotem do kolejki albo oznacz je jako `skipped` |
| **Brak `.gitignore`** explicite w architekturze | `.env` musi być w `.gitignore` od pierwszego commitu — zrobić to w Dniu 1 zanim cokolwiek innego |

**NISKIE — akceptowalne dla MWS:**

| Problem | Sugerowane rozwiązanie |
|---|---|
| Supabase cold start po nieaktywności | Dodać Railway cron job `GET /health` co 5 minut żeby utrzymać połączenie ciepłe, lub upgrade Supabase |
| SPA strony bez Tavily Extract content | Użyć snippet z wyników search jako fallback gdy extract zwraca <100 znaków |
| Brak walidacji formularza aplikacji | Minimum: wymagać pola `position` (chociaż jedno pole żeby rekord miał sens) |

---

### Ocena dojrzałości architektury: **6.5 / 10**

**Mocne strony (+):**
- Discovery loop jako deterministyczna pętla Python (nie agentic LLM loop) — to mądra decyzja która zapobiega tokenowym katastrofom
- Schemat bazy dobrze przemyślany, indeksy na właściwych kolumnach
- ADRy dokumentują dlaczego, nie tylko co — ułatwi debugging za 2 tygodnie
- Single-table design jest prosty i wystarczający dla single user

**Słabe strony (-):**
- Obsługa błędów jest prawie nieobecna (DB, Tavily, brak globalnego timeout)
- Paginacja pominięta mimo że problem jest przewidywalny
- Race condition to klasyczny bug który pojawi się dokładnie wtedy gdy będziesz testował z kolegą albo podwójnie klikniesz z przyzwyczajenia
- Bezpieczeństwo opiera się na "nikt nie zna URL" — cienka linia

**Werdykt:**
Architektura jest solidna koncepcyjnie — właściwe decyzje technologiczne, właściwy zakres MWS, właściwy model kosztowy. Problemy które ma to klasyczne "szczęśliwa ścieżka" — system działa gdy wszystko idzie dobrze, ale nie jest przygotowany na pierwsze realne zderzenie z produkcją. Trzy krytyczne poprawki (paginacja, obsługa błędów DB, race condition) wystarczą żeby podnieść ocenę do 8/10.
