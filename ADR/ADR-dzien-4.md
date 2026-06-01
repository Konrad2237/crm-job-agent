# ADR Dzień 4 — Post-MWS: Manual Entry, Reply Tracking, Edit/Delete, Security

Data: 2026-05-09
Branch: `main` (bezpośrednie pushe — jeden użytkownik, zmiany testowane lokalnie przed każdym pushem)
Status: ukończony, na produkcji

---

## Część I — Dokumentacja techniczna (dla Claude Code)

### Co zostało zbudowane

Cztery niezależne funkcjonalności rozszerzające MWS. Każda była testowana lokalnie przed pushem. Żadna nie dotyka discovery loop ani page_verifier — zmiany wyłącznie w warstwie CRUD i UI.

### Schemat zmienionych plików

```
backend/
│
├── main.py
│   ├── + verify_api_key(x_api_key) → Depends  — sprawdza X-Api-Key header
│   ├── + Depends(verify_api_key) na obu routerach (nie na GET /)
│   └── + "DELETE" w CORS allow_methods (brakowało)
│
├── models/schemas.py
│   ├── ManualCompanyRequest
│   │   └── + what_they_do, position, salary_expectation, contact_email  (były tylko name, url, notes)
│   └── PatchCompanyRequest
│       └── + name, what_they_do  (były tylko status, position, salary, email, notes, reply_*)
│
├── db/client.py
│   ├── + save_manual_company(name, url, domain, data) → dict
│   │   └── INSERT z source="manual", status="applied", applied_at=now
│   └── + delete_company(company_id) → None
│       └── DELETE WHERE id = company_id
│
└── routers/companies.py
    ├── + POST /companies/manual
    │   ├── normalize_domain(url) → sprawdź is_domain_seen → 409 jeśli duplikat
    │   └── save_manual_company(...)
    ├── + DELETE /companies/{company_id}  →  204 No Content
    └── fix: model_dump(exclude_none=True) → model_dump(exclude_unset=True) w PATCH
        # exclude_none usuwało null z payload → nie można było wyczyścić pola przez PATCH

frontend/
│
├── lib/api.ts
│   ├── + const API_SECRET = process.env.NEXT_PUBLIC_API_SECRET
│   ├── apiFetch: dodaje X-Api-Key header gdy API_SECRET ustawiony
│   ├── apiFetch: obsługa 204 No Content (return undefined zamiast res.json())
│   ├── + api.patchCompany(id, data)  — generyczny PATCH
│   ├── + api.deleteCompany(id)       — DELETE → 204
│   └── + api.addManualCompany(data)  — POST /companies/manual
│
├── components/
│   ├── ManualEntryModal.tsx          — nowy
│   │   ├── Pola: name*, url*, what_they_do, position, salary, email, notes
│   │   ├── Walidacja: name i url wymagane (inline przed submittem)
│   │   └── Błędy API (409 duplikat) wyświetlane inline w modalu
│   │
│   ├── ReplyModal.tsx                — nowy
│   │   ├── Pre-fillowany obecnymi wartościami company.reply_status / reply_received
│   │   ├── Dropdown: "" / "rejected" / "interview" / "offer"
│   │   └── Pole tekstowe: reply_received (kiedy/jak, free text)
│   │
│   ├── CompanyEditModal.tsx          — nowy
│   │   ├── Pola: name, what_they_do, status (dropdown), position, salary, email, notes
│   │   ├── Pre-fillowany obecnymi wartościami
│   │   ├── "Usuń firmę" — dwustopniowe potwierdzenie inline (bez osobnego dialogu)
│   │   └── max-h-[90vh] overflow-y-auto — modal nie wychodzi poza ekran
│   │
│   └── CRMTable.tsx                  — rozszerzony
│       ├── + kolumna "Odpowiedź" z badge (rejected=czerwony, interview=niebieski, offer=zielony)
│       ├── + "Ustaw odpowiedź" / "Edytuj" link dla applied rows w kolumnie Odpowiedź
│       ├── + kolumna akcji z "Edytuj" button (otwiera CompanyEditModal)
│       └── + props: onReply?, onEdit?  (optional — tabela działa bez nich)
│
├── app/crm/page.tsx                  — rozszerzony
│   ├── + showModal / modalLoading    — ManualEntryModal
│   ├── + replyCompany / replyLoading — ReplyModal
│   ├── + editCompany / editLoading   — CompanyEditModal
│   ├── + handleManualSubmit()        — POST manual → close + fetchPage(1)
│   ├── + handleReplySubmit()         — PATCH reply fields → close + fetchPage
│   ├── + handleEditSubmit()          — PATCH editable fields → close + fetchPage
│   └── + handleEditDelete()          — DELETE → close + fetchPage
│
└── .env.local                        — nowy (NIE w git)
    └── NEXT_PUBLIC_API_SECRET=...
```

### Decyzje architektoniczne podjęte w Dniu 4

| Decyzja | Wybór | Alternatywa odrzucona | Powód |
|---|---|---|---|
| `exclude_unset=True` w PATCH | unset | `exclude_none=True` | exclude_none uniemożliwiał wyczyszczenie pola przez null — błąd "Brak pól do aktualizacji" gdy payload był `{reply_status: null}` |
| `verify_api_key` jako Depends na routerach | per-router | globalnie na app | `GET /` (health check) musi być dostępny bez klucza — Railway używa go do health probe |
| Pomijanie check gdy `API_SECRET` nie ustawiony | skip | zawsze wymagaj | lokalna dev bez konfiguracji sekretów ma działać out-of-the-box |
| Dwustopniowe usunięcie inline | `confirmDelete` state | osobny modal potwierdzenia | jeden modal zamiast dwóch, mniejszy kod, wystarczy przy jednym użytkowniku |
| `apiFetch` obsługuje 204 | `if (res.status === 204) return undefined` | osobna funkcja dla DELETE | jedno miejsce, zero duplikacji, generyczne rozwiązanie dla każdego 204 w przyszłości |
| `.env.local` nie w git | `.gitignore` (Next.js domyślnie go ignoruje) | commit do repo | sekrety nie trafiają do GitHub |
| Bezpośrednie pushe na main | push bez brancha | branch + PR | jeden użytkownik, każda zmiana testowana lokalnie przed pushem — overhead branchy bez korzyści |

