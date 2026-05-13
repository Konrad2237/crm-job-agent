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
MAX_RESULTS = 5           # ile URLi Tavily zwraca na jedno zapytanie
MAX_CONTENT_CHARS = 2_000 # twardy limit treści przed wysłaniem do Haiku

_POLISH_CHARS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")

# Domeny zawsze odrzucane bez wywoływania Haiku — social media, agregatory, gov
_BLOCKED_DOMAINS = frozenset({
    "facebook.com", "youtube.com", "linkedin.com", "twitter.com", "x.com",
    "instagram.com", "tiktok.com", "wikipedia.org", "wikipedia.pl",
    "pracuj.pl", "olx.pl", "indeed.com", "nofluffjobs.com", "justjoin.it",
    "github.com", "stackoverflow.com", "reddit.com",
    "allegro.pl", "ceneo.pl",
})


def _is_blocked(domain: str) -> bool:
    return domain in _BLOCKED_DOMAINS or ".gov.pl" in domain


_ARTICLE_PATH_PATTERNS = (
    "/blog/", "/news/", "/artykul", "/artykuł", "/ranking",
    "/top-", "/lista-", "/wpis/", "/post/", "/wiedza/", "/porady/",
)
# /2025/03/ lub /2026/02/ — klasyczny WordPress URL artykułu z datą
_DATE_PATH_RE = re.compile(r"/20\d{2}/\d{1,2}/")

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
    " firm ai",   # "15 firm AI...", "polskie firmy AI" itp.
    "katalog ",   # "katalog LegalTech", "katalog firm AI" itp.
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


def _is_likely_article(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(pat in path for pat in _ARTICLE_PATH_PATTERNS) or bool(_DATE_PATH_RE.search(path))


def _is_likely_article_title(title: str) -> bool:
    lower = title.lower()
    return any(pat in lower for pat in _ARTICLE_TITLE_PATTERNS)


def _is_likely_article_snippet(snippet: str) -> bool:
    lower = snippet.lower()
    return any(sig in lower for sig in _ARTICLE_SNIPPET_SIGNALS)

_tavily: AsyncTavilyClient | None = None
_query_history: list[str] = []          # rolling window zapytań — persists across requests
_recent_found_categories: list[str] = [] # rolling window znalezionych kategorii firm
QUERY_HISTORY_MAX = 10
RECENT_FOUND_MAX = 5


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


async def find_company() -> dict | None:
    global _query_history, _recent_found_categories
    try:
        async with asyncio.timeout(45):  # zwiększone z 25 — Extract usunięty, ale 3 próby z Haiku mogą zająć 30s
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
                # Krok 1: Haiku generuje zapytanie — zna poprzednie zapytania i ostatnio znalezione kategorie
                query = await call_with_retry(
                    lambda rc=list(_recent_found_categories): generate_query(previous_queries, rc)
                )
                print(f"[QUERY #{attempt+1}] {query}")
                previous_queries.append(query)
                _query_history.append(query)
                if len(_query_history) > QUERY_HISTORY_MAX:
                    _query_history.pop(0)

                # Krok 2: Tavily szuka — zwraca max 5 URLi z tytułami i snippetami
                search_resp = await call_with_retry(
                    lambda q=query: tavily.search(q, max_results=MAX_RESULTS)
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

                    # Krok 4: snippet jako treść do klasyfikacji — pomijamy Tavily Extract
                    # Snippet (200-500 znaków) wystarczy Haiku do oceny czy to firma AI.
                    # Extract dodawał 2-5 sek latencji i 1500+ tokenów input — usunięty.
                    # Fallback na Extract tylko gdy snippet jest ekstremalnie krótki.
                    if len(snippet) >= 80:
                        content = snippet[:MAX_CONTENT_CHARS]
                    else:
                        content = await _extract_content(tavily, url, snippet)

                    if len(content) < 50:
                        print(f"[SKIP:no-content] {domain} | {title}")
                        continue

                    # Krok 5: Haiku klasyfikuje — polska firma AI?
                    # retries=1 zamiast 2 — przy błędzie parsowania Haiku ponowienie rzadko pomaga
                    print(f"[HAIKU]        {domain} | {title}")
                    try:
                        verification = await call_with_retry(lambda c=content: verify_page(c), retries=1)
                    except Exception:
                        await save_skipped_domain(result.get("title", domain), url, domain)
                        print(f"[SKIP:haiku-err] {domain}")
                        continue  # błąd parsowania — skip URL, nie przepalaj kolejnych tokenów

                    if not verification.is_polish or not verification.is_ai_company:
                        print(f"[SKIP:haiku]   {domain} | pl={verification.is_polish} ai={verification.is_ai_company}")
                        continue

                    # Krok 6: zapisz do bazy i zwróć
                    print(f"[FOUND]        {domain} | {title} | {verification.what_they_do}")
                    if verification.what_they_do:
                        _recent_found_categories.append(verification.what_they_do)
                        if len(_recent_found_categories) > RECENT_FOUND_MAX:
                            _recent_found_categories.pop(0)
                    name = result.get("title", domain)
                    company = await save_company(
                        name=name,
                        url=url,
                        domain=domain,
                        what_they_do=verification.what_they_do,
                    )
                    return company

            return None  # po 3 próbach nic nie znaleziono

    except (asyncio.TimeoutError, asyncio.CancelledError):
        # asyncio.timeout() wewnętrznie używa CancelledError — LangChain może go przebić
        # zanim asyncio.timeout.__aexit__ zdąży go zamienić na TimeoutError
        raise HTTPException(503, "Wyszukiwanie trwa za długo. Spróbuj ponownie.")
