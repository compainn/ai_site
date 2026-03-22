from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from groq import Groq
import re
import uuid
import secrets
from datetime import datetime, timedelta
import os
from authlib.integrations.flask_client import OAuth
from flask_sqlalchemy import SQLAlchemy
import hmac
import hashlib
import time

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
    telegram_id = db.Column(db.String(100), unique=True)
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
app.config['GOOGLE_CLIENT_ID'] = '392453659452-mbmjcs902ojveis5vh9csjlb462ofriv.apps.googleusercontent.com'
app.config['GOOGLE_CLIENT_SECRET'] = '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'
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile',
        'redirect_uri': 'https://pulsex.tech/callback/google'
    },
)
TELEGRAM_BOT_TOKEN = '8569563154:AAGnzJutAFQNUSpMlKQlSKv9MFaaCtRFyFw'
OPENROUTER_API_KEY = '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'
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODELS = [
    "allenai/molmo-2-8b",
    'xiaomi/mimo-v2-flash',
    'nvidia/nemotron-3-nano-30b-a3b:free',
    'mistralai/devstral-2512',
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
    'tngtech/deepseek-r1t2-chimera:free',
    'stepfun/step-3.5-flash:free',
    'upstage/solar-pro-3:free',
    'liquid/lfm-2.5-1.2b-instruct:free',
    'cognitivecomputations/dolphin-mistral-24b-venice-edition:free',
    'google/gemma-3n-e2b-it:free',
    'deepseek/deepseek-r1-0528:free',
    'google/gemma-3n-e4b-it:free',
    'qwen/qwen3-4b:free',
    'mistralai/mistral-small-3.1-24b-instruct:free',
    'google/gemma-3-4b-it:free',
    'google/gemma-3-12b-it:free',
    'google/gemma-3-27b-it:free',
    'meta-llama/llama-3.3-70b-instruct:free',
    'meta-llama/llama-3.2-3b-instruct:free',
    'nousresearch/hermes-3-llama-3.1-405b:free'
]
SYSTEM_PROMPT = """Твоё имя — Pulse. Ты — AI-ассистент.
Важные правила:
1. НИКОГДА не упоминай, что ты Qwen, Llama, GPT-4 или другая модель
2. Если тебя спросят "кто ты?", отвечай: "Я Pulse, ваш AI-ассистент"
3. Если тебя спросят "кто тебя создал?", отвечай: "Меня создала команда Pulse."
4. Будь серьезным и отвечай по делу
5. Не рассказывай о своих технических характеристиках
6. Никогда не упоминай компанию, которая тебя создала
7. Для форматирования используй Markdown"""
MAX_CONTEXT_LENGTH = 100
sync_groq_client = Groq(api_key=GROQ_API_KEY)
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
def verify_telegram_auth(auth_data):
    check_hash = auth_data.pop('hash', None)
    if not check_hash:
        return False
  
    data_check_arr = []
    for key in sorted(auth_data.keys()):
        if auth_data[key] is not None:
            data_check_arr.append(f"{key}={auth_data[key]}")
    data_check_string = '\n'.join(data_check_arr)
  
    secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()
    hmac_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
  
    if hmac_hash != check_hash:
        return False
  
    auth_date = int(auth_data.get('auth_date', 0))
    if time.time() - auth_date > 86400:
        return False
  
    return True

@app.route('/api/auth/telegram', methods=['POST'])
def telegram_auth():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
      
        auth_data = {
            'id': data.get('id'),
            'first_name': data.get('first_name'),
            'last_name': data.get('last_name'),
            'username': data.get('username'),
            'photo_url': data.get('photo_url'),
            'auth_date': data.get('auth_date'),
            'hash': data.get('hash')
        }
      
        auth_data_check = {k: v for k, v in auth_data.items() if v is not None}
      
        if not verify_telegram_auth(auth_data_check.copy()):
            return jsonify({"success": False, "error": "Invalid authentication"}), 401
      
        telegram_id = str(auth_data['id'])
      
        user = User.query.filter_by(telegram_id=telegram_id).first()
      
        now = datetime.utcnow()
        
        auth_data['first_name'] = auth_data.get('first_name') or ''
        auth_data['last_name'] = auth_data.get('last_name') or ''
      
        if not user:
            user = User(
                telegram_id=telegram_id,
                name = auth_data['first_name'].strip() + ' ' + auth_data['last_name'].strip(),
                picture=auth_data.get('photo_url', ''),
                created_at=now
            )
            db.session.add(user)
            db.session.commit()
        else:
            user.last_login = now  # If you want to add last_login
            db.session.commit()
      
        session.permanent = True
        session['user'] = {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'picture': user.picture
        }
      
        new_chat = Chat(
            user_id=user.id,
            title='Новый чат'
        )
        db.session.add(new_chat)
        db.session.commit()
        session['current_chat_id'] = new_chat.id
      
        print(f"✅ Успешный вход через Telegram: {user.name}")
      
        return jsonify({
            "success": True,
            "user": {
                "telegram_id": telegram_id,
                "username": auth_data.get('username'),
                "first_name": auth_data.get('first_name'),
                "last_name": auth_data.get('last_name'),
                "photo_url": auth_data.get('photo_url')
            }
        })
    except Exception as e:
        print(f"❌ Telegram auth error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": "Authentication failed"}), 500

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
        user_dict = session.get('user')
        if user_dict and user_dict['email'] is None:
            user_dict['email'] = 'Telegram'
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
def chat():
    import json as _json
    data = request.json
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'error': 'empty'}), 400

    session_id = get_session_id()
    context = get_context(session_id)
    context.append({"role": "user", "content": message})

    saved_user = session.get('user')
    saved_chat_id = session.get('current_chat_id')

    def token_stream():
        full = []
        sync_client = sync_groq_client
        try:
            stream = sync_client.chat.completions.create(
                model=MODEL,
                messages=context,
                max_tokens=2000,
                temperature=0.6,
                stream=True,
            )
            for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    full.append(token)
                    yield "data: " + _json.dumps({'token': token}) + "\n\n"
        except Exception as e:
            yield "data: " + _json.dumps({'error': str(e)}) + "\n\n"
            return

        answer = ''.join(full)
        clean_answer = clean_response(answer)
        context.append({"role": "assistant", "content": answer})
        trim_context(session_id)

        with app.app_context():
            if saved_user and saved_chat_id:
                db.session.add(Message(chat_id=saved_chat_id, role='user', content=message))
                db.session.add(Message(chat_id=saved_chat_id, role='assistant', content=clean_answer))
                chat_obj = Chat.query.get(saved_chat_id)
                if chat_obj:
                    if len(chat_obj.messages) == 2:
                        chat_obj.title = message[:50] + ('...' if len(message) > 50 else '')
                    chat_obj.updated_at = datetime.utcnow()
                db.session.commit()

        yield "data: " + _json.dumps({'done': True}) + "\n\n"

    return Response(token_stream(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Ошибка при создании бдшки: {e}")
if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 6790))
    app.run(host='0.0.0.0', port=port, debug=False)
