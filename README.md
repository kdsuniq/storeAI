# store_with_AI
<a href='https://github.com/kdsuniq/store_with_AI/wiki/Документация'>Документация</a>

# Инструкция по сбеорке проекта

сначала получаем токен на сайте

```
openrouter.ai
```
создаем файл .env и добавляем в него
```
OPENROUTER_API_KEY=ВАШ-КЛЮЧ
OPENROUTER_MODEL=openrouter/free
```

далее в терминале
```
cd frontend
```

```
npm i
```

```
npm run dev
```

в новом терминале
```
cd backend
```

```
python3 -m venv venv
```

```
source venv/bin/activate
```

```
pip install -r requirements.txt
```

```
python manage.py migrate
```

```
python manage.py runserver
```

Бэкенд после запуска доступен по адресу:
```
http://127.0.0.1:8000/
```

Swagger-документация API:
```
http://127.0.0.1:8000/api/schema/swagger-ui/
```
