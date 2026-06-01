# Architecture Decision Records — CRM Job Agent

---

## ADR-001

**TYTUŁ:** Wybór architektury systemu
**NUMER:** ADR-001
**STATUS:** Zaakceptowana
**DATA:** 2026-05-08

### KONTEKST

System musi obsłużyć jeden główny przepływ: użytkownik klika przycisk → backend odpala discovery loop → zwraca firmę → użytkownik decyduje → dane lądują w bazie. Mamy tydzień na budowę MWS, jeden użytkownik, budżet $20-30/mies. Musimy podjąć tę decyzję teraz bo determinuje strukturę katalogów, sposób deploymentu i ile czasu zajmie setup.

### ROZWAŻANE OPCJE

**Opcja A: Monolit**
Jeden proces FastAPI na Railway obsługuje wszystko: discovery loop, weryfikację stron, zapis do bazy, wszystkie endpointy API.

- Zalety: jeden deployment, zero komunikacji między serwisami, łatwe debugowanie (jeden log), minimalny czas setup, Railway obsługuje to natywnie
- Wady: jeden wolny request może zablokować inne (ale przy jednym użytkowniku to nieistotne), trudniej skalować w przyszłości

**Opcja B: Mikroserwisy**
Osobne serwisy: `discovery-service`, `verifier-service`, `api-gateway`. Komunikują się przez HTTP lub kolejkę.

- Zalety: każdy serwis można skalować niezależnie, izolacja błędów
- Wady: 3 osobne deploymenty na Railway, sieć między serwisami, 3× setup env vars, 3× więcej kodu orkiestrującego, tydzień to za mało żeby to sensownie postawić

**Opcja C: Serverless (Vercel Functions)**
Backend jako serverless functions na Vercel. Zero stałego procesu.

- Zalety: zero kosztów gdy nieużywane, skaluje automatycznie
- Wady: cold start 1-3 sekundy na każde wywołanie, discovery loop trwa ~15-30 sek (limit timeout Vercel Functions = 10 sek na Hobby), trzeba by płacić za Pro plan ($20/mies tylko za Vercel)

### DECYZJA

Wybraliśmy **Opcję A: Monolit**.

Jeden użytkownik, prosty przepływ danych, tydzień na MVP. Mikroserwisy i serverless rozwiązują problemy skali których nie mamy. Monolit na Railway da się postawić w godzinę i debugować przez jeden terminal. Serverless odpada technicznie — discovery loop przekracza limity timeout.

### KONSEKWENCJE

**Pozytywne:**
- Setup backendu to jedno `railway up` i kilka env vars
- Cały discovery loop w jednym pliku, łatwo śledzić przepływ
- Jeden log, jeden deployment, jedna konfiguracja

**Negatywne:**
- Discovery loop blokuje wątek przez ~10-20 sek — obsłużymy przez `async/await` w FastAPI + Tavily async client
- Jeśli kiedykolwiek będzie wielu użytkowników, będzie potrzebna refaktoryzacja

**Migracja:**
Monolit można rozciąć na mikroserwisy gdy zajdzie potrzeba — interfejsy API pozostają bez zmian, wystarczy przenieść moduły do osobnych serwisów i dodać HTTP client między nimi. Koszt migracji: 2-3 dni.

---

## ADR-002

**TYTUŁ:** Wybór modelu AI do poszczególnych zadań
**NUMER:** ADR-002
**STATUS:** Zaakceptowana
**DATA:** 2026-05-08

### KONTEKST

System wykonuje dokładnie dwa zadania wymagające AI:
1. Generowanie zapytania wyszukiwania do Tavily (np. "firma AI automatyzacje Polska")
2. Klasyfikacja treści strony: czy jest po polsku i czy firma zajmuje się AI

Budżet $20-30/mies pokrywa Tavily ($30 Starter = 10k kredytów) i LLM. Musimy wybrać model teraz — determinuje koszty i czy mieścimy się w budżecie.

### ROZWAŻANE OPCJE