### Błędy napotkane w Dniu 4

**B1 — `exclude_none=True` blokuje czyszczenie pól przez null**
- Przyczyna: `model_dump(exclude_none=True)` w PATCH usuwa null z payload → pusty dict → 400 "Brak pól do aktualizacji"
- Scenariusz: użytkownik ustawia odpowiedź "Odrzucono", potem chce wrócić do "Brak odpowiedzi" — niemożliwe
- Fix: `model_dump(exclude_unset=True)` — wyklucza pola których nie przesłano, ale zachowuje explicit null
- Wniosek: PATCH zawsze `exclude_unset`, nie `exclude_none`

**B2 — `apiFetch` crashuje na 204 No Content**
- Przyczyna: `res.json()` na pustej odpowiedzi DELETE rzuca `SyntaxError: Unexpected end of JSON input`
- Fix: `if (res.status === 204) return undefined as T`
- Wniosek: każdy nowy endpoint zwracający 204 jest obsługiwany automatycznie

**B3 — CORS blokuje DELETE z przeglądarki**
- Przyczyna: `allow_methods=["GET", "POST", "PATCH"]` — DELETE nie było na liście
- Fix: dodanie `"DELETE"` do listy
- Wniosek: przy dodawaniu nowej metody HTTP zawsze sprawdź CORS w `main.py`

### Stan po Dniu 4

Aplikacja kompletna do codziennego użytku. Backend zabezpieczony X-Api-Key. Wszystkie CRUD operacje dostępne z UI.

Pozostałe optymalizacje (nie blokują użycia):
- Token limit: 6000 → 2000-3000 znaków (`discovery_loop.py`)
- Heurystyczny pre-filter (polskie znaki / domena .pl) przed wywołaniem Haiku
- Notatki (`notes`) niewidoczne w CRM table — pole istnieje w bazie, można edytować przez modal, ale tabela go nie pokazuje

---

## Część II — Podsumowanie dla Konrada

### Co zbudowaliśmy

Cztery rzeczy które brakowały do wygodnego codziennego użytku:

**1. Ręczne dodawanie firm** — przycisk "+ Dodaj ręcznie" w CRM. Klikasz, wypełniasz formularz (nazwa, URL, czym się zajmuje, stanowisko, finanse, email, notatki), zapisujesz. Firma trafia od razu do tabeli ze statusem "Aplikacja wysłana". Jeśli firma z tą domeną już jest w bazie — dostaniesz błąd. Przydatne gdy znajdziesz firmę samodzielnie na OLX czy Pracuj.pl.

**2. Śledzenie odpowiedzi** — w tabeli CRM, przy każdej wysłanej aplikacji, pojawia się kolumna "Odpowiedź". Klikasz "+ Ustaw odpowiedź", wybierasz: Odrzucono / Zaproszono na rozmowę / Oferta pracy, wpisujesz kiedy i jak dostałeś odpowiedź. Status pojawia się jako kolorowy badge w tabeli.

**3. Edycja i usuwanie firm** — przy każdym wierszu w tabeli przycisk "Edytuj". Możesz zmienić dowolne pole albo usunąć firmę. Usunięcie jest dwustopniowe (żeby nie usunąć przez przypadek). Ważne: jeśli usuniesz firmę, agent może ją znaleźć znowu przy kolejnym wyszukiwaniu.

**4. Zabezpieczenie backendu** — URL Railway jest teraz chroniony hasłem (`crm-klucz-2026`). Każdy request z frontendu wysyła to hasło w nagłówku. Bez hasła backend zwraca 401. Strona główna backendu (`/`) pozostaje otwarta — Railway potrzebuje jej do sprawdzenia czy serwer działa.

### 3 bugi które naprawiliśmy po drodze

1. **Czyszczenie odpowiedzi nie działało** — ustawienie "Brak odpowiedzi" po wcześniejszym odrzuceniu zwracało błąd. Fix: zmiana jednego parametru w obsłudze PATCH.
2. **Usuwanie crashowało frontend** — DELETE zwraca pustą odpowiedź, a kod próbował ją parsować jako JSON. Fix: specjalna obsługa odpowiedzi 204.
3. **DELETE blokowany przez CORS** — przeglądarka blokowała żądania usunięcia. Fix: dodanie DELETE do listy dozwolonych metod HTTP.

### Następne kroki

Aplikacja działa w pełni. To co zostało to optymalizacje, nie nowe funkcjonalności:

- **Tańsze wyszukiwanie** — jedno kliknięcie "Znajdź firmę" zużywa do 6000 znaków tekstu strony. Można bezpiecznie obciąć do 2000-3000 bez straty jakości — Haiku i tak decyduje na podstawie pierwszego ekranu strony, nie całości.
- **Szybszy pre-filter** — zanim zapytamy Haiku "czy to polska firma AI?", możemy tanio sprawdzić czy domena jest .pl albo czy strona ma polskie znaki. Angielskie strony odpadają bez kosztowania tokena.
- **Notatki w tabeli** — pole "notatki" można edytować przez modal ale tabela go nie pokazuje. Prosta zmiana w CRMTable jeśli zajdzie potrzeba.
