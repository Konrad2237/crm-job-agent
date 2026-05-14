import asyncio
import os
import re
from urllib.parse import urlparse
from fastapi import HTTPException
from tavily import AsyncTavilyClient

from db.client import normalize_domain, get_seen_domains, save_company, save_skipped_domain, get_recent_presented, cleanup_stale_presented
from core.query_generator import generate_query
from core.page_verifier import verify_page

MAX_ATTEMPTS = 3          # ile razy generujemy nowe zapytanie Tavily
MAX_RESULTS = 5           # więcej kandydatów per zapytanie — lepsze pokrycie po filtrowaniu
MAX_CONTENT_CHARS = 2_000 # twardy limit treści przed wysłaniem do Haiku

_POLISH_CHARS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")

# Domeny zawsze odrzucane — trafiają do Tavily exclude_domains (nie wracają wcale)
# i są sprawdzane lokalnie. Subdomeny też są blokowane przez _is_blocked().
_BLOCKED_DOMAINS = frozenset({
    # Social media
    "facebook.com", "youtube.com", "linkedin.com", "twitter.com", "x.com",
    "instagram.com", "tiktok.com",
    # Encyklopedie
    "wikipedia.org", "wikipedia.pl",
    # Portale pracy
    "pracuj.pl", "olx.pl", "indeed.com", "nofluffjobs.com", "justjoin.it",
    # Dev / Q&A
    "github.com", "stackoverflow.com", "reddit.com",
    # E-commerce
    "allegro.pl", "ceneo.pl",
    # Portale newsowe i biznesowe — wracały jako wyniki dla zapytań o firmy AI
    "rp.pl", "pb.pl", "infor.pl", "android.com.pl",
    "benchmark.pl", "chip.pl", "pcworld.pl", "pcformat.pl",
    "wirtualnemedia.pl", "money.pl", "forbes.pl", "businessinsider.com.pl",
    "itwiz.pl", "telepolis.pl", "antyweb.pl", "spidersweb.pl",
})


def _is_blocked(domain: str) -> bool:
    if ".gov.pl" in domain:
        return True
    if domain in _BLOCKED_DOMAINS:
        return True
    # Blokuj też subdomeny zablokowanych domen (np. cyfrowa.rp.pl gdy rp.pl jest zablokowane)
    return any(domain.endswith(f".{blocked}") for blocked in _BLOCKED_DOMAINS)


_ARTICLE_PATH_PATTERNS = (
    "/blog/", "/news/", "/artykul", "/artykuł", "/ranking",
    "/top-", "/lista-", "/wpis/", "/post/", "/wiedza/", "/porady/",
)
# /2025/03/ lub /2026/02/ — klasyczny WordPress URL artykułu z datą
_DATE_PATH_RE = re.compile(r"/20\d{2}/\d{1,2}/")
# "10 sposobów...", "100 Top AI Companies..." — artykuły zawsze zaczynają się od liczby
_TITLE_NUMBER_START_RE = re.compile(r"^\d+[\s\-]")

# Sygnały artykułu w tytule wyniku — niezawodne, tytuły artykułów mają stałą strukturę
_ARTICLE_TITLE_PATTERNS = (
    "ranking",
    "top 10", "top 5", "top 15", "top 20",
    "lista firm",
    "zestawienie firm",
    "najlepsze firmy",
    "jak wybrać",
    "jak działa",
    "co to jest",
    "poradnik",
    "przewodnik",
    " firm ai",      # "15 firm AI...", "polskie firmy AI" itp.
    "katalog ",      # "katalog LegalTech", "katalog firm AI" itp.
    "companies in",  # "Top AI Companies in Poland"
    "top ai",        # "Top AI Companies..."
    "sposobów",      # "10 sposobów jak AI..."
    "zaskakując",    # "10 zaskakujących sposobów..."
)
# Sygnały artykułu w snippecie — tylko te które NIGDY nie pojawiają się na stronie firmowej
_ARTICLE_SNIPPET_SIGNALS = (
    "w tym artykule",
    "przeczytaj artykuł",
    "redakcja:",
)


