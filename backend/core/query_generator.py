import random

_TECHNOLOGIES = [
    "ML predykcja analityka",
    "NLP analiza dokumentów tekstu",
    "computer vision inspekcja obrazów",
    "LLM asystent konwersacyjny",
    "automatyzacja procesów RPA",
    "agenci AI workflow",
    "RAG baza wiedzy",
    "forecasting szeregi czasowe",
    "rekomendacje personalizacja",
    "OCR ekstrakcja danych",
    "klasyfikacja anomalie wykrywanie",
    "chatbot voicebot",
]

_INDUSTRIES = [
    "fintech bankowość ubezpieczenia",
    "HR rekrutacja onboarding",
    "medtech diagnostyka healthcare",
    "legal analiza umów prawo",
    "e-commerce retail",
    "produkcja manufacturing przemysł",
    "logistyka transport",
    "marketing reklama",
    "edukacja e-learning",
    "nieruchomości proptech",
    "energetyka utilities",
    "obsługa klienta contact center",
]

_SIGNALS = [
    "wdrożenia dla firm oferta",
    "platforma SaaS B2B",
    "rozwiązania dla biznesu kontakt",
    "usługi wdrożeniowe klienci",
    "demo cennik oferta",
]


def generate_query() -> str:
    tech = random.choice(_TECHNOLOGIES)
    industry = random.choice(_INDUSTRIES)
    signal = random.choice(_SIGNALS)
    return f"{tech} {industry} Polska {signal}"
