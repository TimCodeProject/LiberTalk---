from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
import json
import os
import base64
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime
from PIL import Image
import io

app = Flask(__name__)
app.secret_key = 'libertalk-secret-key-2024'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['AVATAR_FOLDER'] = 'static/avatars'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx',
    'mp3', 'wav', 'ogg', 'm4a',  # Аудио
    'mp4', 'webm', 'mov', 'avi'  # Видео
}
# Константы для голосовых сообщений
MAX_VOICE_DURATION = 30
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a', 'webm'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov', 'avi'}

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['AVATAR_FOLDER'], exist_ok=True)

def allowed_file(filename, file_type='all'):
    if file_type == 'image':
        extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    elif file_type == 'audio':
        extensions = {'mp3', 'wav', 'ogg', 'm4a', 'webm'}
    elif file_type == 'video':
        extensions = {'mp4', 'webm', 'mov', 'avi'}
    else:
        extensions = ALLOWED_EXTENSIONS
    
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions

def load_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def process_avatar(image_data, username):
    """Process and save avatar image"""
    try:
        # Remove data URL prefix
        if ',' in image_data:
            image_data = image_data.split(',', 1)[1]
        
        # Decode base64
        image_bytes = base64.b64decode(image_data)
        
        # Open image and resize
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert('RGB')
        img.thumbnail((150, 150), Image.Resampling.LANCZOS)
        
        # Save as JPEG
        filename = f"{username}_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join(app.config['AVATAR_FOLDER'], filename)
        img.save(filepath, 'JPEG', quality=85)
        
        return filename
    except Exception as e:
        print(f"Error processing avatar: {e}")
        return None

def get_user_avatar(username):
    users = load_json('users.json')
    if username in users:
        return users[username].get('avatar', 'default_avatar.jpg')
    return 'default_avatar.jpg'

def is_room_admin(room_name, username):
    rooms = load_json('rooms.json')
    if room_name in rooms:
        room = rooms[room_name]
        return room.get('created_by') == username or username in room.get('moderators', [])
    return False

def is_room_creator(room_name, username):
    rooms = load_json('rooms.json')
    if room_name in rooms:
        return rooms[room_name].get('created_by') == username
    return False

def get_user_role(room_name, username):
    rooms = load_json('rooms.json')
    if room_name in rooms:
        room = rooms[room_name]
        if room.get('created_by') == username:
            return 'admin'
        elif username in room.get('moderators', []):
            return 'moderator'
    return 'user'

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            return render_template('login.html', error='Заполните все поля')
        
        users = load_json('users.json')
        if username in users and users[username]['password'] == password:
            session['username'] = username
            session['avatar'] = users[username].get('avatar', 'default_avatar.jpg')
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Неверный логин или пароль')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        avatar_selected = request.form.get('avatar_selected', '')
        avatar_file = request.files.get('avatar_file_upload')
        
        if not username or not password:
            return render_template('register.html', error='Заполните все поля')
        
        if password != confirm_password:
            return render_template('register.html', error='Пароли не совпадают')
        
        users = load_json('users.json')
        if username in users:
            return render_template('register.html', error='Пользователь уже существует')
        
        # Обработка аватарки
        avatar_filename = 'default_avatar.jpg'
        
        # Если загружена своя аватарка
        if avatar_file and avatar_file.filename:
            try:
                if allowed_file(avatar_file.filename, 'image'):
                    # Генерируем уникальное имя файла
                    filename = f"{username}_{uuid.uuid4().hex[:8]}.jpg"
                    filepath = os.path.join(app.config['AVATAR_FOLDER'], filename)
                    
                    # Обрабатываем и сохраняем изображение
                    img = Image.open(avatar_file)
                    img = img.convert('RGB')
                    img.thumbnail((150, 150), Image.LANCZOS)
                    img.save(filepath, 'JPEG', quality=85)
                    avatar_filename = filename
            except Exception as e:
                print(f"Error processing avatar: {e}")
                return render_template('register.html', error='Ошибка обработки изображения')
        
        # Если выбрана стандартная аватарка
        elif avatar_selected:
            # Проверяем существует ли выбранная аватарка
            avatar_path = os.path.join(app.config['AVATAR_FOLDER'], avatar_selected)
            if os.path.exists(avatar_path):
                # Копируем выбранную аватарку для пользователя
                import shutil
                new_filename = f"{username}_{uuid.uuid4().hex[:8]}.jpg"
                new_filepath = os.path.join(app.config['AVATAR_FOLDER'], new_filename)
                shutil.copy2(avatar_path, new_filepath)
                avatar_filename = new_filename
        
        # Если ничего не выбрано, остается default_avatar.jpg
        
        users[username] = {
            'password': password,
            'avatar': avatar_filename,
            'created_at': datetime.now().isoformat(),
            'banned_rooms': []
        }
        save_json('users.json', users)
        
        session['username'] = username
        session['avatar'] = avatar_filename
        return redirect(url_for('dashboard'))
    
    return render_template('register.html')

