import os
import json
import time
import uuid
import threading
import mimetypes
from flask import (
    Flask, render_template, render_template_string, request,
    redirect, url_for, session, send_from_directory, jsonify, flash
)
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key')

# Folders
UPLOAD_FOLDER = os.path.join('images')
DATA_FOLDER = os.path.join('data')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Passcodes
USER_PASSCODE = os.environ.get('USER_PASSCODE')
ADMIN_PASSCODE = os.environ.get('ADMIN_PASSCODE')
GUEST_PASSCODE = os.environ.get('GUEST_PASSCODE')
MESSAGE_PASSCODE = os.environ.get('MESSAGE_PASSCODE')              # view/post messages
MESSAGE_MOD_PASSCODE = os.environ.get('MESSAGE_MOD_PASSCODE')  # delete messages
AI_CODE = os.environ.get('AI_CODE')

# Messages storage
MESSAGES_FILE = os.path.join(DATA_FOLDER, 'messages.json')
_messages_lock = threading.Lock()
if not os.path.exists(MESSAGES_FILE):
    with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)

def load_messages():
    with _messages_lock:
        try:
            with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

def save_messages(messages):
    with _messages_lock:
        with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)

def ensure_ids(messages):
    changed = False
    seen_ids = set()
    for m in messages:
        msg_id = m.get('id')
        if not isinstance(msg_id, str) or not msg_id.strip() or msg_id in seen_ids:
            m['id'] = uuid.uuid4().hex
            changed = True
        seen_ids.add(m['id'])

        if 'parent_id' not in m:
            m['parent_id'] = None
            changed = True
        elif not m.get('parent_id'):
            if m.get('parent_id') is not None:
                m['parent_id'] = None
                changed = True
        elif not isinstance(m.get('parent_id'), str):
            m['parent_id'] = None
            changed = True

        if 'ts' not in m:
            m['ts'] = int(time.time())
            changed = True
        else:
            try:
                ts = int(m.get('ts', 0))
                if ts != m.get('ts'):
                    m['ts'] = ts
                    changed = True
            except Exception:
                m['ts'] = int(time.time())
                changed = True

    valid_ids = {m.get('id') for m in messages if m.get('id')}
    for m in messages:
        parent_id = m.get('parent_id')
        if parent_id and parent_id not in valid_ids:
            m['parent_id'] = None
            changed = True

    if changed:
        save_messages(messages)
    return messages

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.avif', '.heic', '.heif'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.m4v', '.webm', '.ogv', '.ogg', '.mkv', '.avi', '.wmv'}


def detect_file_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext in IMAGE_EXTENSIONS:
        return 'image'
    if ext in VIDEO_EXTENSIONS:
        return 'video'
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type:
        if mime_type.startswith('image/'):
            return 'image'
        if mime_type.startswith('video/'):
            return 'video'
    return 'file'


def format_file_size(size_bytes):
    value = float(size_bytes)
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == 'B':
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{int(size_bytes)} B"


def clean_filename(raw_filename):
    filename = secure_filename((raw_filename or '').strip())
    return filename or None


def build_unique_storage_path(filename):
    candidate = filename
    name, ext = os.path.splitext(filename)
    counter = 1
    while True:
        path = os.path.join(app.config['UPLOAD_FOLDER'], candidate)
        if not os.path.exists(path):
            return path, candidate
        candidate = f"{name}_{counter}{ext}"
        counter += 1


def get_storage_items_sorted_by_date(folder):
    items = []
    for fname in os.listdir(folder):
        path = os.path.join(folder, fname)
        if os.path.isfile(path):
            ctime = os.path.getctime(path)
            size_bytes = os.path.getsize(path)
            items.append({
                'name': fname,
                'type': detect_file_type(fname),
                'created_at': ctime,
                'size_bytes': size_bytes,
                'size_label': format_file_size(size_bytes),
            })
    items.sort(key=lambda item: item['created_at'], reverse=True)
    return items


def get_upload_list_from_request():
    uploads = []
    for field_name in ('files', 'images'):
        if field_name in request.files:
            uploads.extend(request.files.getlist(field_name))
    # Fallback for any other form field names.
    if not uploads:
        for key in request.files:
            uploads.extend(request.files.getlist(key))
    return uploads


def save_uploaded_files(files):
    saved_files = []
    for file in files:
        if not file or not file.filename:
            continue
        filename = clean_filename(file.filename)
        if not filename:
            continue
        path, final_name = build_unique_storage_path(filename)
        file.save(path)
        saved_files.append(final_name)
    return saved_files

# --- Session helpers ---
def set_all_false():
    session['is_user'] = False
    session['is_admin'] = False
    session['is_guest'] = False
    session['is_chat'] = False
    session['is_msgmod'] = False
    session['is_ollama'] = False

