# Testy przypadków — weryfikacja architektury
**Data:** 2026-05-08

---

## Scenariusz 1: Pierwsza wizyta — happy path

**Opis:** Pusta baza, użytkownik klika "Znajdź firmę" po raz pierwszy, dostaje kartę firmy, decyduje się aplikować, wypełnia formularz.

**Dane wejściowe:**
- DB: 0 rekordów
- Tavily search zwraca: `[{url: "https://nexocode.com", title: "Nexocode - AI Software House", snippet: "Tworzymy rozwiązania AI dla przedsiębiorstw..."}]`
- Użytkownik wypełnia: stanowisko = "AI Developer", notatki = "Wysłałem email na hr@nexocode.com"

**Oczekiwany rezultat:** Rekord w DB ze statusem `applied`, position i notes wypełnione.

---

### Ścieżka przez komponenty

```
[1] Company Presenter (Frontend)
    Użytkownik klika "Znajdź firmę"
    → POST /find → Backend Orchestrator

[2] Backend Orchestrator
    Odbiera żądanie, wywołuje discovery_loop()
    Dane: brak parametrów wejściowych

[3] Query Generator (Haiku)
    Prompt: "Wygeneruj polskie zapytanie wyszukiwania dla polskich firm AI"
    Poprzednie zapytania: [] (pusta lista)
    Output: "firma AI automatyzacje agenci Polska"
    Tokeny: ~120 input + ~15 output = ~135 tokenów

[4] Tavily Search API
    Zapytanie: "firma AI automatyzacje agenci Polska", max_results=5
    Output: lista 5 URL-i, w tym nexocode.com

[5] Dedup Filter (dla nexocode.com)
    SELECT EXISTS(SELECT 1 FROM companies WHERE domain = 'nexocode.com')
    Wynik: false (pusta baza)
    Czas: <1ms

[6] Tavily Extract API
    URL: https://nexocode.com
    Output: ~3,000 słów treści po polsku o usługach AI

[7] Pre-filter (bez AI)
    Czy treść niepusta? TAK ✓
    Czy domena .pl? NIE (nexocode.com)
    Czy treść zawiera polskie znaki (ą,ę,ó,ś,ź,ż)? TAK ✓
    Wynik: przechodzi

[8] Page Verifier (Haiku)
    Input: treść strony ~3,000 słów
    Output: {is_valid: true, what_they_do: "AI software house, automatyzacje procesów, ML"}
    Tokeny: ~500 input + ~30 output = ~530 tokenów

[9] CRM Database
    INSERT INTO companies (
      name='Nexocode', url='https://nexocode.com',
      domain='nexocode.com', what_they_do='AI software house...',
      status='presented', source='agent'
    )
    Output: {id: "uuid-123", ...}

[10] Company Presenter (Frontend)
     Wyświetla kartę: nazwa, link, opis działalności
     Użytkownik klika link → otwiera w nowej karcie
     Użytkownik klika "Wysłałem CV"

[11] Application Form (Frontend)
     Użytkownik wypełnia: position="AI Developer", notes="..."
     Klika "Zapisz"
     → POST /companies/uuid-123/apply

[12] Backend Orchestrator
     UPDATE companies SET
       status='applied', position='AI Developer',
       notes='...', applied_at=NOW()
     WHERE id='uuid-123'

[13] Company Presenter (Frontend)
     ??? ← luka w architekturze (patrz niżej)
```

---

### Potencjalne problemy

| Etap | Problem | Prawdopodobieństwo |
|---|---|---|
| [3] Query Generator | Pierwsza sesja bez historii — zapytanie może być zbyt generyczne ("AI Polska") i zwrócić głównie artykuły blogowe | Średnie |
| [7] Pre-filter | nexocode.com nie ma domeny .pl — gdyby treść była po angielsku, firma byłaby odrzucona mimo że jest polska | Niskie |
| [13] Po zapisie | Frontend nie wie co pokazać po "Zapisz" — automatycznie szuka nowej firmy? Pokazuje komunikat sukcesu? Niezdecydowane zachowanie | **Pewne** |

