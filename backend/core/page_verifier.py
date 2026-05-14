from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel


class PageVerification(BaseModel):
    is_polish: bool
    is_ai_company: bool


_model = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    max_tokens=200,
    temperature=0.0,
).with_structured_output(PageVerification)

SYSTEM_PROMPT = """Oceniasz czy dana firma to polska firma sprzedająca AI.

is_polish: Czy to firma założona i działająca w Polsce, z polskim zespołem?
TAK: polska siedziba lub adres, polski zespół, oferta skierowana do polskich klientów.
NIE: międzynarodowe narzędzie SaaS z polską wersją językową (brak polskiego zespołu/adresu), globalna platforma dostępna w wielu krajach, firma z zagraniczną centralą.
Sama polska wersja strony NIE wystarczy — liczy się polski zespół i polskie korzenie firmy.

is_ai_company: Czy główna oferta tej firmy to sprzedaż lub wdrożenia AI dla klientów?
TAK: firma której core biznes to chatboty, agenci AI, systemy ML, computer vision, automatyzacja AI, analiza predykcyjna, LLM — sprzedawane lub wdrażane u klientów.
NIE: agencja marketingowa/SEO/PR/web która używa AI jako narzędzia pracy; software house bez specjalizacji AI; firma gdzie AI to jedna z wielu funkcji produktu; portal newsowy; artykuł; katalog firm; firma szkoleniowa."""


async def verify_page(content: str, domain: str = "", title: str = "") -> PageVerification:
    header_parts = []
    if domain:
        header_parts.append(f"Domena: {domain}")
    if title:
        header_parts.append(f"Tytuł: {title}")
    header = "\n".join(header_parts) + "\n\n" if header_parts else ""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"{header}Treść:\n\n{content}"),
    ]
    return await _model.ainvoke(messages)