def logged_in():
    return any([
        session.get('is_user', False),
        session.get('is_admin', False),
        session.get('is_guest', False),
        session.get('is_chat', False),
        session.get('is_msgmod', False),
        session.get('is_ollama', False),
    ])

def is_user():
    return session.get('is_user', False)

def is_admin():
    return session.get('is_admin', False)

def is_guest():
    return session.get('is_guest', False)

def is_chat():
    return session.get('is_chat', False)

def is_msgmod():
    return session.get('is_msgmod', False)

def is_ollama():
    return session.get('is_ollama', False)

# --- Routes ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/passcode', methods=['GET', 'POST'])
def passcode():
    if request.method == 'POST':
        code = (request.form.get('code') or '').strip()

        if code == ADMIN_PASSCODE:
            session.clear()
            set_all_false()
            session['is_admin'] = True
            return redirect(url_for('admin'))

        elif code == USER_PASSCODE:
            session.clear()
            set_all_false()
            session['is_user'] = True
            return redirect(url_for('images'))

        elif code == GUEST_PASSCODE:
            session.clear()
            set_all_false()
            session['is_guest'] = True
            return redirect(url_for('view_gallery'))

        elif code == MESSAGE_PASSCODE:
            session.clear()
            set_all_false()
            session['is_chat'] = True
            return redirect(url_for('messages_page'))

        elif code == MESSAGE_MOD_PASSCODE:
            session.clear()
            set_all_false()
            session['is_chat'] = True     # can view/post messages
            session['is_msgmod'] = True   # can delete individual messages
            return redirect(url_for('messages_page'))

        elif code == AI_CODE:
            session.clear()
            set_all_false()
            session['is_ollama'] = True
            return redirect(url_for('ollama_ui'))

        else:
            flash("Incorrect passcode.", "danger")
            return render_template('passcode.html')
    return render_template('passcode.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('passcode'))

@app.route('/logout_passcode')
def logout_passcode():
    session.clear()
    return redirect(url_for('passcode'))

@app.route('/ollama')
def ollama_ui():
    if not logged_in() or not is_ollama():
        return redirect(url_for('passcode'))
    return render_template('local_ollama_ui_index.html')

# --- Images area ---

@app.route('/images')
def images():
    # Only normal "user" can upload/view here (not admin/guest/chat/mod)
    if not logged_in() or not is_user():
        return redirect(url_for('passcode'))
    items = get_storage_items_sorted_by_date(app.config['UPLOAD_FOLDER'])
    media_items = [item for item in items if item['type'] in ('image', 'video')]
    file_items = [item for item in items if item['type'] == 'file']
    return render_template('images.html', media_items=media_items, file_items=file_items)

@app.route('/admin')
def admin():
    if not logged_in() or not is_admin():
        return redirect(url_for('passcode'))
    items = get_storage_items_sorted_by_date(app.config['UPLOAD_FOLDER'])
    media_items = [item for item in items if item['type'] in ('image', 'video')]
    file_items = [item for item in items if item['type'] == 'file']
    return render_template('admin.html', media_items=media_items, file_items=file_items)

@app.route('/view')
def view_gallery():
    if not logged_in() or not is_guest():
        return redirect(url_for('passcode'))
    items = get_storage_items_sorted_by_date(app.config['UPLOAD_FOLDER'])
    media_items = [item for item in items if item['type'] in ('image', 'video')]
    file_items = [item for item in items if item['type'] == 'file']
    return render_template('view.html', media_items=media_items, file_items=file_items)


def _handle_upload_files():
    # Only allow normal user (not admin/guest/chat/mod) to upload
    if not logged_in() or not is_user():
        return jsonify({'success': False, 'msg': 'Unauthorized'}), 403
    files = get_upload_list_from_request()
    if not files:
        return jsonify({'success': False, 'msg': 'No file part'}), 400
    saved_files = save_uploaded_files(files)
    if saved_files:
        return jsonify({'success': True, 'files': saved_files})
    return jsonify({'success': False, 'msg': 'No files saved'}), 400


@app.route('/upload_files', methods=['POST'])
def upload_files():
    return _handle_upload_files()


@app.route('/upload_image', methods=['POST'])
def upload_image():
    # Backward-compatible alias.
    return _handle_upload_files()


def _handle_delete_file():
    # Only admin can delete storage files.
    if not logged_in() or not is_admin():
        return jsonify({'success': False, 'msg': 'Not authorized'}), 403
    filename = (request.form.get('filename') or '').strip()
    if not filename:
        payload = request.get_json(silent=True) or {}
        filename = (payload.get('filename') or '').strip()
    safe_filename = clean_filename(filename)
    if not safe_filename:
        return jsonify({'success': False, 'msg': 'Invalid filename'}), 400
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
    if not os.path.isfile(file_path):
        return jsonify({'success': False, 'msg': 'File not found'}), 404
    try:
        os.remove(file_path)
        return jsonify({'success': True})
    except OSError:
        return jsonify({'success': False, 'msg': 'Delete failed'}), 500

@app.route('/delete_file', methods=['POST'])
def delete_file():
    return _handle_delete_file()


@app.route('/delete_image', methods=['POST'])
def delete_image():
    # Backward-compatible alias.
    return _handle_delete_file()

@app.route('/images/<path:filename>')
def uploaded_file(filename):
    safe_filename = clean_filename(filename)
    if not safe_filename:
        return jsonify({'success': False, 'msg': 'Invalid filename'}), 400
    return send_from_directory(app.config['UPLOAD_FOLDER'], safe_filename)


@app.route('/download/<path:filename>')
def download_file(filename):
    # Storage downloads are available to storage-capable roles.
    if not logged_in() or (not is_user() and not is_admin() and not is_guest()):
        return redirect(url_for('passcode'))
    safe_filename = clean_filename(filename)
    if not safe_filename:
        return jsonify({'success': False, 'msg': 'Invalid filename'}), 400
    path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
    if not os.path.isfile(path):
        return jsonify({'success': False, 'msg': 'File not found'}), 404
    return send_from_directory(app.config['UPLOAD_FOLDER'], safe_filename, as_attachment=True)

# --- Messages area ---

@app.route('/messages')
def messages_page():
    # Allow admins, chat users, and message moderators
    if not logged_in() or (not is_admin() and not is_chat() and not is_msgmod()):
        return redirect(url_for('passcode'))
    # Pass deletion capability to template
    return render_template('messages.html', can_delete=(is_admin() or is_msgmod()))

@app.route('/api/messages', methods=['GET', 'POST'])
def api_messages():
    # Allow admins, chat users, and message moderators
    if not logged_in() or (not is_admin() and not is_chat() and not is_msgmod()):
        return jsonify({'success': False, 'msg': 'Unauthorized'}), 403

    if request.method == 'GET':
        msgs = load_messages()
        msgs = ensure_ids(msgs)
        msgs.sort(key=lambda m: m.get('ts', 0))
        return jsonify(msgs)

    # POST a message
    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception:
        data = {}
    author = (data.get('author') or '').strip()
    text = (data.get('text') or '').strip()
    parent_id = (data.get('parent_id') or '').strip()

    if not text:
        return jsonify({'success': False, 'msg': 'Empty message'}), 400
    if len(author) > 50:
        author = author[:50]
    if len(text) > 2000:
        text = text[:2000]

    msgs = ensure_ids(load_messages())
    if parent_id and not any(m.get('id') == parent_id for m in msgs):
        return jsonify({'success': False, 'msg': 'Parent message not found'}), 400

    msg = {
        'id': uuid.uuid4().hex,
        'author': author,
        'text': text,
        'ts': int(time.time()),
        'parent_id': parent_id or None,
    }
    msgs.append(msg)
    save_messages(msgs)
    return jsonify({'success': True})

@app.route('/api/messages/delete', methods=['POST'])
def api_messages_delete():
    # Allow admins and message moderators to delete individual messages
    if not logged_in() or (not is_admin() and not is_msgmod()):
        return jsonify({'success': False, 'msg': 'Not authorized'}), 403

    payload = request.get_json(silent=True) or {}
    msg_id = (payload.get('id') or '').strip()
    if not msg_id:
        return jsonify({'success': False, 'msg': 'Missing id'}), 400

    msgs = ensure_ids(load_messages())
    if not any(m.get('id') == msg_id for m in msgs):
        return jsonify({'success': False, 'msg': 'Message not found'}), 404

    children = {}
    for message in msgs:
        parent = message.get('parent_id')
        if parent:
            children.setdefault(parent, []).append(message.get('id'))

    to_delete = set()
    stack = [msg_id]
    while stack:
        current = stack.pop()
        if current in to_delete:
            continue
        to_delete.add(current)
        stack.extend(children.get(current, []))

    remaining = [m for m in msgs if m.get('id') not in to_delete]
    save_messages(remaining)
    return jsonify({'success': True, 'deleted': len(to_delete)})

@app.route('/api/messages/clear', methods=['POST'])
def api_messages_clear():
    # Only admin can clear all
    if not logged_in() or not is_admin():
        return jsonify({'success': False, 'msg': 'Not authorized'}), 403
    save_messages([])
    return jsonify({'success': True})

# Optional: error handler for 404
@app.errorhandler(404)
def not_found(e):
    return render_template('index.html'), 404

if __name__ == '__main__':
    # Port 8080 to match your previous setup
    app.run(host='0.0.0.0', port=8080, debug=True)