@app.route('/update_avatar', methods=['POST'])
def update_avatar():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    avatar_data = request.json.get('avatar_data', '')
    if not avatar_data:
        return jsonify({'error': 'No avatar data'}), 400
    
    avatar_filename = process_avatar(avatar_data, session['username'])
    if not avatar_filename:
        return jsonify({'error': 'Error processing avatar'}), 400
    
    users = load_json('users.json')
    if session['username'] in users:
        users[session['username']]['avatar'] = avatar_filename
        save_json('users.json', users)
        session['avatar'] = avatar_filename
        
        # Update avatar in all rooms
        rooms = load_json('rooms.json')
        for room_name, room in rooms.items():
            if 'messages' in room:
                for message in room['messages']:
                    if message['username'] == session['username']:
                        message['avatar'] = avatar_filename
        save_json('rooms.json', rooms)
        
        return jsonify({'success': True, 'avatar': avatar_filename})
    
    return jsonify({'error': 'User not found'}), 404

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    rooms = load_json('rooms.json')
    open_rooms = {}
    
    for name, room in rooms.items():
        if room.get('type') == 'open' and session['username'] not in room.get('banned_users', []):
            open_rooms[name] = room
    
    return render_template('dashboard.html', 
                         username=session['username'],
                         avatar=session.get('avatar', 'default_avatar.jpg'),
                         rooms=open_rooms)

@app.route('/create_room', methods=['GET', 'POST'])
def create_room():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        room_name = request.form.get('room_name', '').strip()
        room_type = request.form.get('room_type', 'open')
        password = request.form.get('password', '').strip()
        
        if not room_name:
            return render_template('create_room.html', error='Введите название комнаты')
        
        rooms = load_json('rooms.json')
        if room_name in rooms:
            return render_template('create_room.html', error='Комната с таким именем уже существует')
        
        rooms[room_name] = {
            'type': room_type,
            'password': password,
            'created_by': session['username'],
            'created_at': datetime.now().isoformat(),
            'moderators': [],
            'banned_users': [],
            'messages': []
        }
        save_json('rooms.json', rooms)
        
        return redirect(url_for('room', room_name=room_name))
    
    return render_template('create_room.html')