**Opcja A: Claude Haiku 4.5 do obu zadań**
Najtańszy model z rodziny Claude 4.x. ~$0.0008/1K tokenów input, ~$0.004/1K output.

- Zalety: najniższy koszt, szybki (~1 sek odpowiedź), w zupełności wystarcza do prostej klasyfikacji i generowania krótkich zapytań
- Wady: przy bardzo niejednoznacznych stronach może się mylić częściej niż większy model

**Opcja B: Claude Sonnet 4.6 do obu zadań**
Średni model. ~$0.003/1K tokenów input, ~$0.015/1K output — około 4× droższy od Haiku.

- Zalety: lepsza rozumienie niuansów, mniej błędów klasyfikacji
- Wady: przy 100 kliknięciach/mies worst case ~$6-8 tylko na LLM, plus Tavily $30 = przekracza budżet; overkill do zadań na poziomie "czy ta strona jest po polsku"

**Opcja C: Haiku do generowania zapytań, Sonnet do weryfikacji stron**
Haiku tam gdzie zadanie jest mechaniczne (query generation), Sonnet tam gdzie potrzeba rozumowania (page classification).

- Zalety: optymalny balans jakość/koszt
- Wady: dwa modele = dwa zestawy promptów do utrzymania, ~2× droższe od samego Haiku, trudniejsze debugowanie

### DECYZJA

Wybraliśmy **Opcję A: Claude Haiku 4.5 do obu zadań**.

Oba zadania są klasyfikacyjne i krótkie. Generowanie zapytania to wyprodukowanie jednego zdania po polsku. Weryfikacja strony to dwie odpowiedzi tak/nie + krótki opis. Haiku radzi sobie z tym bez problemu. Sonnet byłby zasadny gdybyśmy analizowali skomplikowane dokumenty lub prowadzili wieloetapowe rozumowanie — tutaj nie ma takiej potrzeby. Koszt worst case (100 kliknięć/mies): ~$1.50 na LLM. Zostaje ~$0-1.50 wolnego budżetu przy założeniu Tavily Starter $30.

### KONSEKWENCJE

**Pozytywne:**
- Koszt LLM marginalny (~$1-2/mies przy regularnym używaniu)
- Haiku jest szybki — weryfikacja strony trwa ~0.8-1.5 sek
- Jeden model = jeden zestaw promptów do utrzymania i testowania

**Negatywne:**
- Haiku może przepuścić stronę angielską jeśli ma dużo polskich słów w meta-tagach (ryzyko niskie)
- Może sklasyfikować firmę jako AI jeśli mają jeden artykuł blogowy o AI, a nie faktycznie oferują usługi AI — mitygujemy promptem który wymaga weryfikacji usług, nie treści bloga

**Migracja:**
Podmiana modelu to zmiana jednej stałej `MODEL_NAME = "claude-haiku-4-5-20251001"` w `config.py`. Jeśli jakość klasyfikacji okaże się niewystarczająca po tygodniu używania, upgrade do Sonnet to 5 minut i jedno env var.

---

## ADR-003

**TYTUŁ:** Strategia obsługi błędów i pomyłek modelu AI
**NUMER:** ADR-003
**STATUS:** Zaakceptowana
**DATA:** 2026-05-08

### KONTEKST

Model AI może się mylić na dwa sposoby:
- **False positive:** przepuszcza firmę która jest angielska albo nie zajmuje się AI → użytkownik traci 30 sekund klikając w zły link
- **False negative:** odrzuca dobrą polską firmę AI → użytkownik nigdy jej nie zobaczy

Dodatkowo mogą wystąpić błędy techniczne: Tavily Extract zwróci pustą stronę, Anthropic API zwróci 429/500, strona będzie za duża do przetworzenia. Musimy podjąć tę decyzję teraz bo wpływa na strukturę discovery_loop.py i page_verifier.py.

### ROZWAŻANE OPCJE

