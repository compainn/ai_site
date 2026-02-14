from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from openai import AsyncOpenAI
import asyncio
from functools import wraps
import re
import uuid
import secrets
from datetime import datetime, timedelta
import os
from authlib.integrations.flask_client import OAuth
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.permanent_session_lifetime = timedelta(days=30)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///pulse.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(100), unique=True)
    email = db.Column(db.String(100))
    name = db.Column(db.String(100))
    picture = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    chats = db.relationship('Chat', backref='user', lazy=True, cascade='all, delete-orphan',
                            order_by='desc(Chat.updated_at)')

class Chat(db.Model):
    __tablename__ = 'chats'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), default='Новый чат')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = db.relationship('Message', backref='chat', lazy=True, order_by='Message.created_at',
                               cascade='all, delete-orphan')

class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('chats.id'), nullable=False)
    role = db.Column(db.String(20))
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

app.config['GOOGLE_CLIENT_ID'] = '263568169592-0a49h298c3e9v7k5shqaksiun6b937hm.apps.googleusercontent.com'
app.config['GOOGLE_CLIENT_SECRET'] = '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'

oauth = OAuth(app)

google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

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
2. Если тебя спросят "кто ты?", отвечай: "Я Pulse, ваш AI-ассистент"
3. Если тебя спросят "кто тебя создал?", отвечай: "Меня создала команда Pulse."
4. Будь серьезным и отвечай по делу
5. Не рассказывай о своих технических характеристиках
6. Никогда не упоминай компанию, которая тебя создала"""

MAX_CONTEXT_LENGTH = 10

ai_client = AsyncOpenAI(
    base_url=OPENROUTER_BASE_URL,
    api_key=OPENROUTER_API_KEY,
)

context_storage = {}

def get_session_id():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

def get_context(session_id):
    if session_id not in context_storage:
        context_storage[session_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    return context_storage[session_id]

def trim_context(session_id):
    context = context_storage[session_id]
    if len(context) > MAX_CONTEXT_LENGTH:
        system_msg = context[0]
        recent_msgs = context[-(MAX_CONTEXT_LENGTH - 1):]
        context_storage[session_id] = [system_msg] + recent_msgs

def clean_response(text):
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
    @wraps(f)
    def wrapped(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapped

@app.route('/login/google')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/callback/google')
def google_callback():
    try:
        token = google.authorize_access_token()
        userinfo = google.get('https://openidconnect.googleapis.com/v1/userinfo').json()

        user = User.query.filter_by(google_id=userinfo['sub']).first()
        if not user:
            user = User(
                google_id=userinfo['sub'],
                email=userinfo['email'],
                name=userinfo.get('name', ''),
                picture=userinfo.get('picture', '')
            )
            db.session.add(user)
            db.session.commit()

        session['user'] = {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'picture': user.picture
        }
        session.permanent = True

        new_chat = Chat(
            user_id=user.id,
            title='Новый чат'
        )
        db.session.add(new_chat)
        db.session.commit()
        session['current_chat_id'] = new_chat.id

        print(f"✅ Успешный вход: {user.email}")
    except Exception as e:
        print(f"❌ Google auth error: {e}")
        import traceback
        traceback.print_exc()

    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('current_chat_id', None)
    return redirect(url_for('index'))

@app.route('/api/chats')
def get_chats():
    if not session.get('user'):
        return jsonify([])

    chats = Chat.query.filter_by(user_id=session['user']['id']).order_by(Chat.updated_at.desc()).all()
    return jsonify([{
        'id': chat.id,
        'title': chat.title,
        'created_at': chat.created_at.isoformat(),
        'updated_at': chat.updated_at.isoformat(),
        'message_count': len(chat.messages),
        'is_current': chat.id == session.get('current_chat_id')
    } for chat in chats])

@app.route('/api/chat/<int:chat_id>')
def get_chat(chat_id):
    if not session.get('user'):
        return jsonify({'error': 'Not logged in'}), 401

    chat = Chat.query.filter_by(id=chat_id, user_id=session['user']['id']).first()
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404

    return jsonify([{
        'role': msg.role,
        'content': msg.content,
        'created_at': msg.created_at.isoformat()
    } for msg in chat.messages])

@app.route('/api/chat/<int:chat_id>/load', methods=['POST'])
def load_chat(chat_id):
    if not session.get('user'):
        return jsonify({'error': 'Not logged in'}), 401

    chat = Chat.query.filter_by(id=chat_id, user_id=session['user']['id']).first()
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404

    session['current_chat_id'] = chat.id

    messages = []
    for msg in chat.messages:
        messages.append({"role": msg.role, "content": msg.content})

    context_storage[get_session_id()] = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    return jsonify({
        'success': True,
        'messages': [{
            'role': msg.role,
            'content': msg.content,
            'created_at': msg.created_at.isoformat()
        } for msg in chat.messages]
    })

@app.route('/api/chat/new', methods=['POST'])
def new_chat():
    if not session.get('user'):
        return jsonify({'error': 'Not logged in', 'message': 'Зарегистрируйтесь чтобы создавать чаты'}), 401

    new_chat = Chat(
        user_id=session['user']['id'],
        title='Новый чат'
    )
    db.session.add(new_chat)
    db.session.commit()

    session['current_chat_id'] = new_chat.id
    context_storage[get_session_id()] = [{"role": "system", "content": SYSTEM_PROMPT}]

    return jsonify({
        'success': True,
        'chat_id': new_chat.id,
        'title': new_chat.title
    })

@app.route('/api/chat/<int:chat_id>/delete', methods=['POST'])
def delete_chat(chat_id):
    if not session.get('user'):
        return jsonify({'error': 'Not logged in'}), 401

    chat = Chat.query.filter_by(id=chat_id, user_id=session['user']['id']).first()
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404

    db.session.delete(chat)
    db.session.commit()

    if session.get('current_chat_id') == chat_id:
        new_chat = Chat(
            user_id=session['user']['id'],
            title='Новый чат'
        )
        db.session.add(new_chat)
        db.session.commit()
        session['current_chat_id'] = new_chat.id
        context_storage[get_session_id()] = [{"role": "system", "content": SYSTEM_PROMPT}]

    return jsonify({'success': True})

@app.route('/')
def index():
    session_id = get_session_id()
    messages_data = []

    if session.get('user') and session.get('current_chat_id'):
        chat = Chat.query.get(session['current_chat_id'])
        if chat and chat.messages:
            messages = []
            for msg in chat.messages:
                messages.append({"role": msg.role, "content": msg.content})
                messages_data.append({
                    'role': msg.role,
                    'content': msg.content
                })
            context_storage[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
            print(f"✅ Загружено {len(messages_data)} сообщений для чата {chat.id}")

    return render_template('index.html',
                           user=session.get('user'),
                           messages=messages_data)

@app.route('/clear', methods=['POST'])
def clear_context():
    if session.get('user') and session.get('current_chat_id'):
        Message.query.filter_by(chat_id=session['current_chat_id']).delete()
        db.session.commit()

    session_id = get_session_id()
    context_storage[session_id] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    return jsonify({'status': 'success', 'message': 'История очищена'})

@app.route('/chat', methods=['POST'])
@async_route
async def chat():
    try:
        data = request.json
        message = data.get('message', '').strip()

        if not message:
            return jsonify({'error': 'Пустое сообщение'}), 400

        session_id = get_session_id()
        context = get_context(session_id)
        context.append({"role": "user", "content": message})

        last_error = None

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

                context.append({"role": "assistant", "content": answer})
                trim_context(session_id)

                if session.get('user') and session.get('current_chat_id'):
                    user_msg = Message(
                        chat_id=session['current_chat_id'],
                        role='user',
                        content=message
                    )
                    db.session.add(user_msg)

                    assistant_msg = Message(
                        chat_id=session['current_chat_id'],
                        role='assistant',
                        content=answer
                    )
                    db.session.add(assistant_msg)

                    chat_obj = Chat.query.get(session['current_chat_id'])
                    if len(chat_obj.messages) == 2:
                        chat_obj.title = message[:50] + ('...' if len(message) > 50 else '')

                    chat_obj.updated_at = datetime.utcnow()
                    db.session.commit()

                return jsonify({
                    'response': clean_answer,
                    'status': 'success'
                })

            except Exception as e:
                last_error = str(e)
                if "429" in str(e) or "Rate limit" in str(e) or "rate" in str(e).lower():
                    continue
                continue

        if context[-1]["role"] == "user":
            context.pop()

        return jsonify({
            'error': 'Не удалось получить ответ от моделей',
            'details': str(last_error)
        }), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Ошибка при создании бдшки: {e}")

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