@app.route('/room/<room_name>', methods=['GET', 'POST'])
def room(room_name):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    rooms = load_json('rooms.json')
    if room_name not in rooms:
        return redirect(url_for('dashboard'))
    
    room_data = rooms[room_name]
    
    # Check if user is banned
    if session['username'] in room_data.get('banned_users', []):
        return render_template('banned.html', room_name=room_name)
    
    # Check if room is password protected
    if room_data.get('password') and not session.get(f'access_{room_name}'):
        if request.method == 'POST':
            password = request.form.get('password', '').strip()
            if password == room_data['password']:
                session[f'access_{room_name}'] = True
                return redirect(url_for('room', room_name=room_name))
            else:
                return render_template('room_password.html', room_name=room_name, error='Неверный пароль')
        else:
            return render_template('room_password.html', room_name=room_name)
    
    if request.method == 'POST':
        message_type = request.form.get('message_type', 'text')
        
        # Обработка текстовых сообщений
        if message_type == 'text':
            message = request.form.get('message', '').strip()
            file = request.files.get('file')
            
            file_data = None
            if file and file.filename and allowed_file(file.filename):
                filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                file_data = {
                    'filename': file.filename,
                    'path': filename,
                    'type': file.content_type
                }
            
            new_message = {
                'id': str(uuid.uuid4()),
                'type': 'text',
                'username': session['username'],
                'avatar': session.get('avatar', 'default_avatar.jpg'),
                'message': message,
                'file': file_data,
                'timestamp': datetime.now().isoformat(),
                'role': get_user_role(room_name, session['username'])
            }
        
        # Обработка голосовых сообщений
        elif message_type == 'voice':
            voice_file = request.files.get('voice_message')
            if voice_file and voice_file.filename and allowed_file(voice_file.filename, 'audio'):
                filename = f"voice_{uuid.uuid4().hex}_{secure_filename(voice_file.filename)}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                voice_file.save(file_path)
                
                # Здесь можно добавить проверку длительности аудио
                # (требует дополнительных библиотек типа mutagen)
                
                new_message = {
                    'id': str(uuid.uuid4()),
                    'type': 'voice',
                    'username': session['username'],
                    'avatar': session.get('avatar', 'default_avatar.jpg'),
                    'voice_path': filename,
                    'duration': MAX_VOICE_DURATION,  # Можно определить реальную длительность
                    'timestamp': datetime.now().isoformat(),
                    'role': get_user_role(room_name, session['username'])
                }
            else:
                return redirect(url_for('room', room_name=room_name))
        
        # Обработка опросов
        elif message_type == 'poll':
            poll_question = request.form.get('poll_question', '').strip()
            poll_options = request.form.getlist('poll_options[]')
            poll_options = [opt.strip() for opt in poll_options if opt.strip()]
            
            if not poll_question or len(poll_options) < 2:
                return redirect(url_for('room', room_name=room_name))
            
            new_message = {
                'id': str(uuid.uuid4()),
                'type': 'poll',
                'username': session['username'],
                'avatar': session.get('avatar', 'default_avatar.jpg'),
                'question': poll_question,
                'options': [{'text': opt, 'votes': 0, 'voters': []} for opt in poll_options],
                'total_votes': 0,
                'voters': [],
                'timestamp': datetime.now().isoformat(),
                'role': get_user_role(room_name, session['username'])
            }
        
        else:
            return redirect(url_for('room', room_name=room_name))
        
        if 'messages' not in room_data:
            room_data['messages'] = []
        
        room_data['messages'].append(new_message)
        rooms[room_name] = room_data
        save_json('rooms.json', rooms)
        
        return redirect(url_for('room', room_name=room_name))
    
    return render_template('room.html', 
                         room_name=room_name, 
                         room_data=room_data,
                         username=session['username'],
                         avatar=session.get('avatar', 'default_avatar.jpg'),
                         user_role=get_user_role(room_name, session['username']),
                         is_admin=is_room_admin(room_name, session['username']),
                         is_creator=is_room_creator(room_name, session['username']))

@app.route('/admin/<room_name>')
def room_admin(room_name):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if not is_room_admin(room_name, session['username']):
        return redirect(url_for('room', room_name=room_name))
    
    rooms = load_json('rooms.json')
    if room_name not in rooms:
        return redirect(url_for('dashboard'))
    
    room_data = rooms[room_name]
    users = load_json('users.json')
    
    # Get all users who have sent messages in the room
    room_users = {}
    for message in room_data.get('messages', []):
        username = message['username']
        if username not in room_users:
            room_users[username] = {
                'avatar': users.get(username, {}).get('avatar', 'default_avatar.jpg'),
                'role': get_user_role(room_name, username)
            }
    
    return render_template('admin.html',
                         room_name=room_name,
                         room_data=room_data,
                         users=room_users,
                         is_creator=is_room_creator(room_name, session['username']))

@app.route('/admin_action/<room_name>', methods=['POST'])
def admin_action(room_name):
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    if not is_room_admin(room_name, session['username']):
        return jsonify({'error': 'No permission'}), 403
    
    action = request.json.get('action')
    target_user = request.json.get('target_user')
    
    if not action or not target_user:
        return jsonify({'error': 'Missing parameters'}), 400
    
    rooms = load_json('rooms.json')
    if room_name not in rooms:
        return jsonify({'error': 'Room not found'}), 404
    
    room_data = rooms[room_name]
    is_creator = is_room_creator(room_name, session['username'])
    
    # Check permissions
    target_role = get_user_role(room_name, target_user)
    if target_role == 'admin' and not is_creator:
        return jsonify({'error': 'Cannot modify admin'}), 403
    if target_role == 'moderator' and action in ['ban', 'moderator'] and not is_creator:
        return jsonify({'error': 'Cannot modify moderator'}), 403
    
    if action == 'moderator':
        if target_user in room_data.get('moderators', []):
            room_data['moderators'].remove(target_user)
        else:
            if 'moderators' not in room_data:
                room_data['moderators'] = []
            room_data['moderators'].append(target_user)
    
    elif action == 'ban':
        if 'banned_users' not in room_data:
            room_data['banned_users'] = []
        if target_user not in room_data['banned_users']:
            room_data['banned_users'].append(target_user)
        # Remove from moderators if was moderator
        if target_user in room_data.get('moderators', []):
            room_data['moderators'].remove(target_user)
    
    elif action == 'kick':
        # Just remove from moderators if was moderator
        if target_user in room_data.get('moderators', []):
            room_data['moderators'].remove(target_user)
    
    elif action == 'clear_chat':
        room_data['messages'] = []
    
    rooms[room_name] = room_data
    save_json('rooms.json', rooms)
    
    return jsonify({'success': True})