### Czy architektura obsługuje ten przypadek?

**PRAWIE — jeden gap.** Kroki 1-12 działają poprawnie. Problem pojawia się po kroku 12: architektura nie definiuje co dzieje się po kliknięciu "Zapisz" w formularzu. Użytkownik widzi... co? Pusty ekran? Ten sam formularz? Czy automatycznie odpala się kolejne `/find`?

### Modyfikacja

W `ApplicationForm.tsx` po udanym POST `/apply` → automatycznie wywołaj `POST /find` i przejdź do kolejnej firmy. Bez akcji użytkownika — naturalny rytm pracy.

---
---

## Scenariusz 2: Race condition — podwójne kliknięcie

**Opis:** Użytkownik nerwowo klika "Znajdź firmę" dwa razy w odstępie 80ms (np. z przyzwyczajenia do powolnych stron). Dwa równoległe POST /find trafiają na backend.

**Dane wejściowe:**
- DB: 50 rekordów (aktywny użytkownik)
- Oba requesty generują zapytanie i Tavily zwraca tę samą listę wyników
- Pierwszym nowym URL-em (nie w DB) jest `https://bothouse.pl`

**Oczekiwany rezultat:** Użytkownik widzi jedną kartę firmy. `bothouse.pl` ma jeden rekord w DB.

---

### Ścieżka przez komponenty (timeline)

```
t=0ms     Request A: POST /find → discovery_loop()
t=80ms    Request B: POST /find → discovery_loop()

t=200ms   Request A: Query Generator → "firma chatboty Polska"
t=240ms   Request B: Query Generator → "agenci AI wdrożenia Polska" (inne zapytanie - OK)

t=800ms   Request A: Tavily Search → zwraca wyniki, pierwszy nowy URL: bothouse.pl
t=840ms   Request B: Tavily Search → zwraca podobne wyniki, też trafia na bothouse.pl

t=850ms   Request A: Dedup check dla bothouse.pl
           SELECT EXISTS(... WHERE domain='bothouse.pl') → FALSE (nie ma w DB)

t=890ms   Request B: Dedup check dla bothouse.pl
           SELECT EXISTS(... WHERE domain='bothouse.pl') → FALSE ← jeszcze nie ma!
                                                                   Request A nie zdążył zapisać

t=1200ms  Request A: Tavily Extract bothouse.pl
t=1240ms  Request B: Tavily Extract bothouse.pl (marnuje kredyt Tavily)

t=1800ms  Request A: Page Verifier → is_valid: true
t=1840ms  Request B: Page Verifier → is_valid: true (marnuje tokeny)

t=1900ms  Request A: INSERT companies (domain='bothouse.pl', status='presented')
           → sukces

t=1940ms  Request B: INSERT companies (domain='bothouse.pl', status='presented')
           → ??? co się dzieje?
```

---

### Wariant A — brak UNIQUE constraint (obecna architektura)

Request B INSERT przechodzi. W bazie są **dwa rekordy** z `domain='bothouse.pl'`.

Frontend A wyświetla kartę bothouse.pl — użytkownik klika "Wysłałem CV".
Frontend B wyświetla kartę bothouse.pl — użytkownik widzi dwie identyczne karty.

Dedup dla przyszłych sesji: `WHERE domain='bothouse.pl'` zwróci TRUE — firma się nie powtórzy. Ale baza jest zanieczyszczona duplikatem.

### Wariant B — z UNIQUE constraint (zalecone w stress teście)

Request B INSERT rzuca `UniqueViolationError` — **nieobsłużony wyjątek** → HTTP 500 dla Request B.

Frontend B: nieoczekiwany błąd 500 → użytkownik widzi "coś poszło nie tak" podczas gdy firma jest wyświetlona w Request A.

### Potencjalne problemy

| Etap | Problem | Skutek |
|---|---|---|
| Dedup check | Sprawdzone przed zapisem — okno race condition ~90ms | Duplikat lub błąd 500 |
| Tavily Extract | Wywołany dwa razy dla tego samego URL | -2 kredyty Tavily |
| Page Verifier | Wywołany dwa razy | -2× koszt tokenów |
| Frontend | Dwie karty jednocześnie | Dezorientacja użytkownika |