def _is_likely_polish(domain: str, text: str) -> bool:
    if domain.endswith(".pl"):
        return True
    return any(c in _POLISH_CHARS for c in text)


def _is_edu_domain(domain: str) -> bool:
    return ".edu.pl" in domain


def _is_likely_article(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if path.endswith(".pdf"):
        return True
    return any(pat in path for pat in _ARTICLE_PATH_PATTERNS) or bool(_DATE_PATH_RE.search(path))


def _is_likely_article_title(title: str) -> bool:
    if _TITLE_NUMBER_START_RE.match(title):
        return True
    lower = title.lower()
    return any(pat in lower for pat in _ARTICLE_TITLE_PATTERNS)


def _is_likely_article_snippet(snippet: str) -> bool:
    lower = snippet.lower()
    return any(sig in lower for sig in _ARTICLE_SNIPPET_SIGNALS)

_tavily: AsyncTavilyClient | None = None
_query_history: list[str] = []  # rolling window zapytań — persists across requests
QUERY_HISTORY_MAX = 5


def _get_tavily() -> AsyncTavilyClient:
    global _tavily
    if _tavily is None:
        _tavily = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    return _tavily


async def call_with_retry(fn, retries: int = 2, delay: float = 2.0):
    # Wspólny retry dla Tavily i Anthropic API.
    # fn to callable zwracający coroutine — wywołujemy go na nowo przy każdym retry,
    # bo zużyta coroutine nie może być awaited drugi raz.
    for attempt in range(retries + 1):
        try:
            return await fn()
        except Exception:
            if attempt == retries:
                raise
            await asyncio.sleep(delay)


async def _extract_content(tavily: AsyncTavilyClient, url: str, snippet: str) -> str:
    # Próbujemy pobrać pełną treść strony przez Tavily Extract.
    # Fallback na snippet z wyników search gdy:
    #   - strona jest SPA (React/Vue) i Extract zwraca pusty HTML
    #   - Extract API zwraca błąd
    try:
        resp = await call_with_retry(lambda: tavily.extract([url]))
        results = resp.get("results", [])
        content = results[0].get("raw_content", "") if results else ""
    except Exception:
        content = ""

    if len(content) < 300:
        content = snippet  # snippet z Tavily Search — zawsze dostępny, 200-400 słów

    return content[:MAX_CONTENT_CHARS]


def _name_from_title(title: str, domain: str) -> str:
    def _is_junk(text: str) -> bool:
        # Odrzuca listy miast: "Gdańsk, Poznań, Warszawa" — wiele słów po przecinku, każde z dużej litery
        parts = [p.strip() for p in text.split(",")]
        return len(parts) >= 2 and all(p and p[0].isupper() for p in parts)

    # Próbuj " | " najpierw — standardowy format PL: "Opis strony | Nazwa Firmy"
    for sep in (" | ", " – ", " - "):
        parts = title.split(sep)
        if len(parts) > 1:
            candidate = parts[-1].strip()
            if 2 < len(candidate) < 45 and not _is_junk(candidate):
                return candidate
    return domain


async def find_company() -> dict | None:
    global _query_history
    try:
        async with asyncio.timeout(55):  # Extract homepage: +3-8s/kandydat; przy 3 próbach max ~50s
            # Krok 0: czy jest firma z niepodjętą decyzją z ostatnich 24h?
            # Scenariusz: użytkownik zamknął przeglądarkę przed kliknięciem Pomiń/Aplikuj.
            pending = await get_recent_presented()
            if pending:
                return pending

            # Wyczyść firmy "presented" starsze niż 24h → zmień na "skipped"
            await cleanup_stale_presented()

            tavily = _get_tavily()
            previous_queries: list[str] = list(_query_history)

            for attempt in range(MAX_ATTEMPTS):
                # Krok 1: Haiku generuje zapytanie — zna poprzednie żeby się nie powtarzać
                query = await call_with_retry(
                    lambda: generate_query(previous_queries)
                )
                print(f"[QUERY #{attempt+1}] {query}")
                previous_queries.append(query)
                _query_history.append(query)
                if len(_query_history) > QUERY_HISTORY_MAX:
                    _query_history.pop(0)

                # Krok 2: Tavily szuka — exclude_domains działa po stronie Tavily,
                # więc social media i portale pracy nie wracają wcale (zero tokenów)
                search_resp = await call_with_retry(
                    lambda q=query: tavily.search(
                        q,
                        max_results=MAX_RESULTS,
                        search_depth="advanced",
                        exclude_domains=list(_BLOCKED_DOMAINS),
                    )
                )

                # Krok 3: normalizacja domen + batch dedup — 1 zapytanie zamiast 5
                candidates = []
                for result in search_resp.get("results", []):
                    url = result.get("url", "")
                    if not url:
                        continue
                    domain = normalize_domain(url)
                    if domain:
                        candidates.append((domain, url, result))

                seen = await get_seen_domains([d for d, _, _ in candidates])

                for domain, url, result in candidates:
                    if domain in seen:
                        print(f"[SKIP:seen]    {domain}")
                        continue

                    if _is_blocked(domain):
                        print(f"[SKIP:blocked] {domain}")
                        continue

                    if _is_edu_domain(domain):
                        print(f"[SKIP:edu] {domain}")
                        continue

                    # Krok 3.5: heurystyczny pre-filter — zero tokenów
                    # Odrzuca angielskie strony i artykuły zanim zapłacimy za Haiku
                    snippet = result.get("content", "")
                    title = result.get("title", "")
                    if not _is_likely_polish(domain, snippet):
                        print(f"[SKIP:not-pl]  {domain} | {title}")
                        continue
                    if _is_likely_article(url):
                        print(f"[SKIP:url-pat] {domain} | {title}")
                        continue
                    if _is_likely_article_title(title):
                        print(f"[SKIP:title]   {domain} | {title}")
                        continue
                    if _is_likely_article_snippet(snippet):
                        print(f"[SKIP:snippet] {domain} | {title}")
                        continue

                    # Krok 4: pobierz treść do klasyfikacji.
                    # .pl: Extract homepage — pełna treść strony, najdokładniejsze źródło.
                    # non-.pl: snippet z Tavily (po polsku) — Extract dałby angielski homepage
                    #   i Haiku fałszywie odrzuciłby polską firmę z domeną .com/.ai/.io.
                    if domain.endswith(".pl"):
                        content = await _extract_content(tavily, f"https://{domain}", snippet)
                    else:
                        content = snippet[:MAX_CONTENT_CHARS] if snippet else ""

                    if len(content) < 50:
                        print(f"[SKIP:no-content] {domain} | {title}")
                        continue

                    # Krok 5: Haiku klasyfikuje — polska firma AI?
                    # Przekazujemy domenę i tytuł jako dodatkowy kontekst obok treści.
                    print(f"[HAIKU]        {domain} | {title}")
                    try:
                        verification = await call_with_retry(
                            lambda c=content, d=domain, t=title: verify_page(c, d, t), retries=1
                        )
                    except Exception:
                        await save_skipped_domain(result.get("title", domain), url, domain)
                        print(f"[SKIP:haiku-err] {domain}")
                        continue  # błąd parsowania — skip URL, nie przepalaj kolejnych tokenów

                    if not verification.is_polish or not verification.is_ai_company:
                        print(f"[SKIP:haiku]   {domain} | pl={verification.is_polish} ai={verification.is_ai_company}")
                        continue

                    # Krok 6: zapisz do bazy i zwróć
                    name = _name_from_title(title, domain)
                    homepage_url = f"https://{domain}"
                    print(f"[FOUND]        {domain} | {name}")
                    company = await save_company(name=name, url=homepage_url, domain=domain)
                    return company

            return None  # po 3 próbach nic nie znaleziono

    except (asyncio.TimeoutError, asyncio.CancelledError):
        # asyncio.timeout() wewnętrznie używa CancelledError — LangChain może go przebić
        # zanim asyncio.timeout.__aexit__ zdąży go zamienić na TimeoutError
        raise HTTPException(503, "Wyszukiwanie trwa za długo. Spróbuj ponownie.")
