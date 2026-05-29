import os
import json
import logging
import httpx
from functools import lru_cache
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Конфигурация OpenRouter
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'openrouter/free')

# Системные промпты для разных типов ответов
SYSTEM_PROMPT_JSON = (
    "Ты AI-помощник интернет-магазина. ВСЕГДА отвечай ТОЛЬКО в формате JSON. "
    "Никакого текста до или после JSON. Используй двойные кавычки. "
    "Структура ответа зависит от вопроса пользователя."
)

SYSTEM_PROMPT_CHAT = (
    "Ты AI-помощник интернет-магазина. Отвечай структурированно, используя только обычный текст, "
    "без маркдауна и без символов **. Правила форматирования:\n"
    "\n"
    "1. Заголовки делай ЗАГЛАВНЫМИ БУКВАМИ с двоеточием\n"
    "2. Для списков используй дефис с пробелом в начале строки\n"
    "3. Для нумерованных списков используй цифры с точкой\n"
    "4. Делай пустые строки между разделами\n"
    "5. Используй эмодзи для выделения (✅, ⚠️, 📦, 💡)\n"
    "6. Пиши на русском, грамотно, дружелюбно"
)

SYSTEM_PROMPT_PRODUCT = (
    "Ты создаешь описания товаров. Отвечай в формате JSON со следующей структурой:\n"
    "{\n"
    '  "short_description": "краткое описание (1 предложение)",\n'
    '  "full_description": "полное описание (2-3 абзаца)",\n'
    '  "advantages": ["преимущество 1", "преимущество 2", "преимущество 3"],\n'
    '  "call_to_action": "призыв к покупке (1 фраза)"\n'
    "}\n"
    "Никакого другого текста, только JSON."
)

SYSTEM_PROMPT_ANALYTICS = (
    "Ты e-commerce аналитик. Отвечай в формате JSON:\n"
    "{\n"
    '  "summary": "краткий вывод (1-2 предложения)",\n'
    '  "recommendations": ["рекомендация 1", "рекомендация 2", "рекомендация 3"],\n'
    '  "forecast": "прогноз на 2 недели",\n'
    '  "action_items": ["действие 1", "действие 2"]\n'
    "}"
)


async def ask_openrouter(
    message: str,
    system_prompt: str = SYSTEM_PROMPT_CHAT,
    temperature: float = 0.7,
    max_tokens: int = 1000
) -> Dict[str, Any]:
    """Отправляет запрос к OpenRouter API"""
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY is not set")
        return {
            "success": False,
            "error": "API ключ не настроен",
            "fallback": get_fallback_response(message)
        }
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return {
                    "success": True,
                    "content": content,
                    "model": data.get("model", OPENROUTER_MODEL)
                }
            else:
                logger.error(f"OpenRouter error: {response.status_code}")
                return {
                    "success": False,
                    "error": f"API error: {response.status_code}",
                    "fallback": get_fallback_response(message)
                }
    except Exception as e:
        logger.error(f"OpenRouter request failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "fallback": get_fallback_response(message)
        }


def get_fallback_response(message: str) -> str:
    """Ответ при недоступности API"""
    return (
        "AI временно недоступен\n\n"
        "Вот базовые рекомендации:\n"
        "- Смотрите на товары с высоким спросом\n"
        "- Держите актуальные цены\n"
        "- Добавляйте качественные фото\n"
        "- Указывайте наличие на складе"
    )


def parse_json_response(content: str) -> Optional[Dict]:
    """Парсит JSON из ответа AI"""
    try:
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            json_str = content[json_start:json_end]
            return json.loads(json_str)
        return None
    except json.JSONDecodeError:
        return None


def build_product_prompt(name: str, category: str, specs: dict) -> str:
    """Создает промпт для генерации описания товара"""
    specs_text = "\n".join([f"- {k}: {v}" for k, v in specs.items()]) if specs else "- Нет характеристик"
    return (
        f"Создай описание товара в формате JSON.\n"
        f"Название: {name}\n"
        f"Категория: {category or 'Не указана'}\n"
        f"Характеристики:\n{specs_text}\n\n"
        "Верни ТОЛЬКО JSON, без пояснений."
    )