### Czy architektura obsługuje ten przypadek?

**NIE.** Race condition jest realny i wystąpi przy pierwszym nerwowym kliknięciu.

### Modyfikacja (dwa poziomy)

**Poziom 1 — frontend (najprostszy fix, wystarczy na MWS):**
```typescript
// CompanyCard.tsx
const [isLoading, setIsLoading] = useState(false)

const handleFind = async () => {
  if (isLoading) return  // ignoruj kliknięcie gdy request w locie
  setIsLoading(true)
  await fetch('/find', { method: 'POST' })
  setIsLoading(false)
}
```

**Poziom 2 — baza danych (obrona w głębi):**
```sql
-- W Supabase: unique constraint na domain
ALTER TABLE companies ADD CONSTRAINT unique_domain UNIQUE (domain);
-- I w db/client.py:
INSERT INTO companies ... ON CONFLICT (domain) DO NOTHING
-- Jeśli duplikat: zwróć istniejący rekord zamiast błędu
```

Oba fixy razem = problem rozwiązany całkowicie.

---
---

## Scenariusz 3: Tavily zwraca stronę JavaScript (SPA)

**Opis:** Agent generuje zapytanie, Tavily Search znajduje `https://mindcraft.ai` — prawdziwą polską firmę AI. Ich strona jest zbudowana w React (Single Page Application). Tavily Extract próbuje pobrać treść ale dostaje tylko pusty HTML z bundlem JS.

**Dane wejściowe:**
- URL: `https://mindcraft.ai`
- Tavily Extract output: `<html><head>...</head><body><div id="root"></div><script src="/bundle.js"></script></body></html>`
- Treść: ~150 znaków, zero polskich znaków, zero opisu usług

**Oczekiwany rezultat:** URL pominięty, pętla próbuje kolejnego URL-a. Firma bezpowrotnie stracona.

---

### Ścieżka przez komponenty

```
[1–4] Normalny przebieg: query → Tavily Search → mindcraft.ai w wynikach

[5] Dedup Filter
    domain: mindcraft.ai → nie w DB → przechodzi

[6] Tavily Extract
    Output: "<html><body><div id='root'></div>...</body></html>"
    Rozmiar treści: 150 znaków

[7] Pre-filter
    Czy treść niepusta? TAK (150 znaków, technicznie nie pusta) ← PROBLEM
    Czy domena .pl? NIE
    Czy treść zawiera polskie znaki? NIE (pusty div, brak treści)
    Wynik: odpada na braku polskich znaków → URL SKIP

    → discovery_loop: continue, następny URL
```

---

### Potencjalne problemy

| Etap | Problem | Skutek |
|---|---|---|
| Pre-filter "treść niepusta" | 150 znaków to technicznie niepusta treść — ale to tylko HTML szkielet | Pre-filter nie złapie tego przez "content empty" check — złapie dopiero przez brak polskich znaków |
| Stracona firma | mindcraft.ai jest zapisane jako `domain` w DB ze statusem... | **Nie jest zapisane** — loop tylko robi `continue`, nie zapisuje odrzuconych URL-i |
| Ponowne próby | Czy Tavily znajdzie mindcraft.ai w przyszłości? | TAK — za 2 tygodnie ten sam URL może wrócić. Nie ma zapisu że był już próbowany |

### Kluczowy bug: brak "odwiedzonych ale odrzuconych" rekordów

Przy obecnej architekturze, URL który odpada na pre-filterze lub weryfikacji AI **nie jest zapisywany do bazy**.

To znaczy:
- Tavily może zwrócić ten sam URL za tydzień
- Loop spróbuje go znowu: Extract → pusty → odrzucony → znowu stracony kredyt Tavily
- Może się to powtarzać w nieskończoność

### Czy architektura obsługuje ten przypadek?

**CZĘŚCIOWO.** Pre-filter poprawnie odrzuca SPA z pustą treścią. Ale:
- Firma jest bezpowrotnie stracona (brak fallback na snippet)
- Ten sam URL może wracać wielokrotnie (brak czarnej listy odrzuconych)

