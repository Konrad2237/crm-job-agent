from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel


class PageVerification(BaseModel):
    is_polish: bool
    is_ai_company: bool
    what_they_do: str = ""  # pusty gdy którekolwiek kryterium False


# temperature=0.0 — klasyfikacja wymaga determinizmu, nie kreatywności
_model = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    max_tokens=100,
    temperature=0.0,
).with_structured_output(PageVerification)

SYSTEM_PROMPT = """Klasyfikujesz fragmenty stron internetowych.

Kryterium 1 — is_polish: czy to polska firma?
- Treść głównie po polsku LUB siedziba w Polsce LUB domena .pl
- Oddziały zagranicznych korporacji w Polsce = NIE

Kryterium 2 — is_ai_company: czy to strona firmy która SPRZEDAJE usługi lub produkty AI?
- TAK: chatboty, voiceboty, agenci AI, automatyzacje LLM, RAG, wdrożenia AI, AI consulting, własny produkt SaaS oparty o AI, software house z ofertą AI
- NIE — każde z poniższych dyskwalifikuje:
  • artykuł, blog, news, ranking, zestawienie lub lista firm (nawet jeśli wymienia firmy AI)
  • katalog firm, portal porównawczy, agregator
  • firma tylko wspomina AI bez konkretnej oferty usług
  • kursy i szkolenia z AI
  • e-commerce lub marketing który "używa AI"

what_they_do: jednozdaniowy opis (np. "chatboty dla e-commerce, integracje GPT-4") — tylko gdy oba kryteria TAK. W przeciwnym razie pusty string."""


async def verify_page(content: str) -> PageVerification:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Treść strony:\n\n{content}"),
    ]
    return await _model.ainvoke(messages)
