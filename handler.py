import base64
import json
import os
import urllib.error
import urllib.request

TELEGRAM_API_BASE = "https://api.telegram.org"
YANDEXGPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
HTTP_TIMEOUT = 20


def parse_update(update):
    message = update.get("message") or {}
    edited_message = update.get("edited_message") or {}

    text = message.get("text") or edited_message.get("text")
    chat = message.get("chat") or edited_message.get("chat") or {}
    chat_id = chat.get("id")

    return chat_id, text


def escape_markdown(text):
    if text is None:
        return ""
    escape_chars = "_[]()~`>#+-=|{}.!*\\"
    return "".join(f"\\{ch}" if ch in escape_chars else ch for ch in text)


def format_reply(data):
    lines = [
        f"Type: {escape_markdown(data['type'])}",
        f"Title: {escape_markdown(data['title'])}",
        f"Priority: {escape_markdown(data['priority'])}",
        f"Due: {escape_markdown(data['due'] or '—')}",
    ]

    tags = data.get("tags") or []
    if tags:
        lines.append("Tags: " + ", ".join(escape_markdown(tag) for tag in tags))
    else:
        lines.append("Tags: —")

    actions = data.get("action_items") or []
    if actions:
        lines.append("Steps:")
        lines.extend(f"• {escape_markdown(item)}" for item in actions)
    else:
        lines.append("Steps: —")

    questions = data.get("questions") or []
    if questions:
        lines.append("Questions:")
        lines.extend(f"• {escape_markdown(item)}" for item in questions)
    else:
        lines.append("Questions: —")

    return "\n".join(lines)


def call_yandexgpt(text, api_key, folder_id, temperature):
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "type",
            "title",
            "clean_text",
            "due",
            "priority",
            "tags",
            "action_items",
            "questions",
        ],
        "properties": {
            "type": {"type": "string", "enum": ["task", "reminder", "note", "other"]},
            "title": {"type": "string"},
            "clean_text": {"type": "string"},
            "due": {"type": ["string", "null"]},
            "priority": {"type": "string", "enum": ["low", "medium", "high"]},
            "tags": {"type": "array", "items": {"type": "string"}},
            "action_items": {"type": "array", "items": {"type": "string"}},
            "questions": {"type": "array", "items": {"type": "string"}},
        },
    }

    payload = {
        "modelUri": f"gpt://{folder_id}/yandexgpt-lite/latest",
        "completionOptions": {
            "stream": False,
            "temperature": temperature,
            "maxTokens": 800,
        },
        "messages": [
            {
                "role": "system",
                "text": (
                    "You are a helpful assistant. Extract a structured note. "
                    "Return only JSON that строго соответствует schema."
                ),
            },
            {"role": "user", "text": text},
        ],
        "jsonSchema": schema,
    }

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        YANDEXGPT_URL,
        data=data,
        headers={
            "Authorization": f"Api-Key {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        raw = response.read().decode("utf-8")
    body = json.loads(raw)

    alternatives = body.get("result", {}).get("alternatives", [])
    if not alternatives:
        raise ValueError("Empty alternatives")

    message = alternatives[0].get("message", {})
    text_response = message.get("text")
    if not text_response:
        raise ValueError("Empty response text")

    return json.loads(text_response)


def telegram_send_message(chat_id, text, token):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True,
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{TELEGRAM_API_BASE}/bot{token}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        response.read()


def handler(event, context):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    api_key = os.getenv("YC_API_KEY")
    folder_id = os.getenv("YC_FOLDER_ID")

    body = event.get("body")
    if event.get("isBase64Encoded") and body:
        body = base64.b64decode(body).decode("utf-8")

    try:
        update = json.loads(body or "{}")
    except json.JSONDecodeError:
        return {"statusCode": 200, "body": "ok"}

    chat_id, text = parse_update(update)
    if not chat_id:
        return {"statusCode": 200, "body": "ok"}

    if not text:
        if token:
            try:
                telegram_send_message(chat_id, "Пришли текст заметки.", token)
            except urllib.error.URLError:
                pass
        return {"statusCode": 200, "body": "ok"}

    if not (token and api_key and folder_id):
        return {"statusCode": 200, "body": "ok"}

    try:
        result = call_yandexgpt(text, api_key, folder_id, temperature=0.2)
    except (ValueError, json.JSONDecodeError, urllib.error.URLError):
        result = None

    if result is None:
        try:
            result = call_yandexgpt(text, api_key, folder_id, temperature=0.0)
        except (ValueError, json.JSONDecodeError, urllib.error.URLError):
            result = None

    if result is None:
        reply = "Не получилось распознать заметку, переформулируй."
    else:
        try:
            reply = format_reply(result)
        except (KeyError, TypeError):
            reply = "Не получилось распознать заметку, переформулируй."

    try:
        telegram_send_message(chat_id, reply, token)
    except urllib.error.URLError:
        pass

    return {"statusCode": 200, "body": "ok"}