### Modyfikacja

**Fix 1 — fallback na Tavily snippet** (zamiast tylko Extract):
```python
# page_verifier.py
content = tavily_extract(url)

# Jeśli extract zwrócił za mało treści, użyj snippetu z wyników search
if len(content) < 300:
    content = search_result.snippet  # snippet z Tavily Search (zawsze dostępny)
    # Snippet to zazwyczaj 200-400 słów — wystarczy do wstępnej klasyfikacji
```

**Fix 2 — zapis odrzuconych domen** (opcjonalnie, po MWS):
```python
# Gdy URL odpada na pre-filterze lub page_verifier:
await db.save_rejected_domain(domain)
# Dedup check złapie to przy kolejnym wystąpieniu
```

Fix 1 rozwiązuje problem straconych SPA firm. Fix 2 oszczędza Tavily kredyty na powtórkach.

---
---

## Scenariusz 4: Duża strona — eksplozja tokenów

**Opis:** Tavily zwraca `https://deepsense.ai` — uznana polska firma AI z rozbudowaną stroną: case studies, blog z 150 artykułami, opisy projektów. Tavily Extract zwraca pełną treść.

**Dane wejściowe:**
- URL: `https://deepsense.ai`
- Tavily Extract output: 87,000 znaków (~70,000 tokenów) — pełna treść strony z blogiem

**Oczekiwany rezultat:** Firma poprawnie sklasyfikowana, koszt weryfikacji normalny (~$0.001).

---

### Ścieżka przez komponenty

```
[1–6] Normalny przebieg. Pre-filter: treść niepusta, polskie znaki → przechodzi.

[7] Page Verifier (Haiku) — tutaj jest problem
    
    Wejście do Haiku:
    - System prompt: ~400 tokenów
    - Treść strony: 70,000 tokenów
    - Łącznie: ~70,400 tokenów input

    Haiku 4.5 limit: 200,000 tokenów → mieści się technicznie
    
    Koszt:
    - Input: 70,400 × $0.0008 / 1000 = $0.0563
    - Output: ~50 tokenów × $0.004 / 1000 = $0.0002
    - Łącznie: ~$0.056 za JEDNĄ weryfikację

    Porównanie:
    - Normalna weryfikacja (3,000 znaków): $0.001
    - Ta weryfikacja: $0.056 = 56× drożej

    Czas odpowiedzi Haiku przy 70k tokenach: ~8-15 sekund
    (vs normalnie ~1-2 sekundy)
```

### Symulacja kosztu dla sesji z dużymi stronami

Jeśli 3 z 5 URL-i w jednej partii to duże strony:
```
3 × $0.056 = $0.168 za jedno kliknięcie "Znajdź firmę"
Przy 100 kliknięciach/mies: $16.80 tylko na LLM
+ Tavily Starter $30 = $46.80 → przekracza budżet $20-30
```

### Potencjalne problemy

| Etap | Problem | Skutek |
|---|---|---|
| Page Verifier | Brak truncacji przed wysłaniem do Haiku | Koszt 56× wyższy, czas 8× dłuższy |
| Backend response time | Discovery loop z 3 dużymi stronami: 3 × 12 sek = 36 sek | Frontend spinner przez 36 sekund, Railway może urwać połączenie (timeout 30 sek) |
| Budżet | Kilka dużych stron = przekroczenie miesięcznego budżetu LLM | Zablokowanie Anthropic API do następnego okresu rozliczeniowego |

### Czy architektura obsługuje ten przypadek?

**NIE.** Brak truncacji treści jest wprost wymieniony w stress teście jako problem, ale architektura nie zawiera rozwiązania.

### Modyfikacja

```python
# page_verifier.py — dodać przed wywołaniem Haiku
MAX_CONTENT_CHARS = 6_000  # pierwsze 6000 znaków = zazwyczaj hero + usługi + o nas

def prepare_content(raw_content: str) -> str:
    if len(raw_content) > MAX_CONTENT_CHARS:
        return raw_content[:MAX_CONTENT_CHARS] + "\n[treść ucięta]"
    return raw_content
```

