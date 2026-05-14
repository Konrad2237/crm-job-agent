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

SYSTEM_PROMPT = """Oceniasz czy dana firma to polska firma AI.

is_polish: Czy to polska firma lub firma działająca głównie na polskim rynku?
TAK: polska siedziba, oferta po polsku, klienci w Polsce.
NIE: strona wyłącznie po angielsku, brak polskiego adresu/kontaktu, firma z zagraniczną centralą obsługująca globalny rynek.

is_ai_company: Czy główna oferta tej firmy to sprzedaż lub wdrożenia technologii inteligentnych dla klientów?
TAK — nawet bez słowa "AI" — jeśli firma oferuje: chatboty, agentów, systemy ML/NLP, computer vision, machine vision, automatyzację opartą na algorytmach, analizę predykcyjną, LLM, rozpoznawanie obrazu/mowy.
NIE: portal newsowy, agencja rekrutacyjna/HR, firma używająca AI tylko wewnętrznie, artykuł, katalog firm."""


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
