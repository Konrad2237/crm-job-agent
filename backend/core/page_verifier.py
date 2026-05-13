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
    max_tokens=150,
    temperature=0.0,
).with_structured_output(PageVerification)

SYSTEM_PROMPT = """Klasyfikujesz fragmenty stron internetowych.

Kryterium 1 — is_polish: czy to polska firma?
- Treść głównie po polsku LUB siedziba w Polsce LUB domena .pl
- Oddziały zagranicznych korporacji w Polsce = NIE

Kryterium 2 — is_ai_company: czy to strona FIRMY która ŚWIADCZY usługi AI lub buduje produkty AI jako organizacja z zespołem?
- TAK: chatboty, voiceboty, agenci AI, automatyzacje LLM, RAG, wdrożenia AI, AI consulting, własny produkt SaaS oparty o AI, software house z ofertą AI — nawet jeśli firma oferuje też szkolenia lub warsztaty jako usługę dodatkową
- NIE — każde z poniższych dyskwalifikuje:
  • artykuł, blog, news, ranking, zestawienie lub lista firm (nawet jeśli wymienia firmy AI)
  • katalog firm, portal porównawczy, agregator, marketplace
  • firma tylko wspomina AI bez konkretnej oferty usług
  • firma WYŁĄCZNIE sprzedaje kursy lub szkolenia z AI, bez żadnych wdrożeń
  • e-commerce lub marketing który "używa AI" ale nie sprzedaje AI jako usługi
  • strona prezentuje JEDNO gotowe narzędzie SaaS dla wąskiej grupy zawodowej (prawnicy, lekarze, księgowi, HR) bez widocznego opisu firmy, zespołu ani oferty usług wdrożeniowych — to produkt, nie firma
  • subdomena aplikacji lub panel demo (app.*, try.*, demo.*) bez kontekstu firmowego

what_they_do: jednozdaniowy opis (np. "chatboty dla e-commerce, integracje GPT-4") — tylko gdy oba kryteria TAK. W przeciwnym razie pusty string."""


async def verify_page(content: str) -> PageVerification:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Treść strony:\n\n{content}"),
    ]
    return await _model.ainvoke(messages)
