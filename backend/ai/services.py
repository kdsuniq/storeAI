import os
import json
import logging
import re
import httpx
from functools import lru_cache
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Конфигурация OpenRouter
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY') or os.getenv('OPENAI_API_KEY', '')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'openrouter/free')

# Системные промпты для разных типов ответов
SYSTEM_PROMPT_JSON = (
    "Ты AI-помощник интернет-магазина. ВСЕГДА отвечай ТОЛЬКО в формате JSON. "
    "Никакого текста до или после JSON. Используй двойные кавычки. "
    "Структура ответа зависит от вопроса пользователя."
)

SYSTEM_PROMPT_CHAT = (
    "Ты AI-помощник интернет-магазина. Отвечай коротко, спокойно и по делу. "
    "Используй только обычный текст: без маркдауна, без **, без эмодзи и без CAPS-заголовков. "
    "Правила форматирования:\n"
    "\n"
    "1. Максимум 4 короткие строки.\n"
    "2. Если нужен список, используй максимум 3 пункта с дефисом.\n"
    "3. Не перечисляй товары из каталога: интерфейс покажет их отдельно.\n"
    "4. Не используй слова вроде 'ЗАГЛАВНЫМИ'.\n"
    "5. Пиши на русском, грамотно и дружелюбно."
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


def extract_openrouter_content(data: Dict[str, Any]) -> Optional[str]:
    """Достаёт текст ответа из разных форматов OpenRouter/OpenAI-compatible API."""
    choices = data.get("choices") or []
    if not choices:
        return None

    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        joined = "\n".join(part for part in parts if part.strip())
        if joined:
            return joined

    for key in ("reasoning", "refusal"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value

    text = choices[0].get("text")
    if isinstance(text, str) and text.strip():
        return text

    return None


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
                content = extract_openrouter_content(data)
                if not content:
                    logger.error("OpenRouter returned empty content: %s", data)
                    return {
                        "success": False,
                        "error": "empty AI response",
                        "fallback": get_fallback_response(message)
                    }
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


def normalize_specs(specs: Any) -> Dict[str, Any]:
    if isinstance(specs, dict):
        return specs
    if isinstance(specs, list):
        normalized = {}
        for index, item in enumerate(specs, start=1):
            if isinstance(item, dict):
                key = item.get("name") or item.get("key") or item.get("title") or f"Характеристика {index}"
                value = item.get("value") or item.get("text") or item.get("description") or ""
                if value:
                    normalized[str(key)] = value
            elif isinstance(item, str) and item.strip():
                normalized[f"Характеристика {index}"] = item.strip()
        return normalized
    return {}


def build_local_product_description(name: str, category: str = "", specs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    clean_name = str(name).strip()
    clean_category = str(category or "").strip()
    specs = normalize_specs(specs)
    category_text = clean_category or "товаров для ежедневного использования"
    specs_text = ", ".join([f"{key}: {value}" for key, value in specs.items()]) if specs else ""
    detail_sentence = f" Ключевые характеристики: {specs_text}." if specs_text else ""
    lower_context = f"{clean_name} {clean_category}".lower()

    if "космет" in lower_context or "сыворот" in lower_context:
        product_kind = "сыворотка" if "сыворот" in lower_context else "средство"
        product_label = product_kind if product_kind not in clean_name.lower() else "средство"
        return {
            "short_description": (
                f"{clean_name} — {product_label} для ежедневного ухода из категории «{category_text}»."
            ),
            "full_description": (
                f"{clean_name} подойдёт для аккуратной и понятной карточки в категории «{category_text}». "
                "Описание не содержит неподтверждённых обещаний о составе или эффекте, поэтому его можно безопасно "
                f"использовать как основу и дополнить реальными данными продавца.{detail_sentence}\n\n"
                "Чтобы карточка выглядела убедительнее, добавьте фото товара, объём, способ применения, тип кожи "
                "и ключевые компоненты, если они указаны на упаковке."
            ),
            "advantages": [
                "Подходит для ежедневного ухода",
                "Описание не выдумывает состав и свойства",
                "Легко дополнить фото и характеристиками",
            ],
            "call_to_action": "Добавьте товар в корзину или уточните характеристики перед покупкой.",
        }

    return {
        "short_description": f"{clean_name} — удачный выбор в категории «{category_text}» для ежедневного использования.",
        "full_description": (
            f"{clean_name} подойдёт покупателям, которые ищут практичный и аккуратно представленный товар "
            f"в категории «{category_text}». Средство легко добавить в регулярный уход или использовать как "
            f"универсальное решение для личной косметички.{detail_sentence}\n\n"
            "Описание можно дополнить конкретными преимуществами состава, объёмом, способом применения и типом кожи, "
            "если эти данные есть у продавца."
        ),
        "advantages": [
            "Понятное назначение для покупателя",
            "Подходит для регулярного использования",
            "Карточку легко дополнить характеристиками и фото",
        ],
        "call_to_action": "Добавьте товар в корзину и дополните уход подходящими средствами.",
    }


def parse_json_response(content: str) -> Optional[Dict]:
    """Парсит JSON из ответа AI"""
    if not isinstance(content, str) or not content.strip():
        return None
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
    specs = normalize_specs(specs)
    specs_text = "\n".join([f"- {k}: {v}" for k, v in specs.items()]) if specs else "- Нет характеристик"
    return (
        f"Создай продающее, но правдивое описание товара для интернет-магазина в формате JSON.\n"
        f"Название: {name}\n"
        f"Категория: {category or 'Не указана'}\n"
        f"Характеристики:\n{specs_text}\n\n"
        "Не выдумывай состав, объём, бренд, страну производства или лечебные свойства, если их нет в характеристиках.\n"
        "Для косметики не обещай медицинский эффект.\n"
        "Верни ТОЛЬКО JSON с полями: short_description, full_description, advantages, call_to_action."
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
        return (
            f"Пользователь спрашивает: {user_message}\n\n"
            "Дай короткий ответ для боковой панели магазина. "
            "Не добавляй список найденных товаров, цены и длинные подборки: они отображаются отдельными карточками."
        )


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
    temperature: float = 0.7,
    system_prompt_override: Optional[str] = None,
) -> str:
    """Синхронная версия для Django"""
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    system_prompt = system_prompt_override or (SYSTEM_PROMPT_JSON if response_format == "json" else SYSTEM_PROMPT_CHAT)
    
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

from products.models import CartItem, Order, Product


def get_products_with_prices(limit: int = 100) -> List[Dict]:
    """
    Получает товары с ценами для AI анализа
    """
    products = Product.objects.select_related('category').filter(stock__gt=0).order_by("-created_at")[:limit]
    
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


def _tokens(text: str) -> set:
    return {token for token in re.findall(r"[a-zа-яё0-9]+", text.lower()) if len(token) > 2}


def is_unhelpful_ai_answer(answer: str) -> bool:
    if not isinstance(answer, str) or not answer.strip():
        return True
    normalized = answer.strip().lower()
    service_markers = ("user safety:", "safety:", "safe", "unsafe", "policy:")
    if normalized in {"safe", "user safety: safe"}:
        return True
    return any(normalized.startswith(marker) for marker in service_markers)


def build_compact_chat_fallback(user_query: str, semantic_result: Dict[str, Any]) -> str:
    recommendations = semantic_result.get("recommendations", [])
    if recommendations:
        categories = []
        for rec in recommendations[:3]:
            category = (rec.get("product") or {}).get("category")
            if category and category not in categories:
                categories.append(category)
        category_text = ", ".join(categories) if categories else "подходящих товаров"
        return (
            f"Нашёл несколько вариантов под запрос «{user_query.strip()}».\n"
            f"Начните с категории: {category_text}.\n"
            "Ниже показал самые подходящие товары из каталога."
        )
    questions = semantic_result.get("clarifying_questions", [])
    if questions:
        return f"Нужно немного уточнить запрос.\n{questions[0]}"
    return "Не нашёл точного совпадения. Попробуйте указать бюджет, категорию или назначение товара."


def _product_search_text(product: Dict[str, Any]) -> str:
    specs = product.get("specs") or {}
    specs_text = " ".join([f"{key} {value}" for key, value in specs.items()])
    return " ".join(
        [
            product.get("name", ""),
            product.get("category", ""),
            product.get("description", ""),
            specs_text,
        ]
    )


def enrich_recommendations(raw_recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched_recommendations = []
    seen_products = set()
    for rec in raw_recommendations:
        product = Product.objects.select_related("category").filter(id=rec.get("product_id")).first()
        if product and product.id not in seen_products:
            seen_products.add(product.id)
            image = ""
            if product.image:
                try:
                    image = product.image.url
                except ValueError:
                    image = str(product.image)
            enriched_recommendations.append(
                {
                    **rec,
                    "product_id": str(product.id),
                    "name": rec.get("name") or product.name,
                    "price": float(product.price),
                    "product": {
                        "id": str(product.id),
                        "name": product.name,
                        "price": float(product.price),
                        "description": product.description,
                        "category": product.category.name if product.category else None,
                        "image": image,
                        "stock": product.stock,
                    },
                }
            )
    return enriched_recommendations


def fallback_rank_products(user_query: str, products: List[Dict[str, Any]], limit: int = 6) -> List[Dict[str, Any]]:
    query_tokens = _tokens(user_query)
    lower_query = user_query.lower()
    gift_tokens = {"подар", "жене", "девуш", "женщ", "подруг", "маме", "сестре"}
    beauty_tokens = {"космет", "уход", "сыворот", "крем", "маск"}
    tech_tokens = {"телефон", "ноутбук", "техника", "гаджет", "наушник", "часы"}
    home_tokens = {"дом", "уют", "кухн", "свеч", "плед"}
    scored = []
    for product in products:
        search_text = _product_search_text(product).lower()
        product_tokens = _tokens(search_text)
        score = len(query_tokens & product_tokens) * 3

        if any(token in lower_query for token in gift_tokens):
            if any(word in search_text for word in ("подар", "космет", "аксессуар", "уход", "дом и уют", "книг", "платье", "серьги", "свеч")):
                score += 8
        if any(token in lower_query for token in beauty_tokens) and any(word in search_text for word in ("космет", "уход", "сыворот", "крем", "маск")):
            score += 7
        if any(token in lower_query for token in tech_tokens) and any(word in search_text for word in ("техника", "телефон", "наушник", "часы", "камера")):
            score += 7
        if any(token in lower_query for token in home_tokens) and any(word in search_text for word in ("дом", "уют", "кухн", "свеч", "плед")):
            score += 6

        if score:
            scored.append((score, product))

    if not scored:
        scored = [(1, product) for product in products[:limit]]

    scored.sort(key=lambda item: (-item[0], item[1]["price"]))
    picked = []
    seen_names = set()
    for score, product in scored:
        name_key = product["name"].strip().lower()
        if name_key in seen_names:
            continue
        seen_names.add(name_key)
        picked.append((score, product))
        if len(picked) >= limit:
            break

    return [
        {
            "product_id": product["id"],
            "name": product["name"],
            "price": product["price"],
            "why_fits": "Подходит по смыслу запроса и доступен в наличии",
            "price_rating": "средний",
        }
        for _, product in picked
    ]


def get_user_context(user=None) -> Dict[str, Any]:
    if not user or not getattr(user, "is_authenticated", False):
        return {
            "is_authenticated": False,
            "cart": [],
            "recent_purchases": [],
            "recent_views": [],
            "preferred_categories": [],
        }

    cart = [
        {
            "product_id": str(item.product_id),
            "name": item.product.name,
            "category": item.product.category.name if item.product.category else None,
            "quantity": item.quantity,
        }
        for item in CartItem.objects.select_related("product", "product__category").filter(user=user)[:20]
    ]

    recent_orders = (
        Order.objects.filter(user=user)
        .prefetch_related("items", "items__product", "items__product__category")
        .order_by("-created_at")[:5]
    )
    recent_purchases = []
    category_counts = {}
    for order in recent_orders:
        for item in order.items.all():
            category_name = item.product.category.name if item.product.category else None
            if category_name:
                category_counts[category_name] = category_counts.get(category_name, 0) + item.quantity
            recent_purchases.append(
                {
                    "product_id": str(item.product_id),
                    "name": item.product.name,
                    "category": category_name,
                    "quantity": item.quantity,
                }
            )

    try:
        from .models import ProductViewEvent

        recent_views = [
            {
                "product_id": str(event.product_id),
                "name": event.product.name,
                "category": event.product.category.name if event.product.category else None,
                "query": event.query,
            }
            for event in ProductViewEvent.objects.select_related("product", "product__category").filter(user=user)[:20]
        ]
        for view in recent_views:
            category_name = view.get("category")
            if category_name:
                category_counts[category_name] = category_counts.get(category_name, 0) + 1
    except Exception:
        recent_views = []

    preferred_categories = [
        category for category, _ in sorted(category_counts.items(), key=lambda item: item[1], reverse=True)[:5]
    ]

    return {
        "is_authenticated": True,
        "cart": cart,
        "recent_purchases": recent_purchases[:20],
        "recent_views": recent_views,
        "preferred_categories": preferred_categories,
    }


def build_semantic_search_prompt(user_query: str, products: List[Dict], user_context: Dict[str, Any]) -> str:
    products_text = "\n".join(
        [
            f"{product['id']} | {product['name']} | {product['price']}₽ | {product['category']} | "
            f"{product['description'][:220]} | specs: {json.dumps(product.get('specs') or {}, ensure_ascii=False)}"
            for product in products[:80]
        ]
    )
    return f"""
Ты AI-поисковик интернет-магазина. Найди товары по смыслу, а не только по точным словам.

Запрос пользователя: "{user_query}"

Контекст пользователя:
{json.dumps(user_context, ensure_ascii=False)}

Каталог:
{products_text}

Если запрос слишком широкий, верни 1-3 уточняющих вопроса. Если товаров достаточно, верни лучшие совпадения.

Верни ТОЛЬКО JSON:
{{
  "understanding": "что понял из запроса",
  "clarifying_questions": ["вопрос 1"],
  "recommendations": [
    {{
      "product_id": "id товара из каталога",
      "name": "название",
      "price": 1000,
      "why_fits": "почему подходит",
      "price_rating": "бюджетный/средний/премиум"
    }}
  ],
  "budget_advice": "совет по бюджету",
  "alternative_advice": "что уточнить или чем заменить"
}}
"""


def semantic_search_products(user_query: str, user=None, limit: int = 6) -> Dict[str, Any]:
    products = get_products_with_prices(limit=120)
    user_context = get_user_context(user)
    if not products:
        return {
            "understanding": "В магазине пока нет товаров",
            "clarifying_questions": [],
            "recommendations": [],
            "budget_advice": None,
            "alternative_advice": "Добавьте товары в каталог",
            "context": user_context,
        }

    prompt = build_semantic_search_prompt(user_query, products, user_context)
    response = ask_ai_sync(prompt, response_format="json", temperature=0.35)
    parsed = parse_json_response(response)

    if parsed:
        recommendations = enrich_recommendations(parsed.get("recommendations", []))[:limit]
        if recommendations:
            return {
                "understanding": parsed.get("understanding", ""),
                "clarifying_questions": parsed.get("clarifying_questions", []),
                "recommendations": recommendations,
                "budget_advice": parsed.get("budget_advice"),
                "alternative_advice": parsed.get("alternative_advice"),
                "context": user_context,
            }

    fallback = enrich_recommendations(fallback_rank_products(user_query, products, limit=limit))
    return {
        "understanding": "Подобрал товары по совпадениям в названии, описании и характеристиках",
        "clarifying_questions": ["Какой бюджет и какие характеристики для вас важнее всего?"],
        "recommendations": fallback,
        "budget_advice": None,
        "alternative_advice": "Уточните назначение, бюджет или желаемую категорию",
        "context": user_context,
    }


def get_personal_recommendations(user=None, limit: int = 6) -> Dict[str, Any]:
    context = get_user_context(user)
    query = "Подбери персональные рекомендации по истории покупок, просмотров и корзине"
    result = semantic_search_products(query, user=user, limit=limit)
    result["personal_context"] = context
    return result


def build_bundle_prompt(user_query: str, products: List[Dict], user_context: Dict[str, Any]) -> str:
    products_text = "\n".join(
        [
            f"{product['id']} | {product['name']} | {product['price']}₽ | {product['category']} | {product['description'][:160]}"
            for product in products[:80]
        ]
    )
    return f"""
Ты комплектовщик интернет-магазина. Нужно собрать готовую подборку товаров.

Запрос: "{user_query}"
Контекст пользователя:
{json.dumps(user_context, ensure_ascii=False)}

Каталог:
{products_text}

Правила:
- Подбери 2-6 совместимых товаров.
- Не добавляй товары, которых нет в каталоге.
- Если запрос неясный, верни уточняющие вопросы.

Верни ТОЛЬКО JSON:
{{
  "title": "название комплекта",
  "occasion": "повод или сценарий",
  "clarifying_questions": [],
  "items": [
    {{"product_id": "id товара", "role": "зачем нужен в комплекте", "quantity": 1}}
  ],
  "total_estimate": 1000,
  "explanation": "почему комплект цельный"
}}
"""


def build_bundle(user_query: str, user=None) -> Dict[str, Any]:
    products = get_products_with_prices(limit=120)
    user_context = get_user_context(user)
    if not products:
        return {
            "title": "Комплект недоступен",
            "occasion": user_query,
            "clarifying_questions": [],
            "items": [],
            "total_estimate": 0,
            "explanation": "В каталоге пока нет товаров",
            "context": user_context,
        }

    response = ask_ai_sync(build_bundle_prompt(user_query, products, user_context), response_format="json", temperature=0.45)
    parsed = parse_json_response(response) or {}
    item_ids = [item.get("product_id") for item in parsed.get("items", [])]
    products_by_id = {
        str(product.id): product
        for product in Product.objects.select_related("category").filter(id__in=item_ids, stock__gt=0)
    }

    items = []
    for item in parsed.get("items", []):
        product = products_by_id.get(str(item.get("product_id")))
        if not product:
            continue
        try:
            quantity = max(1, int(item.get("quantity") or 1))
        except (TypeError, ValueError):
            quantity = 1
        items.append(
            {
                "product_id": str(product.id),
                "role": item.get("role") or "Подходит к комплекту",
                "quantity": quantity,
                "product": {
                    "id": str(product.id),
                    "name": product.name,
                    "price": float(product.price),
                    "description": product.description,
                    "category": product.category.name if product.category else None,
                    "stock": product.stock,
                },
            }
        )

    if not items:
        fallback_items = enrich_recommendations(fallback_rank_products(user_query, products, limit=4))
        items = [
            {
                "product_id": rec["product_id"],
                "role": rec.get("why_fits", "Подходит к запросу"),
                "quantity": 1,
                "product": rec["product"],
            }
            for rec in fallback_items
        ]

    total_estimate = sum(item["product"]["price"] * item["quantity"] for item in items)
    return {
        "title": parsed.get("title") or "AI-комплект",
        "occasion": parsed.get("occasion") or user_query,
        "clarifying_questions": parsed.get("clarifying_questions", []),
        "items": items,
        "total_estimate": total_estimate,
        "explanation": parsed.get("explanation") or "Собрано по смыслу запроса и наличию товаров",
        "context": user_context,
    }


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
