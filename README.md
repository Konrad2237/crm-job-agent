# CRM Job Agent

Narzędzie do automatycznego wyszukiwania polskich firm AI i śledzenia aplikacji o pracę.

---

## Spis treści

1. [Co to robi](#co-to-robi)
2. [Funkcjonalności](#funkcjonalności)
3. [Technologie](#technologie)
4. [Jak to działa](#jak-to-działa)
5. [Struktura projektu](#struktura-projektu)
6. [Czego się nauczyłem](#czego-się-nauczyłem)
7. [Autor](#autor)

---

## Co to robi

Szukanie polskich firm AI ręcznie zajmuje dużo czasu i daje słabe wyniki — ChatGPT podaje nieistniejące linki, wyszukiwarka zwraca angielskie strony i te same portale w kółko. Jednocześnie notatnik z firmami szybko staje się bezużyteczny: brak dat, statusów i linków sprawia że nie wiadomo gdzie już wysłałem CV, a gdzie nie.

CRM Job Agent rozwiązuje oba problemy. Narzędzie samo przeszukuje internet i prezentuje jedną polską firmę AI przy każdym kliknięciu — z linkiem do strony, bez powtórzeń. Użytkownik decyduje czy aplikuje. Każda decyzja trafia do CRM: firma, stanowisko, finanse, odpowiedź rekrutera.

Narzędzie dla jednej osoby — bez logowania, bez kont, bez multi-user.

---

## Funkcjonalności

**Discovery — wyszukiwanie firm**
Losuje zapytanie z puli 24 fraz branżowych, wyszukuje przez Google i pokazuje jedną nową polską firmę AI. Każda firma zapisywana jest po domenie — ta sama firma nie pojawi się dwa razy, nawet po restarcie. Jeśli użytkownik zamknął przeglądarkę przed podjęciem decyzji, firma wraca przy następnym kliknięciu zamiast zaginąć. Po 24h niepodjęta decyzja jest automatycznie oznaczana jako pominięcie.

**Karta firmy**
Wyświetla nazwę i link do strony. Dwa przyciski: "Pomiń" (firma nie wróci) i "Wysłałem CV" (otwiera formularz aplikacji).

**Formularz aplikacji**
Zbiera stanowisko, oczekiwania finansowe, e-mail kontaktowy i notatki. Dwa tryby zapisu: "Zapisz" (wraca do ekranu głównego) i "Zapisz i szukaj dalej" (zapisuje aplikację i natychmiast wyszukuje kolejną firmę).

**CRM Dashboard**
Tabela wszystkich firm z paginacją (20 rekordów na stronę). Filtrowanie po statusie z licznikami: aplikacje, pominięte, pokazane. Wyszukiwanie po nazwie lub domenie — działa na całej bazie, nie tylko na bieżącej stronie. Sortowanie po nazwie firmy, statusie i dacie. Pasek statystyk z liczbą aplikacji i odsetkiem odpowiedzi.

**Ręczne dodawanie**
Okno "+ Dodaj ręcznie" dla firm znalezionych samodzielnie na OLX, Pracuj.pl lub gdzie indziej. Firma trafia od razu ze statusem "wysłano CV" — formularz zakłada że użytkownik już aplikował. Jeśli domena już jest w bazie, formularz zwraca błąd zamiast tworzyć duplikat.

**Śledzenie odpowiedzi**
Dla każdej aplikacji można ustawić status odpowiedzi: Odrzucono / Zaproszono na rozmowę / Oferta. Kolorowe etykiety w tabeli. Pole tekstowe na treść lub datę odpowiedzi.

**Edycja i usuwanie**
Każdy rekord edytowalny przez okno dialogowe — wszystkie pola, łącznie ze statusem. Usunięcie wymaga potwierdzenia. Usuniętą firmę narzędzie może znaleźć ponownie.

**Zabezpieczenie API**
Wszystkie requesty między frontendem a backendem wymagają nagłówka `X-Api-Key` ze wspólnym sekretem. Bez klucza backend zwraca 401. Health check `GET /` pozostaje otwarty — Railway używa go do sprawdzania czy serwer działa.

---

## Technologie

| Narzędzie | Wersja | Do czego |
|---|---|---|
| Next.js | 16.2.6 | Frontend — App Router, dwie strony: Discovery i CRM |
| React | 19.2.4 | Komponenty UI |
| Tailwind CSS | 4.x | Stylowanie |
| TypeScript | 5.x | Typowanie frontendu |
| Python | 3.12 | Backend |
| FastAPI | ≥0.111.0 | REST API, CORS, auth middleware |
| LangChain + langchain-anthropic | ≥0.2.0 | Wywołania Claude z automatycznym LangSmith tracingiem |
| Claude Haiku 4.5 | claude-haiku-4-5-20251001 | Klasyfikacja strony: polska firma AI tak/nie (structured output) |
| SerpAPI | ≥2.4.2 | Google Search — wyszukiwanie firm (gl=pl, hl=pl) |
| httpx + BeautifulSoup4 | ≥0.27.0 / ≥4.12.0 | Pobieranie i parsowanie treści stron jako fallback |
| Supabase | ≥2.5.0 | PostgreSQL — baza danych, async client |
| Railway | — | Hosting backendu (~$5/mies) |
| Vercel | — | Hosting frontendu (Hobby plan, bezpłatny) |
| LangSmith | — | Monitorowanie wywołań LLM — tokeny, czas, cache (opcjonalne) |

---

## Jak to działa

### Flow wyszukiwania (POST /find)

```
Klik "Znajdź firmę"
  │
  ├─ Czy jest firma w statusie "presented" z ostatnich 24h?
  │   TAK → zwróć ją (użytkownik nie podjął decyzji)
  │   NIE → wyczyść stale "presented" starsze niż 24h → ustaw na "skipped"
  │
  ▼
generate_query() — losowy wybór z 24 hardkodowanych fraz branżowych
np. "polska firma RAG baza wiedzy LLM wdrożenia"
  │
  ▼
SerpAPI Google Search (gl=pl, hl=pl, num=5)
  │
  dla każdego z 5 wyników:
  ├─ normalize_domain() — stripuje www., wyciąga domenę
  ├─ batch dedup — jedno zapytanie SQL dla wszystkich 5 domen naraz
  ├─ blocklist domen (media, social, portale pracy, uczelnie…)
  ├─ pre-filter: domena .pl lub polskie znaki diakrytyczne w snippecie?
  ├─ pre-filter: URL lub tytuł wygląda jak artykuł / ranking / lista?
  ├─ pre-filter: snippet jednoznacznie wyklucza firmę AI?
  │
  ├─ snippet ≥150 znaków → użyj snippetu (bez dodatkowego fetcha)
  └─ snippet <150 znaków → pobierz stronę (httpx + BS4, timeout 5s)
                            fallback na snippet jeśli fetch zawiedzie
  │
  ▼
Claude Haiku 4.5 — structured output, max 2000 znaków treści
{is_polish: bool, is_ai_company: bool}
  │
  ├─ PASS → save_company() status="presented" → zwróć firmę
  │          frontend: wyświetl kartę → decyzja użytkownika
  │          "Wysłałem CV" → formularz → POST /apply → auto POST /find → kolejna firma
  └─ FAIL → save_skipped_domain() → sprawdź następny wynik
  │
  brak pasującego wyniku → HTTP 404 → "Spróbuj ponownie"
```

Jedno wywołanie `/find` = jedno zapytanie Google, maksymalnie 5 kandydatów. Jeśli żaden nie przejdzie filtrów, backend zwraca 404 — użytkownik klika ponownie. To świadoma decyzja: szybkie "spróbuj ponownie" zamiast kolejnych zapytań w tej samej sesji.

Cały `find_company()` ma twardy limit `asyncio.timeout(55s)`.

### Kluczowe decyzje techniczne

**LLM tylko do klasyfikacji, nie do orkiestracji**
Wcześniejsze podejście (agentic loop gdzie LLM sam decyduje kiedy skończyć) skończyło się na 800k tokenów bez odpowiedzi. Tutaj pętla jest w Pythonie. Claude Haiku odpowiada tylko na jedno pytanie: "czy ta strona to polska firma AI?". Logika "co dalej" należy wyłącznie do kodu.

**Generowanie zapytań bez LLM**
Zapytania były początkowo generowane przez Haiku z historią poprzednich zapytań. W praktyce historia blokowała całe nisze — po jednej aplikacji do firmy HR AI narzędzie przestawało szukać w tej branży. Rozwiązanie: 24 precyzyjne frazy branżowe, `random.choice()` przy każdym wywołaniu. Prostsze, przewidywalne, zero kosztu tokenów.

**Snippet jako priorytet, fetch strony jako fallback**
Snippet z Google Search wystarczy do klasyfikacji dla większości firm — Google już go przygotował. Fetch strony uruchamia się tylko gdy snippet ma mniej niż 150 znaków. Oszczędza 3–8 sekund na kandydacie.

**Dedup na znormalizowanej domenie**
`www.firma.pl` i `firma.pl` to ta sama firma. `normalize_domain()` stripuje prefiks przed każdym zapisem i sprawdzeniem. Batch query — jedno zapytanie SQL dla całej partii kandydatów zamiast osobnego dla każdego.

**Trzy warstwy obrony przed duplikatami**
1. Wyłączony przycisk podczas requesta — zapobiega race condition po stronie użytkownika
2. `UNIQUE(domain)` w bazie danych — gwarantuje unikalność na poziomie DB
3. `ON CONFLICT (domain) DO NOTHING` przy każdym INSERT — obsługuje przypadek gdy dwa requesty dotrą jednocześnie

**Truncacja treści do 2000 znaków**
Blog z 200 artykułami może mieć 70k tokenów. Przy normalnym koszcie $0.001 za weryfikację, taka strona kosztuje $0.056 — 56× więcej, z czasem odpowiedzi 8–15 sekund. Nagłówek strony i sekcja usług mieszczą się w pierwszych 2000 znakach — wszystko co Haiku potrzebuje do klasyfikacji. Artykuły zaczynają się za tym progiem.

---

## Struktura projektu

```
crm-job-agent/
│
├── backend/
│   ├── main.py                   # FastAPI app, CORS, middleware X-Api-Key
│   │
│   ├── core/
│   │   ├── discovery_loop.py     # Pętla wyszukiwania — filtry, SerpAPI, fetch, Haiku
│   │   ├── page_verifier.py      # Claude Haiku: is_polish + is_ai_company
│   │   └── query_generator.py    # random.choice z 24 fraz branżowych
│   │
│   ├── db/
│   │   └── client.py             # Supabase async client, normalize_domain, safe_db_call
│   │
│   ├── routers/
│   │   ├── discovery.py          # POST /find  /skip  /apply
│   │   └── companies.py          # GET /companies  /stats  POST /manual  PATCH  DELETE
│   │
│   └── models/
│       └── schemas.py            # Pydantic modele request/response
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx            # Root layout — nawigacja Odkrywanie / CRM
│   │   ├── page.tsx              # Discovery — maszyna stanów: idle → found → applying
│   │   └── crm/
│   │       └── page.tsx          # CRM Dashboard — paginacja, filtry, search, sort, okna dialogowe
│   │
│   ├── components/
│   │   ├── CompanyCard.tsx       # Karta firmy + przyciski Pomiń / Wysłałem CV
│   │   ├── ApplicationForm.tsx   # Formularz aplikacji z dwoma trybami zapisu
│   │   ├── CRMTable.tsx          # Tabela z sortowaniem, etykietami statusów, kopiowaniem e-maila
│   │   ├── ManualEntryModal.tsx  # Okno ręcznego dodawania firmy
│   │   ├── ReplyModal.tsx        # Okno odpowiedzi od rekrutera
│   │   └── CompanyEditModal.tsx  # Okno edycji i usunięcia z potwierdzeniem
│   │
│   └── lib/
│       └── api.ts                # Typowany klient HTTP — X-Api-Key header, obsługa błędów
│
├── Procfile                      # Railway start command
├── requirements.txt              # Zależności Pythona
└── .env.example                  # Szablon zmiennych środowiskowych
```

---

## Czego się nauczyłem

**Agentic loops bez kontroli tokenów to pułapka**
Pierwsza wersja używała LangChain AgentExecutor gdzie LLM decydował kiedy skończyć szukanie. Skończyło się na 800k tokenów i braku odpowiedzi. Wniosek: jeśli LLM kontroluje pętlę, koszt jest nieprzewidywalny. Pętla musi być w kodzie — LLM odpowiada tylko na jedno, konkretne pytanie.

**Prostota wygrywa nad elegancją**
Generowanie zapytań przez Haiku z historią poprzednich zapytań brzmiało sensownie. W praktyce historia blokowała całe nisze. Zastąpiłem to `random.choice()` z 24 frazami. Prostsze, przewidywalne, zero kosztu tokenów.

**Pre-filtry są tańsze niż LLM**
Zamiast wysyłać każdy wynik Google do Haiku, najpierw uruchamiam serię sprawdzeń w czystym Pythonie: lista zablokowanych domen, polskie znaki, wzorce URL artykułów, frazy wykluczające. Haiku dostaje tylko kandydatów którzy przeszli wszystkie filtry — w praktyce 1–3 wywołania zamiast 5 na każde zapytanie.

**Race conditions pojawiają się w nieoczekiwanych miejscach**
Podwójne kliknięcie przy wolnym połączeniu — dwa równoległe POST /find — oba sprawdzają dedup jednocześnie, oba widzą domenę jako nową, oba próbują zapisać. Rozwiązanie wymagało trzech warstw: wyłączony przycisk, UNIQUE constraint w DB, ON CONFLICT DO NOTHING przy INSERT.

**Status "pokazana ale bez decyzji" to realny problem**
Użytkownik widzi firmę, otwiera link, zamyka laptopa. Firma ma status "presented" — dedup ją złapie przy kolejnym wywołaniu i nie wróci. Stracona bez śladu. Rozwiązanie: przy każdym POST /find sprawdź najpierw czy jest nierozstrzygnięta firma z ostatnich 24h i zwróć ją ponownie.

**Truncacja treści to decyzja produktowa, nie ograniczenie techniczne**
Blog firmowy z artykułami może mieć 70k tokenów. Przy cenie Haiku jedno takie wywołanie kosztuje 56× więcej niż normalne i trwa 8–15 sekund zamiast 1–2. Nagłówek strony i sekcja usług mieszczą się w pierwszych 2000 znakach. Artykuły zaczynają się za tym progiem — nie są potrzebne do klasyfikacji.

---

## Autor

**Konrad Pochwała**

- GitHub: [DO UZUPEŁNIENIA]
- LinkedIn: [DO UZUPEŁNIENIA]
