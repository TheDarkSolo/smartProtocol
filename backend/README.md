# Smart Protocol — бэкенд

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Документация API: http://localhost:8000/docs

## Что здесь есть сейчас
- `GET /api/health`
- `GET /api/config` — цена документа, значение МРП, лимиты загрузки
- `POST /api/cases` — приём постановления, создание дела

## Чего ещё нет (этап 1 по ROADMAP.md)
Разбор PDF, подбор оснований, генерация жалобы, PDF на выходе, оплата.
