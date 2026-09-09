"""Тонкий клиент DeepSeek (OpenAI-совместимый chat/completions).

Используется ровно для одной задачи — связного изложения фактов, которые уже
сообщил пользователь (см. app/services/appeal_draft.py). Модель не решает,
какие нормы права применимы, и не подставляет ссылки на статьи: это делает
шаблон из данных knowledge/articles.yaml. Такое разделение — единственная
гарантия того, что в документе для суда не появится несуществующая статья.
"""

import httpx

from ..config import settings


class DeepSeekError(RuntimeError):
    """Не удалось получить ответ от DeepSeek — вызывающий код обязан иметь
    запасной путь и никогда не должен падать целиком из-за недоступности LLM."""


async def complete(system_prompt: str, user_prompt: str, *, max_tokens: int = 700) -> str:
    if not settings.deepseek_api_key:
        raise DeepSeekError("DEEPSEEK_API_KEY не задан")

    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    headers = {"Authorization": f"Bearer {settings.deepseek_api_key}"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.deepseek_base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise DeepSeekError(f"DeepSeek недоступен: {exc}") from exc

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:
        raise DeepSeekError(f"Неожиданный формат ответа DeepSeek: {data}") from exc