Dlaczego 6,000 znaków (a nie mniej)?
- Pierwsze ~2,000 znaków: nawigacja + hero text + główne usługi
- 2,000–4,000: sekcja "O nas" + technologie
- 4,000–6,000: dodatkowe usługi, case studies
- Powyżej 6,000: zazwyczaj artykuły blogowe — niepotrzebne do klasyfikacji

Koszt po truncacji: $0.001 (identyczny jak normalna strona). Czas: 1-2 sekundy.

---
---

## Scenariusz 5: Użytkownik zamyka przeglądarkę w połowie sesji

**Opis:** Użytkownik klika "Znajdź firmę" o 10:00. Dostaje kartę `BotHouse.pl`. Otwiera stronę w nowej karcie — sprawdza. Telefon przerywa mu pracę, zamyka laptopa. Wraca o 18:00, otwiera aplikację od nowa.

**Dane wejściowe:**
- DB: rekord `{id: "uuid-456", domain: "bothouse.pl", status: "presented", created_at: "10:00"}` (nigdy nie podjęto decyzji)
- Użytkownik klika "Znajdź firmę" o 18:00

**Oczekiwany rezultat:** Użytkownik powinien zobaczyć BotHouse.pl ponownie — ma niepodjętą decyzję.

---

### Ścieżka przez komponenty

```
[18:00] Użytkownik klika "Znajdź firmę" → POST /find

[Backend] discovery_loop()
    attempt=0 → Query Generator → "chatboty AI Polska firmy"
    Tavily Search → zwraca wyniki
    
    Dla bothouse.pl (może wrócić w wynikach):
    [Dedup check] SELECT EXISTS(... WHERE domain='bothouse.pl')
    → TRUE (rekord ze statusem 'presented' jest w DB)
    → SKIP — pominięty

    Dla innych URL-i:
    Dedup check → nie ma ich w DB → weryfikacja → nowa firma zwrócona

[Frontend] Wyświetla nową, inną firmę
```

### Co się stało z BotHouse.pl?

Firma jest w DB ze statusem `presented`. Dla dedup filtra to bez różnicy — `presented` i `skipped` i `applied` traktowane jednakowo: "już widziana". 

BotHouse.pl **nigdy nie wróci**. Użytkownik nie miał szansy zdecydować. Firma zniknęła bez śladu.

### Skala problemu

W ciągu miesiąca intensywnego szukania, jeśli 3-4 razy dziennie zdarzy się przerwanie przed decyzją:
- 3-4 firmy/dzień × 20 dni roboczych = **60-80 firm** bezpowrotnie utraconych w ciągu miesiąca

To nie edge case — to regularne zachowanie przy realnym użytkowaniu.

### Potencjalne problemy

| Problem | Skutek |
|---|---|
| Status `presented` nie wygasa | Każde przerwanie = stracona firma |
| Brak informacji dla użytkownika | Nie wie że ma niepodjęte decyzje |
| Baza rośnie o "presented" rekordy | Śmieciowe dane w CRM |

### Czy architektura obsługuje ten przypadek?

**NIE.** To jeden z poważniejszych UX bugów — cicha utrata firm bez żadnej informacji zwrotnej.

### Modyfikacja

**Fix — sprawdzenie pending firm przy każdym POST /find:**

```python
# discovery_loop.py — dodać NA POCZĄTKU przed generowaniem zapytania
async def find_company():
    # 1. Czy jest firma z niepodjętą decyzją z ostatnich 24h?
    pending = await db.get_pending_presented()
    if pending:
        return pending  # zwróć tę samą firmę, nie szukaj nowej

    # 2. Normalny flow discovery
    for attempt in range(MAX_ATTEMPTS):
        ...
```

```sql
-- db/client.py
SELECT * FROM companies
WHERE status = 'presented'
AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC
LIMIT 1
```

Efekt: jeśli masz niepodjętą firmę z ostatnich 24h, przy następnym kliknięciu "Znajdź firmę" zobaczysz ją ponownie zamiast nowej.

