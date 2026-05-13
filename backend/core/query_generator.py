from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

# Model inicjalizujemy raz przy imporcie modułu, nie przy każdym wywołaniu.
# max_tokens=100 — zapytanie to 5-10 słów, 100 tokenów w zupełności wystarcza
# temperature=0.9 — wysoka losowość żeby kolejne zapytania były różne, nie warianty tego samego
_model = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    max_tokens=100,
    temperature=0.9,
)

SYSTEM_PROMPT = """Generujesz zapytania do wyszukiwarki żeby znaleźć strony główne polskich firm zajmujących się sztuczną inteligencją.

Wyobraź sobie że szukasz firmy AI w Polsce do której możesz wysłać CV. Chcesz trafić na stronę główną takiej firmy — nie na artykuł, ranking ani portal z listą firm.

Eksploruj szeroko: różne branże (fintech, medtech, legaltech, HR, e-commerce, produkcja, logistyka, edukacja, marketing, budownictwo, ubezpieczenia, retail), różne typy firm (startup, software house, agencja, consulting, product company), różne rodzaje rozwiązań AI (chatboty, agenci, RAG, automatyzacje, analityka, computer vision, NLP).

Każde zapytanie inne niż poprzednie — inna kombinacja branży i rodzaju AI.
Zwróć tylko zapytanie, bez wyjaśnień.

Przykłady naturalnych zapytań które trafiają w strony firmowe:
- polska firma AI automatyzacja procesów finansowych
- chatbot dla branży medycznej wdrożenia Polska
- agenci AI software house Warszawa
- RAG analiza dokumentów prawnych polska firma
- computer vision kontrola jakości produkcja Polska
- NLP przetwarzanie faktur automatyzacja polska firma
- AI consulting wdrożenia dla ubezpieczycieli Polska
- startup machine learning rekomendacje e-commerce\""""


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