def build_chat_prompt(user_message: str, response_format: str = "structured") -> str:
    """Создает промпт для чата"""
    if response_format == "json":
        return (
            f"Ответь на вопрос пользователя в формате JSON.\n"
            f"Вопрос: {user_message}\n\n"
            "Структура ответа:\n"
            "{\n"
            '  "answer": "основной ответ",\n'
            '  "tips": ["совет 1", "совет 2"]\n'
            "}"
        )
    else:
        return f"Пользователь спрашивает: {user_message}\n\nОтветь структурированно, используя заголовки и списки."


def build_market_insights_prompt(raw_stats: dict) -> str:
    """Создает промпт для аналитики"""
    return (
        f"На основе статистики магазина верни анализ в формате JSON.\n\n"
        f"Статистика:\n"
        f"- Всего товаров: {raw_stats.get('seller_products_count', 0)}\n"
        f"- Добавлений в корзину: {raw_stats.get('total_cart_additions', 0)}\n\n"
        "Верни JSON с полями: summary, recommendations, forecast, action_items"
    )


def ask_ai_sync(
    message: str,
    response_format: str = "structured",
    temperature: float = 0.7
) -> str:
    """Синхронная версия для Django"""
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    system_prompt = SYSTEM_PROMPT_JSON if response_format == "json" else SYSTEM_PROMPT_CHAT
    
    try:
        result = loop.run_until_complete(
            ask_openrouter(message, system_prompt, temperature)
        )
        
        if result.get("success"):
            content = result["content"]
            if response_format == "json":
                parsed = parse_json_response(content)
                if parsed:
                    return json.dumps(parsed, ensure_ascii=False)
            return content
        else:
            return result.get("fallback", "AI временно недоступен")
    except Exception as e:
        logger.error(f"AI sync request failed: {e}")
        return get_fallback_response(message)


@lru_cache(maxsize=50)
def ask_ai_cached(prompt: str, response_format: str = "structured") -> str:
    return ask_ai_sync(prompt, response_format)


# ========== НОВЫЕ ФУНКЦИИ ДЛЯ ПОИСКА ПО ЦЕНЕ ==========

from products.models import Product


def get_products_with_prices(limit: int = 100) -> List[Dict]:
    """
    Получает товары с ценами для AI анализа
    """
    products = Product.objects.select_related('category').filter(stock__gt=0)[:limit]
    
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "price": float(p.price),
            "category": p.category.name if p.category else "Без категории",
            "description": p.description[:150],
            "specs": p.specs,
            "stock": p.stock
        }
        for p in products
    ]


def build_price_recommendation_prompt(user_query: str, products: List[Dict]) -> str:
    """
    Создает промпт для рекомендации товаров с учетом цены
    """
    if not products:
        return "Нет товаров для анализа"
    
    products_text = "\n".join([
        f"{i+1}. {p['name']} - {p['price']}₽ | {p['category']}\n"
        f"   Описание: {p['description'][:80]}..."
        for i, p in enumerate(products[:40])
    ])
    
    return f"""
Ты AI-помощник интернет-магазина. Пользователь хочет купить товар.

ЗАПРОС ПОЛЬЗОВАТЕЛЯ: "{user_query}"

ДОСТУПНЫЕ ТОВАРЫ (с ценами):
{products_text}

ЗАДАЧА:
1. Найди товары, которые пользователь может купить, учитывая его бюджет (если указан)
2. Учти требования к характеристикам, категории, цене
3. Отсортируй по релевантности и цене
4. Если бюджет не указан, предложи варианты в разных ценовых сегментах

ФОРМАТ ОТВЕТА (ТОЛЬКО JSON, БЕЗ ДРУГОГО ТЕКСТА):
{{
  "understanding": "краткое описание того, что понял из запроса",
  "budget_found": true,
  "budget_amount": число_если_указан,
  "recommendations": [
    {{
      "product_id": "id_товара",
      "name": "название",
      "price": 1000,
      "why_fits": "почему подходит под запрос",
      "price_rating": "бюджетный/средний/премиум"
    }}
  ],
  "budget_advice": "совет по бюджету (если нужен)",
  "alternative_advice": "альтернативные советы"
}}
"""


