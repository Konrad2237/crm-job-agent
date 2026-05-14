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
oferta / wdrożenia / SaaS / demo / B2B / platforma / usługi / case study

Eksploruj różne kombinacje branży i technologii: fintech, medtech, legaltech, HR, e-commerce, produkcja, logistyka, edukacja, marketing — i: chatboty, agenci AI, RAG, ML, NLP, computer vision, automatyzacja, LLM.

Każde zapytanie inne niż poprzednie — inna branża lub inna technologia.
Zwróć tylko zapytanie, bez wyjaśnień.

Przykłady dobrych zapytań (zawierają słowo firmowe):
- chatbot AI obsługa klienta SaaS Polska oferta
- automatyzacja procesów ML B2B Polska wdrożenia
- computer vision inspekcja jakości platforma Polska
- NLP analiza dokumentów prawnych Polska usługi
- agenci AI e-commerce rekomendacje Polska demo
- LLM automatyzacja HR rekrutacja Polska SaaS
- AI fintech scoring kredytowy platforma Polska"""


async def generate_query(previous_queries: list[str]) -> str:
    if previous_queries:
        previous_section = "Poprzednie zapytania (nie powtarzaj tych fraz):\n" + "\n".join(
            f"- {q}" for q in previous_queries
        )
    else:
        previous_section = "To jest pierwsze zapytanie w tej sesji."

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"{previous_section}\n\nGeneruj nowe zapytanie:"),
    ]

    response = await _model.ainvoke(messages)
    return response.content.strip()
