# Календарь встреч

Корпоративный инструмент для управления встречами. Сотрудник добавляет встречу, указывает участников и время - система автоматически проверяет конфликты.

## Стек

**FastAPI** - роутинг и API, минимальная конфигурация, хорошая поддержка Pydantic из коробки.

**Jinja2** - серверный рендеринг шаблонов. Наследование через `extends/block`, переиспользуемые частицы через `include`. Без сборщиков и фреймворков на фронте.

**PostgreSQL + psycopg2** - хранение встреч и пользователей. `RealDictCursor` для словарного доступа к строкам.

**Vanilla JS** - только для прогрессивного улучшения: отправка формы через `fetch`, инлайн-отображение конфликта без перезагрузки страницы.

**flatpickr** (CDN) - красивый выбор даты и времени.

## Запуск локально

```bash
pip install -r requirements.txt

# нужна переменная с подключением к БД
export DATABASE_URL=postgresql://user:password@host:5432/dbname

uvicorn app.main:app --reload
```

Открыть: http://localhost:8000

Логин по умолчанию: `worker` / `worker123`

## Деплой (Render + Supabase)

1. Создать проект на [supabase.com](https://supabase.com), скопировать Connection String из Project Settings -> Database
2. Создать Web Service на [render.com](https://render.com), подключить этот репозиторий
3. В Environment Variables добавить `DATABASE_URL` со строкой из Supabase
4. Build command: `pip install -r requirements.txt`
5. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Таблицы создаются автоматически при первом запуске.

## Структура

```
app/
  main.py          - точка входа, монтирование роутеров
  database.py      - подключение к БД, инициализация таблиц, seed-данные
  models.py        - Pydantic-схемы запросов и ответов
  repository.py    - все SQL-запросы, проверка конфликтов
  router/
    pages.py       - HTML-маршруты, cookie-авторизация
    meetings.py    - JSON API для встреч

templates/         - Jinja2-шаблоны с наследованием
static/            - CSS и JS
```

## Логика конфликтов

Встреча блокируется, если хотя бы один участник занят в это время. Проверка: `start_time < new_end AND end_time > new_start` по всем участникам.
