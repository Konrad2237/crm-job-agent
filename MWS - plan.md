# MWS — Minimum Working Solution

---

## Komponenty w MWS

### Co wchodzi i dlaczego

| Komponent | W MWS? | Uzasadnienie |
|---|---|---|
| Discovery Loop | TAK | Serce systemu — bez tego nie ma nic |
| Page Verifier | TAK | Rozwiązuje prawdziwy problem: złe linki, angielskie strony |
| Dedup Filter | TAK | Rozwiązuje prawdziwy problem: powtórki |
| Backend API (3 endpointy) | TAK | Klej systemu, minimalne 3: /find, /skip, /apply |
| Supabase DB | TAK | Persystencja — bez tego brak pamięci między sesjami |
| Company Presenter (frontend) | TAK | Bez UI nie możesz wejść w interakcję z agentem |
| Formularz aplikacji (podstawowy) | TAK | Uproszczony — tylko stanowisko i notatki |

### Co jest pominięte i dlaczego

| Komponent | Pominięty | Zamiennik na MWS |
|---|---|---|
| CRM Dashboard | TAK | Supabase Studio — masz tam tabelę gotową, przeglądasz dane bezpośrednio |
| Manual Entry Form | TAK | Wpisujesz ręcznie przez Supabase Studio — rzadko potrzebne na etapie testowania |
| Pełne pola CRM (salary, email, reply_status) | TAK | MWS zbiera tylko: stanowisko + notatki. Reszta pól jest w DB, użytkownik doda przez Studio |
| LangSmith monitoring | TAK | Przydatne, ale MWS ma działać — debugujesz logami na razie |
| Filtrowanie / sortowanie w UI | TAK | Supabase Studio ma filtry |
| Edycja rekordów w UI | TAK | Supabase Studio |

### Uproszczenia

1. **Formularz aplikacji** zbiera tylko 2 pola: `position` i `notes`. Reszta (salary, email) jest nullable w DB — dodasz przez Studio lub po wdrożeniu CRM Dashboard.

2. **Frontend** to jedna strona HTML — brak routingu, brak nawigacji do dashboardu. Tylko pętla: znajdź → zdecyduj → znajdź.

3. **Brak autentykacji** — aplikacja działa na Railway bez żadnego logowania. Single user, URL wiesz tylko Ty.

4. **Error handling** minimalny — jeśli agent nic nie znajdzie, pokazujesz komunikat "Spróbuj ponownie". Nie obsługujesz edge case'ów.

5. **Tavily Extract** tylko jeśli snippet z search nie wystarczy do klasyfikacji. Oszczędza kredyty.

---

## Plan tygodniowy

### Dzień 1 — Fundament backendu

**Co budujesz:**
- Supabase: utwórz tabelę `companies` (SQL z pliku architektury)
- FastAPI: `main.py` z CORS, health check `GET /`
- `db/client.py`: dwie funkcje — `is_domain_seen(domain)` i `save_company(...)`
- `query_generator.py`: Haiku generuje jedno polskie zapytanie do Tavily, przyjmuje listę poprzednich zapytań żeby się nie powtarzał
- Test manualny: wywołujesz `query_generator` z terminala, sprawdzasz czy zwraca sensowne zapytania

**Co masz na koniec dnia:**
Backend odpowiada na `GET /` (health check), Supabase ma tabelę, możesz ręcznie wywołać generator zapytań i widzisz wyniki w terminalu.

---

### Dzień 2 — Discovery loop + endpointy

**Co budujesz:**
- `page_verifier.py`: Haiku klasyfikuje stronę — przyjmuje treść, zwraca `{is_valid: bool, what_they_do: str}`; testujesz na 3 ręcznie wybranych URL-ach (jedna polska AI, jedna angielska, jedna niezwiązana z AI)
- `discovery_loop.py`: pełna pętla Python — generuj zapytanie → Tavily search → dedup → extract → verify → zapisz i zwróć
- Endpointy:
  - `POST /find` → odpala loop, zwraca firmę lub 404
  - `POST /companies/{id}/skip` → status = skipped
  - `POST /companies/{id}/apply` → zapisuje position + notes, status = applied
- Test manualny przez curl lub Postman: `POST /find` zwraca firmę, `POST /skip` i `/apply` działają