**Opcja 2 — hard cleanup (agresywniejsza):**
Przy każdym POST /find, rekordy `presented` starsze niż 24h zmieniają status na `skipped` automatycznie. Firma jest jawnie pominięta, nie "zawieszona".

Która opcja lepsza? Opcja 1 (powrót pending) jest bardziej user-friendly. Opcja 2 jest prostszą implementacją. Na MWS: Opcja 2 (1 linia SQL), po MWS można ulepszyć do Opcji 1.

---

## Podsumowanie

### Które przypadki przechodzą bez problemów

| Scenariusz | Ocena | Uwaga |
|---|---|---|
| SC1: Happy path | ✅ PRZECHODZI z uwagą | Jeden gap: nie zdefiniowany post-save flow |
| SC3: SPA strona | ✅ PRZECHODZI przez pre-filter | Firma stracona, ale system się nie sypie |

### Które wymagają modyfikacji architektury

| Scenariusz | Problem | Priorytet modyfikacji |
|---|---|---|
| SC2: Double click | Race condition → duplikaty lub 500 | **KRYTYCZNY** — zrobić w Dzień 1 (unique constraint + disable button) |
| SC4: Duża strona | Eksplozja tokenów → przekroczenie budżetu | **KRYTYCZNY** — zrobić w Dzień 2 (truncacja do 6,000 znaków) |
| SC5: Zamknięcie przeglądarki | Stracone firmy, status "presented" leak | **POWAŻNY** — zrobić w Dzień 3 lub po MWS |
| SC1: Post-save flow | Niezdefiniowane zachowanie po "Zapisz" | **NISKI** — UX gap, łatwy fix w frontendzie |

### Luki odkryte przez testy

**Luka 1: Brak definicji "co po zapisaniu aplikacji"**
Scenariusz SC1 ujawnił że po POST /apply frontend nie wie co robić. To musi być zdefiniowane zanim napiszesz pierwszą linię kodu frontendu.
→ Decyzja: po zapisaniu aplikacji, automatycznie wywołaj POST /find i pokaż kolejną firmę.

**Luka 2: Odrzucone URL-e nie są zapamiętywane**
Scenariusz SC3 ujawnił że URL który odpada na pre-filterze może wracać wielokrotnie, marnując Tavily kredyty.
→ Na MWS akceptowalne. Po MWS: zapisuj odrzucone domeny w osobnej tabeli lub kolumnie.

**Luka 3: Fallback na snippet gdy Extract zawodzi**
Scenariusz SC3 pokazał że SPA strony tracą firmę mimo że snippet z Tavily Search mógłby wystarczyć do klasyfikacji.
→ Dodaj: jeśli `len(extracted_content) < 300`, użyj `search_result.snippet` jako content.

**Luka 4: Brak global timeout na discovery loop**
Scenariusze SC2 i SC4 razem pokazują że loop może wisieć długo. Railway ma własny timeout ~30 sek.
→ Dodaj: `asyncio.timeout(25)` na całą funkcję `find_company()`.

### Zmodyfikowana lista prioritetów implementacji (Dzień 1-3)

```
Dzień 1 — przed napisaniem czegokolwiek:
  ✓ UNIQUE constraint na domain (fix SC2)
  ✓ .gitignore z .env (bezpieczeństwo)
  ✓ Zdecyduj: post-save → auto find next (fix SC1)

Dzień 2 — przy pisaniu page_verifier:
  ✓ Truncacja treści do 6,000 znaków (fix SC4)
  ✓ Fallback na snippet gdy extract < 300 znaków (fix SC3)
  ✓ asyncio.timeout(25) na discovery_loop (fix wisienia)

Dzień 3 — przy pisaniu frontendu:
  ✓ Disable przycisku "Znajdź firmę" podczas requesta (fix SC2 na froncie)
  ✓ Obsługa pustego stanu (gdy loop nie znajdzie firmy)
  ✓ Cleanup presented > 24h przy starcie (fix SC5 — wersja prosta)
```
