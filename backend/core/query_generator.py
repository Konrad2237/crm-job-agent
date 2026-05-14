from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

_model = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    max_tokens=100,
    temperature=0.9,
)

SYSTEM_PROMPT = """Generujesz zapytania do wyszukiwarki żeby znaleźć strony główne polskich firm zajmujących się sztuczną inteligencją.

Cel: trafić na stronę FIRMY (oferta, usługi, o nas) — nie artykuł, nie ranking, nie news.

Każde zapytanie MUSI zawierać jedno słowo sygnalizujące stronę firmową (nie artykuł):
oferta / wdrożenia / SaaS / demo / B2B / platforma / usługi

Eksploruj różne kombinacje branży i technologii: fintech, medtech, legaltech, HR, e-commerce, produkcja, logistyka, edukacja, marketing — i: chatboty, agenci AI, RAG, ML, NLP, computer vision, automatyzacja, LLM.

Zwróć tylko zapytanie, bez wyjaśnień.

Przykłady dobrych zapytań:
- ML platforma predykcyjna fintech scoring Polska SaaS
- computer vision inspekcja jakości produkcja platforma Polska
- NLP analiza dokumentów prawnych Polska usługi wdrożenia
- agenci AI automatyzacja e-commerce rekomendacje Polska demo
- AI automatyzacja produkcji optymalizacja procesów Polska B2B
- LLM chatbot obsługa klienta Polska SaaS oferta
- AI healthcare diagnostyka obrazowa wdrożenia Polska platforma"""


async def generate_query() -> str:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content="Generuj zapytanie:"),
    ]
    response = await _model.ainvoke(messages)
    return response.content.strip()