**Co masz na koniec dnia:**
Możesz przez terminal/Postman wywołać `/find` i dostać prawdziwą polską firmę AI. Pomiń lub zaaplikuj — dane lądują w Supabase. Zero frontendu, ale core systemu działa.

---

### Dzień 3 — Frontend + deployment + test end-to-end

**Co budujesz:**
- Next.js: strona główna z przyciskiem "Znajdź firmę"
- `CompanyCard`: wyświetla nazwę, link (otwiera w nowej karcie), opis działalności
- Dwa przyciski: "Wysłałem CV" | "Pomiń"
- Po "Wysłałem CV": formularz inline (stanowisko, notatki) + przycisk "Zapisz i szukaj dalej"
- Po "Pomiń" lub "Zapisz": automatycznie odpalasz kolejne `/find`
- Deployment: backend na Railway (nixpacks wykryje Python), frontend na Vercel
- Konfiguracja env vars w obu serwisach
- Test end-to-end: klikasz "Znajdź firmę" na produkcji, przechodzisz przez 5 firm

**Co masz na koniec dnia:**
Działający system na produkcji. Klikasz przycisk → widzisz firmę → decydujesz → dane w Supabase → widzisz kolejną firmę. MWS gotowe.

---

## Kryteria sukcesu MWS

1. **Klikam "Znajdź firmę" i w ciągu 30 sekund widzę firmę** — nie spinner przez 3 minuty, nie błąd 500.

2. **Ta sama firma nigdy się nie powtarza** — po 10 kliknięciach żadna firma nie wróciła drugi raz, nawet po odświeżeniu strony.

3. **Linki faktycznie działają** — z 5 kolejnych firm każda strona się otwiera i jest po polsku.

4. **Po kliknięciu "Wysłałem CV" dane są w Supabase** — wchodzę w Studio, widzę rekord ze statusem `applied`, wypełnionym polem position.

5. **Po kliknięciu "Pomiń" firma nie wraca** — zamykam przeglądarkę, wracam następnego dnia, ta sama firma nie pojawia się ponownie.

---

## Ścieżka od MWS do pełnego systemu

### Etap 2 — CRM Dashboard (po MWS)
**Co dodajesz:** Strona `/crm` z tabelą wszystkich firm, filtrowanie po statusie, edycja statusu inline (rozwijana lista applied/interview/rejected/no_reply).

**Dlaczego teraz:** Masz już dane w Supabase, ale Supabase Studio nie jest wygodne do codziennego przeglądania. Dashboard zastępuje Studio.

**Szacowany czas:** 2-3 dni

---

### Etap 3 — Pełne pola CRM (razem z etapem 2 lub po)
**Co dodajesz:** Formularz aplikacji zbiera wszystkie pola: salary_expectation, contact_email, reply_received, reply_status. Edycja tych pól w dashboardzie.

**Dlaczego teraz:** Masz dane z kilku tygodni używania MWS — wiesz które pola faktycznie wypełniasz, a które są zbędne.

**Szacowany czas:** 1 dzień

---

### Etap 4 — Manual Entry Form
**Co dodajesz:** Modal "+ Dodaj ręcznie" w dashboardzie do dodawania firm z OLX/Pracuj.pl bez Supabase Studio.

**Dlaczego teraz:** Po etapie 2 masz dashboard — naturalnie dokłada się tam formularz ręcznego dodawania.

**Szacowany czas:** 1 dzień

---

### Etap 5 — LangSmith monitoring
**Co dodajesz:** `LANGSMITH_TRACING=true` w Railway env vars. Sprawdzasz dashboard czy tokeny nie rosną nieoczekiwanie.

**Dlaczego teraz:** Opcjonalne — przydatne jak zauważysz że rachunki rosną albo agent zwraca dziwne wyniki.

**Szacowany czas:** 2 godziny

---

### Podsumowanie harmonogramu

| Etap | Co daje | Czas |
|---|---|---|
| MWS (dni 1-3) | Działający discovery + podstawowy zapis | 3 dni |
| Etap 2: CRM Dashboard | Przeglądanie i edycja danych w UI | 2-3 dni |
| Etap 3: Pełne pola | Kompletny CRM zamiast notatnika | 1 dzień |
| Etap 4: Manual Entry | OLX/Pracuj.pl bez Supabase Studio | 1 dzień |
| Etap 5: Monitoring | Kontrola kosztów i jakości | 2 godziny |
| **Łącznie** | **Pełny system** | **~8-9 dni** |
