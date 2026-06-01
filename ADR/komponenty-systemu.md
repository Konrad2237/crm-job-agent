# Dekompozycja systemu — CRM Job Agent

---

## Komponenty

**1. Discovery Agent**
- **Odpowiedzialność:** Generuje zapytanie do Tavily i wybiera z wyników jeden URL kandydata
- **Wejście:** Lista odwiedzonych domen z Dedup Filter (żeby unikać powtórzeń w zapytaniu)
- **Wyjście:** Jeden URL + nazwa firmy → Page Verifier
- **Wymaga AI:** Tak — musi generować zróżnicowane, kreatywne zapytania po polsku i interpretować wyniki
- **Model:** Haiku 4.5 — proste generowanie zapytań, tanie, szybkie, budżet 20-30$/mies
- **Zależności:** Dedup Filter, Tavily API (zewnętrzne)

---

**2. Page Verifier**
- **Odpowiedzialność:** Pobiera treść strony i klasyfikuje: czy polska + czy AI
- **Wejście:** URL z Discovery Agent, treść strony przez Tavily Extract
- **Wyjście:** pass/fail + krótki opis działalności (np. "chatboty, agenci AI") → Backend Orchestrator
- **Wymaga AI:** Tak — musi rozumieć treść i klasyfikować semantycznie
- **Model:** Haiku 4.5 — binarna klasyfikacja, nie wymaga głębokiego rozumowania
- **Zależności:** Discovery Agent, Tavily Extract API (zewnętrzne)

---

**3. Dedup Filter**
- **Odpowiedzialność:** Sprawdza czy URL/domena była już kiedykolwiek zwrócona użytkownikowi
- **Wejście:** URL z Discovery Agent
- **Wyjście:** Boolean (nowa / już widziana) → Discovery Agent
- **Wymaga AI:** Nie — zwykłe zapytanie SQL do bazy
- **Zależności:** CRM Database

---

**4. Backend Orchestrator**
- **Odpowiedzialność:** Przyjmuje żądania z frontendu i napędza pętlę: szukaj → weryfikuj → pokaż → zapisz
- **Wejście:** HTTP requests z frontendu (klik "znajdź", decyzja użytkownika, dane formularza)
- **Wyjście:** HTTP responses (dane firmy do wyświetlenia, potwierdzenia zapisu)
- **Wymaga AI:** Nie — czysta orkiestracja
- **Zależności:** Discovery Agent, Page Verifier, Dedup Filter, CRM Database

---

**5. CRM Database (Supabase)**
- **Odpowiedzialność:** Przechowuje wszystkie rekordy firm — odwiedzone, pominięte, aplikacje, ręcznie dodane
- **Wejście:** Rekordy z Backend Orchestrator
- **Wyjście:** Dane do Dedup Filter, Dashboard, Manual Entry
- **Wymaga AI:** Nie
- **Zależności:** Brak — fundament całego systemu

---

**6. Company Presenter**
- **Odpowiedzialność:** Wyświetla jedną znalezioną firmę (nazwa + link + opis) i pyta o decyzję użytkownika
- **Wejście:** Dane firmy z Backend Orchestrator
- **Wyjście:** Decyzja użytkownika (wysłałem / pominąłem) → Backend Orchestrator
- **Wymaga AI:** Nie
- **Zależności:** Backend Orchestrator

---

**7. Application Form**
- **Odpowiedzialność:** Zbiera pola CRM gdy użytkownik potwierdził wysłanie CV
- **Wejście:** Decyzja "wysłałem" z Company Presenter + dane wpisane przez użytkownika
- **Wyjście:** Kompletny rekord → Backend Orchestrator → CRM Database
- **Wymaga AI:** Nie
- **Zależności:** Company Presenter, Backend Orchestrator

---

**8. CRM Dashboard**
- **Odpowiedzialność:** Tabela wszystkich zapisanych firm z filtrowaniem po statusie i możliwością edycji
- **Wejście:** Dane z Backend Orchestrator
- **Wyjście:** Akcje użytkownika (zmiana statusu, edycja pól)
- **Wymaga AI:** Nie
- **Zależności:** Backend Orchestrator, CRM Database

