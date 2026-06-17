# Store with AI

Маркетплейс с AI-помощником: отдельная регистрация покупателей и продавцов, подтверждение email, оплата (YooKassa / mock), админ-панель.

## Быстрый старт (локально)

```bash
cd store_with_AI/backend
cp .env.example .env
# Добавьте OPENROUTER_API_KEY в .env
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

```bash
cd store_with_AI/frontend
npm i
npm run dev
```

- Frontend: http://127.0.0.1:5173
- API / Swagger: http://127.0.0.1:8000/api/schema/swagger-ui/
- Django Admin: http://127.0.0.1:8000/admin/

## Роли

| Роль | Регистрация | Возможности |
|------|-------------|-------------|
| **Покупатель** | `/auth/buyer` | Каталог, корзина, AI, заказы |
| **Продавец** | `/auth/seller` | Публикация товаров, входящие заказы, AI-аналитика |
| **Админ** | `createsuperuser` | `/admin` в SPA + Django Admin |

## Email

В dev письма выводятся в консоль backend (`EMAIL_BACKEND=console`).

Для production (Yandex SMTP) в `.env`:

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.yandex.ru
EMAIL_PORT=587
EMAIL_HOST_USER=your@yandex.ru
EMAIL_HOST_PASSWORD=app-password
EMAIL_USE_TLS=1
FRONTEND_URL=https://your-domain.ru
```

## Оплата

Без ключей YooKassa заказы **автоматически помечаются оплаченными** (mock-режим для разработки).

Для production:

```
YOOKASSA_SHOP_ID=...
YOOKASSA_SECRET_KEY=...
```

Webhook: `POST /api/products/payments/webhook/`

## Деплой в Yandex Cloud

1. Создайте Container Registry, получите `REGISTRY_ID`
2. Настройте Managed Kubernetes
3. Скопируйте секреты: `cp k8s/secret.example.yaml k8s/secret.yaml` и заполните
4. Обновите `FRONTEND_URL` в `k8s/configmap.yaml`
5. Замените `<REGISTRY_ID>` в `k8s/backend.yaml` и `k8s/frontend.yaml`

```bash
export REGISTRY_ID=crpXXXXXXXX
chmod +x deploy.sh
./deploy.sh
```

После деплоя:

```bash
kubectl exec -it deploy/backend -n store-ai -- python manage.py createsuperuser
kubectl get svc frontend -n store-ai
```

## AI

Получите ключ на https://openrouter.ai и добавьте в `.env`:

```
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=openrouter/free
```

Без ключа AI работает в fallback-режиме (базовые рекомендации по каталогу).


## Фикстуры
Файлы для начального заполнения базы данных

Создание фикстур и определенной products.category
```
python manage.py dumpdata products.category --indent 2 > products/fixtures/categories.json
```
Загрузка данных из фикстур 
```
python manage.py loaddata products/fixtures/categories.json 
python manage.py loaddata products/fixtures/products.json
```




## Удаление данных товаров для создания заново
```
python manage.py shell -c "from products.models import Product; Product.objects.all().delete()"