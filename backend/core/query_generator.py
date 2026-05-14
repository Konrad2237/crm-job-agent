import random

_TECHNOLOGIES = [
    "ML predykcja analityka",
    "przetwarzanie języka naturalnego analiza tekstu",
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
    "legaltech automatyzacja dokumentów kontraktów",
    "e-commerce retail",
    "produkcja manufacturing przemysł",
    "logistyka transport supply chain",
    "marketing reklama personalizacja",
    "edtech szkolenia korporacyjne",
    "nieruchomości proptech",
    "energetyka smart grid",
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