---

**9. Manual Entry Form**
- **Odpowiedzialność:** Pozwala ręcznie dodać firmę/ofertę z OLX lub Pracuj.pl bez udziału agenta
- **Wejście:** Dane wpisane przez użytkownika
- **Wyjście:** Nowy rekord w CRM Database
- **Wymaga AI:** Nie
- **Zależności:** Backend Orchestrator, CRM Database

---

## Diagram przepływu danych

```
USER
 │
 │  klik "Znajdź firmę"
 ▼
┌────────────────────────────────────────────────┐
│             FRONTEND  (Vercel)                  │
│                                                 │
│  [6 Company Presenter]                          │
│       │           │                             │
│  "pomiń"    "wysłałem CV"                       │
│       │           │                             │
│       │    [7 Application Form]                 │
│       │           │                             │
│  [8 CRM Dashboard] ◄── [9 Manual Entry Form]   │
└──┬────┴───────────┴────────────────────────────┘
   │              HTTP (wszystkie ścieżki)
   ▼
┌────────────────────────────────────────────────┐
│          BACKEND ORCHESTRATOR (Railway/Python)  │
│                                                 │
│  POST /find        → odpala discovery loop      │
│  POST /skip        → zapisuje "pominięta"       │
│  POST /apply       → zapisuje aplikację         │
│  GET  /companies   → dane do dashboardu         │
│  POST /manual      → ręczny zapis               │
└──────────────────┬─────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────┐
│                  DISCOVERY LOOP                       │
│                                                       │
│  ┌──────────────────────┐                            │
│  │  1. Discovery Agent  │──────► Tavily Search API   │
│  │     (Haiku 4.5)      │◄────── lista URL-i         │
│  └───────────┬──────────┘                            │
│              │  URL kandydat                         │
│              ▼                                       │
│  ┌──────────────────────┐                            │
│  │  3. Dedup Filter     │──────► Supabase            │
│  └───────────┬──────────┘◄────── już widziana?       │
│         nowy │   widziana → wróć, weź następny URL   │
│              ▼                                       │
│  ┌──────────────────────┐                            │
│  │  2. Page Verifier    │──────► Tavily Extract API  │
│  │     (Haiku 4.5)      │◄────── treść strony        │
│  └───────────┬──────────┘                            │
│         pass │   fail → wróć, weź następny URL       │
│              ▼                                       │
│       ✓ firma znaleziona                             │
│         (nazwa, url, opis)                           │
└──────────────────────────────────────────────────────┘
                   │
                   │  zapis po każdej akcji
                   ▼
        ┌──────────────────────┐
        │  5. CRM Database     │
        │     (Supabase)       │
        │                      │
        │  companies           │
        │  ├── status:         │
        │  │   visited         │
        │  │   skipped         │
        │  │   applied         │
        │  │   manual          │
        │  ├── name, url       │
        │  ├── what_they_do    │
        │  ├── position        │
        │  ├── salary          │
        │  ├── email           │
        │  └── created_at      │
        └──────────────────────┘
```

---

## Ścieżka krytyczna vs rozszerzenia

### Ścieżka krytyczna — bez tych komponentów system nie działa

| Komponent | Dlaczego krytyczny |
|---|---|
| Discovery Agent | Bez niego nie ma żadnych firm |
| Page Verifier | Bez niego wracamy do problemu — złe linki, angielskie strony |
| Dedup Filter | Bez niego wracamy do problemu — powtórki |
| Backend Orchestrator | Klej całego systemu |
| CRM Database | Bez persystencji nie ma pamięci między sesjami |
| Company Presenter | Bez interfejsu użytkownik nie może wejść w interakcję |

### Rozszerzenia — system działa bez nich, tylko gorzej

| Komponent | Co traci bez niego |
|---|---|
| Application Form (pełne pola) | MVP może zapisać tylko nazwę + URL; resztę pól dokłada się iteracyjnie |
| CRM Dashboard | Na MVP można patrzeć w Supabase Studio; wygoda, nie funkcjonalność |
| Manual Entry Form | Firmy z OLX można na razie dodawać ręcznie w Supabase; wrócimy do tego po MVP |
