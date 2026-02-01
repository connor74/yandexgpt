# Telegram webhook → YandexGPT (Yandex Cloud Functions)

## План
1. Принять Telegram update JSON и достать текст.
2. Вызвать YandexGPT completion с JSON schema.
3. Отформатировать результат и отправить его в Telegram.
4. Всегда отвечать `statusCode=200`.

## handler.py
См. `handler.py`.

## Как задеплоить
1. Переменные окружения:
   - `TELEGRAM_BOT_TOKEN`
   - `YC_API_KEY`
   - `YC_FOLDER_ID`
2. Залейте функцию в Yandex Cloud Functions (Python 3.10+).
3. В API Gateway укажите проксирование на HTTP функцию.
4. Установите webhook в Telegram:
   ```bash
   curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
     -d "url=https://<API_GATEWAY_URL>"
   ```
   Здесь `API_GATEWAY_URL` — URL вашего API Gateway.

## Пример
Входной update:
```json
{
  "update_id": 123,
  "message": {
    "message_id": 10,
    "chat": {"id": 42, "type": "private"},
    "text": "Напомни завтра в 9:00 отправить отчет клиенту"
  }
}
```

Ожидаемый ответ в чат (пример):
```
Type: reminder
Title: Отправить отчет клиенту
Priority: medium
Due: 2024-10-12T09:00:00+03:00
Tags: отчет, клиент
Steps:
• Сформировать отчет
• Отправить клиенту
Questions:
• Уточнить формат отчета?
```
