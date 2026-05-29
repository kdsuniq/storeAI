# store_with_AI
<a href='https://github.com/kdsuniq/store_with_AI/wiki/Документация'>Документация</a>

# Инструкция по сбеорке проекта

сначала получаем токен на сайте

```
openrouter.ai
```
создаем файл .env и добавляем в него
```
OPENAI_API_KEY=ВАШ-КЛЮЧ
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

