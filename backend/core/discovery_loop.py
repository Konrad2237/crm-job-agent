import asyncio
import os
from fastapi import HTTPException
from tavily import AsyncTavilyClient

from db.client import normalize_domain, is_domain_seen, save_company, get_recent_presented, cleanup_stale_presented
from core.query_generator import generate_query
from core.page_verifier import verify_page

MAX_ATTEMPTS = 3          # ile razy generujemy nowe zapytanie Tavily
MAX_RESULTS = 5           # ile URLi Tavily zwraca na jedno zapytanie
MAX_CONTENT_CHARS = 6_000 # twardy limit treści przed wysłaniem do Haiku

_tavily: AsyncTavilyClient | None = None


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
    try:
        async with asyncio.timeout(25):  # twardy limit — Railway zerwie połączenie po 30s
            # Krok 0: czy jest firma z niepodjętą decyzją z ostatnich 24h?
            # Scenariusz: użytkownik zamknął przeglądarkę przed kliknięciem Pomiń/Aplikuj.
            pending = await get_recent_presented()
            if pending:
                return pending

            # Wyczyść firmy "presented" starsze niż 24h → zmień na "skipped"
            await cleanup_stale_presented()

            tavily = _get_tavily()
            previous_queries: list[str] = []

            for attempt in range(MAX_ATTEMPTS):
                # Krok 1: Haiku generuje zapytanie (zna poprzednie żeby się nie powtarzać)
                query = await call_with_retry(lambda: generate_query(previous_queries))
                previous_queries.append(query)

                # Krok 2: Tavily szuka — zwraca max 5 URLi z tytułami i snippetami
                search_resp = await call_with_retry(
                    lambda q=query: tavily.search(q, max_results=MAX_RESULTS)
                )

                for result in search_resp.get("results", []):
                    url = result.get("url", "")
                    if not url:
                        continue

                    # Krok 3: normalizacja domeny + dedup — czy już w bazie?
                    domain = normalize_domain(url)
                    if not domain:
                        continue

                    if await is_domain_seen(domain):
                        continue

                    # Krok 4: pobierz treść strony (z fallbackiem na snippet)
                    snippet = result.get("content", "")
                    content = await _extract_content(tavily, url, snippet)

                    if len(content) < 50:
                        continue  # naprawdę nic nie ma — skip

                    # Krok 5: Haiku klasyfikuje — polska firma AI?
                    verification = await call_with_retry(lambda c=content: verify_page(c))

                    if not verification.is_polish or not verification.is_ai_company:
                        continue

                    # Krok 6: zapisz do bazy i zwróć
                    name = result.get("title", domain)
                    company = await save_company(
                        name=name,
                        url=url,
                        domain=domain,
                        what_they_do=verification.what_they_do,
                    )
                    return company

            return None  # po 3 próbach nic nie znaleziono

    except asyncio.TimeoutError:
        raise HTTPException(503, "Wyszukiwanie trwa za długo. Spróbuj ponownie.")
