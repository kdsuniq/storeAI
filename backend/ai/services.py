import os


SYSTEM_PROMPT = (
    "Ты AI-помощник интернет-магазина. Пиши понятные, продающие и честные "
    "описания товаров на русском языке. Не выдумывай факты, которых нет во "
    "входных данных."
)


def _get_client():
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key)


def build_product_prompt(name: str, category: str, specs: dict) -> str:
    specs_text = "\n".join([f"- {k}: {v}" for k, v in specs.items()]) if specs else "- Нет характеристик"
    return (
        f"Создай описание товара для карточки в магазине.\n"
        f"Название: {name}\n"
        f"Категория: {category or 'Не указана'}\n"
        f"Характеристики:\n{specs_text}\n\n"
        "Требования:\n"
        "1) 2-3 абзаца\n"
        "2) Без воды\n"
        "3) Добавь короткий список преимуществ\n"
        "4) Русский язык"
    )


def build_market_insights_prompt(raw_stats: dict) -> str:
    return (
        "Ты аналитик e-commerce. На основе статистики магазина сделай короткий отчет.\n"
        "Нужно:\n"
        "1) Топ-3 наиболее востребованных товара.\n"
        "2) 3 рекомендации, какие товары продавцу сейчас выгоднее добавлять.\n"
        "3) Простой прогноз спроса на ближайшие 2 недели.\n"
        "Пиши на русском, структурированно, без выдуманных цифр.\n\n"
        f"Статистика: {raw_stats}"
    )


def local_fallback_response(message: str) -> str:
    return (
        "AI недоступен, поэтому включен локальный режим. "
        "Сфокусируйтесь на товарах с частыми добавлениями в корзину, "
        "держите конкурентную цену и добавьте четкие характеристики. "
        f"Ваш запрос: {message[:200]}"
    )


def ask_ai(message: str) -> str:
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content or ""
    except Exception:
        return local_fallback_response(message)
