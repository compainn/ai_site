from flask import Flask, render_template, request, jsonify, session
from openai import AsyncOpenAI
import asyncio
from functools import wraps
import re
import uuid
import secrets
from datetime import timedelta
import os

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.permanent_session_lifetime = timedelta(days=30)

# Конфигурация из твоего бота
OPENROUTER_API_KEY = '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'
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

MODELS = [
    "allenai/molmo-2-8b:free",
    'xiaomi/mimo-v2-flash:free',
    'nvidia/nemotron-3-nano-30b-a3b:free',
    'mistralai/devstral-2512:free',
    'arcee-ai/trinity-mini:free',
    'liquid/lfm-2.5-1.2b-thinking:free',
    'arcee-ai/trinity-large-preview:free',
    'tngtech/tng-r1t-chimera:free',
    'nvidia/nemotron-nano-12b-v2-vl:free',
    'qwen/qwen3-next-80b-a3b-instruct:free',
    'nvidia/nemotron-nano-9b-v2:free',
    'openai/gpt-oss-120b:free',
    'openai/gpt-oss-20b:free',
    'z-ai/glm-4.5-air:free',
    'qwen/qwen3-coder:free',
    'tngtech/deepseek-r1t2-chimera:free'
]

SYSTEM_PROMPT = """Твоё имя — Pulse. Ты — AI-ассистент.

ВАЖНЫЕ ПРАВИЛА:
1. НИКОГДА не упоминай, что ты Qwen, Llama, GPT-4 или другая модель
2. Если тебя спросят "кто ты?", отвечай: "Я Pulse, твой AI-помощник\nвеб-сайт: https://pulse-ai.ru/"
3. Если тебя спросят "кто тебя создал?", отвечай: "Меня создала команда Pulse."
4. Если спросят ИМЕННО "как дела?", отвечай: "Отлично, а у вас?" и продолжай диалог
5. Будь серьезным и отвечай по делу
6. Не рассказывай о своих технических характеристиках
7. Никогда не упоминай компанию, которая тебя создала"""

MAX_CONTEXT_LENGTH = 10

ai_client = AsyncOpenAI(
    base_url=OPENROUTER_BASE_URL,
    api_key=OPENROUTER_API_KEY,
)

# Хранилище контекста для сессий
context_storage = {}


def get_session_id():
    """Получить или создать ID сессии"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']


def get_context(session_id):
    """Получить контекст для сессии"""
    if session_id not in context_storage:
        context_storage[session_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    return context_storage[session_id]


def trim_context(session_id):
    """Обрезать контекст"""
    context = context_storage[session_id]
    if len(context) > MAX_CONTEXT_LENGTH:
        system_msg = context[0]
        recent_msgs = context[-(MAX_CONTEXT_LENGTH - 1):]
        context_storage[session_id] = [system_msg] + recent_msgs


def clean_response(text):
    """Очистка ответа от спецсимволов"""
    if not text:
        return text

    if '```' in text:
        parts = text.split('```')
        result = []

        for i, part in enumerate(parts):
            if i % 2 == 0:
                part = part.replace('^2', '²').replace('^3', '³')
                part = re.sub(r'\\(?:frac|left|right|cdot|times|[()\[\]])', '', part)
                part = part.replace('\\(', '').replace('\\)', '')
                part = part.replace('\\[', '').replace('\\]', '')
                part = part.replace('$', '')
                part = re.sub(r'`([^`]+)`', r'CODE:\1:CODE', part)
                part = part.replace('**', '').replace('__', '')
                part = part.replace('*', '').replace('_', '')
                part = part.replace('CODE:', '`').replace(':CODE', '`')
                result.append(part)
            else:
                result.append(f'```{part}```')

        text = ''.join(result)
    else:
        text = text.replace('^2', '²').replace('^3', '³')
        text = re.sub(r'\\(?:frac|left|right|cdot|times|[()\[\]])', '', text)
        text = text.replace('\\(', '').replace('\\)', '')
        text = text.replace('\\[', '').replace('\\]', '')
        text = text.replace('$', '')
        text = text.replace('**', '').replace('__', '')
        text = text.replace('*', '').replace('_', '')

    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith('- '):
            cleaned_lines.append(stripped[2:])
        else:
            cleaned_lines.append(line)

    return '\n'.join(cleaned_lines).strip()


def async_route(f):
    """Декоратор для асинхронных маршрутов"""

    @wraps(f)
    def wrapped(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapped


@app.route('/')
def index():
    """Главная страница"""
    session_id = get_session_id()
    # Создаем контекст если его нет
    get_context(session_id)
    return render_template('index.html')


@app.route('/clear', methods=['POST'])
def clear_context():
    """Очистить контекст"""
    session_id = get_session_id()
    context_storage[session_id] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    return jsonify({'status': 'success', 'message': 'История очищена'})


@app.route('/chat', methods=['POST'])
@async_route
async def chat():
    """Обработка сообщений"""
    try:
        data = request.json
        message = data.get('message', '').strip()

        if not message:
            return jsonify({'error': 'Пустое сообщение'}), 400

        session_id = get_session_id()
        context = get_context(session_id)

        # Добавляем сообщение пользователя
        context.append({"role": "user", "content": message})

        last_error = None

        # Пробуем модели по очереди
        for model in MODELS:
            try:
                response = await ai_client.chat.completions.create(
                    model=model,
                    messages=context,
                    max_tokens=2000,
                    temperature=0.7,
                )

                answer = response.choices[0].message.content
                clean_answer = clean_response(answer)

                # Добавляем ответ в контекст
                context.append({"role": "assistant", "content": answer})
                trim_context(session_id)

                return jsonify({
                    'response': clean_answer,
                    'status': 'success'
                })

            except Exception as e:
                last_error = str(e)
                error = str(e)
                if "429" in error or "Rate limit" in error or "rate" in error.lower():
                    continue
                continue

        # Если все модели не сработали
        if context[-1]["role"] == "user":
            context.pop()

        return jsonify({
            'error': 'Не удалось получить ответ от моделей',
            'details': str(last_error)
        }), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/new_chat', methods=['POST'])
def new_chat():
    """Начать новый чат"""
    session_id = get_session_id()
    context_storage[session_id] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    return jsonify({'status': 'success', 'message': 'Новый чат создан'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