**Opcja A: Pełne zaufanie do modelu — brak dodatkowych zabezpieczeń**
Agent klasyfikuje, wynik przyjmujemy bez weryfikacji. Błędy API: natychmiastowy wyjątek.

- Zalety: najprostszy kod, zero dodatkowej logiki
- Wady: jedna pomyłka modelu lub jeden błąd sieci = crash całego zapytania; false positive kosztuje użytkownika czas i uwagę; false negative bezpowrotnie gubi firmy

**Opcja B: Heurystyczny pre-filter + AI jako finalna weryfikacja**
Przed wywołaniem modelu sprawdzamy prostymi regułami: czy domena jest .pl, czy w treści strony są polskie znaki diakrytyczne (ą, ę, ó, ś, ź, ż), czy Tavily zwrócił niepustą treść. Jeśli pre-filter odpada — pomijamy URL bez kosztowania tokena. AI wywołujemy tylko dla URL-i które przeszły pre-filter.

- Zalety: tańsze (część URL-i odpada przed wywołaniem AI), szybsze, logika językowa jest deterministyczna
- Wady: heurystyka może odrzucić stronę z domeną .com która jest polską firmą (np. acmeai.com prowadzona przez Polaków)

**Opcja C: Retry z exponential backoff + confidence score od modelu**
Model zwraca ocenę pewności (1-5), niskie wyniki trafiają do "kolejki wątpliwych". Błędy API: 3 próby z rosnącym opóźnieniem.

- Zalety: inteligentna obsługa niepewności
- Wady: znacznie bardziej skomplikowana implementacja, prompt musi być dłuższy, Claude nie zawsze jest skalibrowany w confidence scores, kolejka wątpliwych wymaga dodatkowego UI

### DECYZJA

Wybraliśmy **Opcję B: Heurystyczny pre-filter + AI jako finalna weryfikacja**, z elementami retry z Opcji C dla błędów technicznych.

Konkretna implementacja:

```
Pre-filter (zero tokenów):
  1. Czy Tavily zwrócił niepustą treść? Jeśli nie → skip URL
  2. Czy domena to .pl LUB treść zawiera polskie znaki diakrytyczne? Jeśli nie → skip URL

AI klasyfikacja (Haiku):
  → Czy firma oferuje usługi AI (nie: artykuł/blog/news o AI)?
  → Zwraca: {is_valid: bool, what_they_do: str}

Błędy techniczne (Anthropic API / Tavily):
  → Retry: 2 próby z 2-sekundowym opóźnieniem
  → Po 2 nieudanych próbach: skip URL, log błędu, próbuj następny
  → Jeśli żaden URL w całej partii nie zadziałał: zwróć 503 do frontendu z komunikatem "Spróbuj ponownie"
```

### KONSEKWENCJE

**Pozytywne:**
- Pre-filter eliminuje angielskie strony tanio i szybko — większość false positive odpada przed wywołaniem AI
- Retry na błędach API sprawia że przejściowy problem z siecią nie psuje całej sesji użytkownika
- Brak crasha przy błędzie — loop przechodzi do następnego URL, użytkownik nie wie że coś poszło nie tak

**Negatywne:**
- Heurystyka .pl / polskie znaki może odrzucić polską firmę z domeną .com — ryzyko ocenione jako niskie (~5% polskich firm AI używa tylko .com bez polskich znaków na stronie)
- False negative (dobra firma odrzucona przez AI) jest bezpowrotna — firma trafia do pominięć i nigdy nie wróci. Mitygacja: prompt podkreśla że ma być konserwatywny w odrzucaniu — lepiej przepuścić wątpliwą firmę niż odrzucić dobrą.

**Migracja:**
Jeśli okaże się że pre-filter .pl odrzuca za dużo dobrych firm — wystarczy usunąć check domeny i zostawić tylko detekcję polskich znaków. Zmiana jednej linii w `page_verifier.py`. Jeśli false positive od AI będzie zbyt często — dodajemy drugi prompt "sprawdź jeszcze raz" tylko dla wątpliwych przypadków (Opcja C), bez przebudowy architektury.