@app.route('/message_action/<room_name>', methods=['POST'])
def message_action(room_name):
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    if not is_room_admin(room_name, session['username']):
        return jsonify({'error': 'No permission'}), 403
    
    message_id = request.json.get('message_id')
    action = request.json.get('action')
    new_text = request.json.get('new_text', '')
    
    if not message_id or not action:
        return jsonify({'error': 'Missing parameters'}), 400
    
    rooms = load_json('rooms.json')
    if room_name not in rooms:
        return jsonify({'error': 'Room not found'}), 404
    
    room_data = rooms[room_name]
    
    for message in room_data.get('messages', []):
        if message['id'] == message_id:
            if action == 'delete':
                room_data['messages'].remove(message)
            elif action == 'edit' and new_text:
                message['message'] = new_text
                message['edited'] = True
                message['edit_timestamp'] = datetime.now().isoformat()
            break
    
    rooms[room_name] = room_data
    save_json('rooms.json', rooms)
    
    return jsonify({'success': True})

@app.route('/search_room', methods=['POST'])
def search_room():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    search_term = request.json.get('search_term', '')
    rooms = load_json('rooms.json')
    
    found_rooms = {}
    for name, room in rooms.items():
        if (search_term.lower() in name.lower() and 
            room.get('type') == 'closed' and 
            session['username'] not in room.get('banned_users', [])):
            found_rooms[name] = room
    
    return jsonify(found_rooms)

@app.route('/avatars/<filename>')
def avatar_file(filename):
    return send_from_directory(app.config['AVATAR_FOLDER'], filename)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/get_messages/<room_name>')
def get_messages(room_name):
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    rooms = load_json('rooms.json')
    if room_name in rooms and 'messages' in rooms[room_name]:
        return jsonify(rooms[room_name]['messages'])
    
    return jsonify([])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.context_processor
def utility_processor():
    def get_user_role(room_name, username):
        rooms = load_json('rooms.json')
        if room_name in rooms:
            room = rooms[room_name]
            if room.get('created_by') == username:
                return 'admin'
            elif username in room.get('moderators', []):
                return 'moderator'
        return 'user'
    
    def is_room_admin(room_name, username):
        rooms = load_json('rooms.json')
        if room_name in rooms:
            room = rooms[room_name]
            return room.get('created_by') == username or username in room.get('moderators', [])
        return False
    
    def is_room_creator(room_name, username):
        rooms = load_json('rooms.json')
        if room_name in rooms:
            return rooms[room_name].get('created_by') == username
        return False
    
    return dict(
        get_user_role=get_user_role,
        is_room_admin=is_room_admin,
        is_room_creator=is_room_creator
    )

@app.route('/vote/<room_name>/<message_id>', methods=['POST'])
def vote_poll(room_name, message_id):
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    option_index = request.json.get('option_index')
    
    rooms = load_json('rooms.json')
    if room_name not in rooms:
        return jsonify({'error': 'Room not found'}), 404
    
    room_data = rooms[room_name]
    
    # Находим сообщение с опросом
    for message in room_data.get('messages', []):
        if message['id'] == message_id and message['type'] == 'poll':
            # Проверяем, не голосовал ли уже пользователь
            if session['username'] in message['voters']:
                return jsonify({'error': 'Already voted'}), 400
            
            # Проверяем валидность option_index
            if option_index is None or not 0 <= option_index < len(message['options']):
                return jsonify({'error': 'Invalid option'}), 400
            
            # Обновляем голоса
            message['options'][option_index]['votes'] += 1
            message['options'][option_index]['voters'].append(session['username'])
            message['total_votes'] += 1
            message['voters'].append(session['username'])
            
            rooms[room_name] = room_data
            save_json('rooms.json', rooms)
            
            return jsonify({
                'success': True,
                'options': message['options'],
                'total_votes': message['total_votes']
            })
    
    return jsonify({'error': 'Poll not found'}), 404

if __name__ == '__main__':
    # Create necessary JSON files if they don't exist
    if not os.path.exists('users.json'):
        save_json('users.json', {})
    if not os.path.exists('rooms.json'):
        save_json('rooms.json', {})
    
    app.run(debug=True, host='0.0.0.0', port=5000)