def get_ai_price_recommendations(user_query: str) -> Dict[str, Any]:
    """
    Получает рекомендации от AI с учетом цены
    """
    products = get_products_with_prices()
    
    if not products:
        return {
            "understanding": "В магазине пока нет товаров",
            "recommendations": [],
            "budget_advice": "Добавьте первый товар в магазин",
            "alternative_advice": None
        }
    
    prompt = build_price_recommendation_prompt(user_query, products)
    response = ask_ai_sync(prompt, response_format="json")
    
    try:
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            json_str = response[json_start:json_end]
            result = json.loads(json_str)
            
            enriched_recommendations = []
            for rec in result.get('recommendations', []):
                product = Product.objects.filter(id=rec.get('product_id')).first()
                if product:
                    enriched_recommendations.append({
                        **rec,
                        "product": {
                            "id": str(product.id),
                            "name": product.name,
                            "price": float(product.price),
                            "description": product.description,
                            "category": product.category.name if product.category else None,
                            "image": product.image,
                            "stock": product.stock
                        }
                    })
            
            return {
                "understanding": result.get('understanding', ''),
                "budget_found": result.get('budget_found', False),
                "budget_amount": result.get('budget_amount'),
                "recommendations": enriched_recommendations,
                "budget_advice": result.get('budget_advice'),
                "alternative_advice": result.get('alternative_advice')
            }
    except Exception as e:
        logger.error(f"Failed to parse price recommendations: {e}")
    
    return {
        "understanding": "Не удалось обработать запрос",
        "recommendations": [],
        "budget_advice": "Попробуйте переформулировать запрос, указав бюджет",
        "alternative_advice": None
    }


def build_budget_analysis_prompt(products: List[Dict]) -> str:
    """
    Анализ ценового диапазона товаров
    """
    prices = [p['price'] for p in products]
    if not prices:
        return "Нет товаров для анализа"
    
    min_price = min(prices)
    max_price = max(prices)
    avg_price = sum(prices) / len(prices)
    
    cheap_products = [p for p in products if p['price'] < avg_price * 0.7][:5]
    expensive_products = [p for p in products if p['price'] > avg_price * 1.5][:5]
    
    return f"""
Проанализируй цены в магазине:

Диапазон цен: от {min_price}₽ до {max_price}₽
Средняя цена: {avg_price:.0f}₽

Бюджетные товары (до {avg_price * 0.7:.0f}₽):
{', '.join([p['name'] for p in cheap_products])}

Премиум товары (от {avg_price * 1.5:.0f}₽):
{', '.join([p['name'] for p in expensive_products])}

Верни JSON (ТОЛЬКО JSON, БЕЗ ДРУГОГО ТЕКСТА):
{{
  "price_range": {{"min": {min_price}, "max": {max_price}, "avg": {avg_price:.0f}}},
  "budget_category": "бюджетный/средний/премиум",
  "recommended_budget": "рекомендуемый бюджет для разных категорий",
  "insight": "интересное наблюдение о ценах"
}}
"""


def get_price_analysis() -> Dict[str, Any]:
    """
    Получает анализ ценового диапазона
    """
    products = get_products_with_prices()
    if not products:
        return {"error": "Нет товаров для анализа"}
    
    prompt = build_budget_analysis_prompt(products)
    response = ask_ai_sync(prompt, response_format="json")
    
    try:
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            return json.loads(response[json_start:json_end])
    except Exception as e:
        logger.error(f"Failed to parse price analysis: {e}")
    
    return {"error": "Не удалось проанализировать цены"}