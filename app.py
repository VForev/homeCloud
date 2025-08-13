import os
import json
import time
import uuid
import threading
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
MESSAGE_MOD_PASSCODE = os.environ.get('MESSAGE_MOD_PASSCODE')      # delete messages

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
    for m in messages:
        if 'id' not in m:
            m['id'] = uuid.uuid4().hex
            changed = True
    if changed:
        save_messages(messages)
    return messages

def get_images_sorted_by_date(folder):
    images = []
    for fname in os.listdir(folder):
        path = os.path.join(folder, fname)
        if os.path.isfile(path):
            ctime = os.path.getctime(path)
            images.append((fname, ctime))
    images.sort(key=lambda x: x[1], reverse=True)  # Newest first
    return [fname for fname, _ in images]

# --- Session helpers ---
def set_all_false():
    session['is_user'] = False
    session['is_admin'] = False
    session['is_guest'] = False
    session['is_chat'] = False
    session['is_msgmod'] = False

def logged_in():
    return any([
        session.get('is_user', False),
        session.get('is_admin', False),
        session.get('is_guest', False),
        session.get('is_chat', False),
        session.get('is_msgmod', False),
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

        else:
            flash("Incorrect passcode.", "danger")
            return render_template('passcode.html')
    return render_template('passcode.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# --- Images area ---

@app.route('/images')
def images():
    # Only normal "user" can upload/view here (not admin/guest/chat/mod)
    if not logged_in() or not is_user():
        return redirect(url_for('passcode'))
    image_files = get_images_sorted_by_date(app.config['UPLOAD_FOLDER'])
    return render_template('images.html', images=image_files)

@app.route('/admin')
def admin():
    if not logged_in() or not is_admin():
        return redirect(url_for('passcode'))
    image_files = get_images_sorted_by_date(app.config['UPLOAD_FOLDER'])
    return render_template('admin.html', images=image_files)

@app.route('/view')
def view_gallery():
    if not logged_in() or not is_guest():
        return redirect(url_for('passcode'))
    image_files = get_images_sorted_by_date(app.config['UPLOAD_FOLDER'])
    return render_template('view.html', images=image_files)

@app.route('/upload_image', methods=['POST'])
def upload_image():
    # Only allow normal user (not admin/guest/chat/mod) to upload
    if not logged_in() or not is_user():
        return jsonify({'success': False, 'msg': 'Unauthorized'}), 403
    if 'images' not in request.files:
        return jsonify({'success': False, 'msg': 'No file part'}), 400
    files = request.files.getlist('images')
    saved_files = []
    for file in files:
        if file and file.filename:
            filename = secure_filename(file.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            name, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(path):
                filename = f"{name}_{counter}{ext}"
                path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                counter += 1
            file.save(path)
            saved_files.append(filename)
    if saved_files:
        return jsonify({'success': True, 'files': saved_files})
    return jsonify({'success': False, 'msg': 'No images saved'}), 400

@app.route('/delete_image', methods=['POST'])
def delete_image():
    # Only admin can delete images
    if not logged_in() or not is_admin():
        return jsonify({'success': False, 'msg': 'Not authorized'}), 403
    filename = request.form.get('filename')
    if not filename:
        return jsonify({'success': False, 'msg': 'No filename'}), 400
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'msg': 'File not found'}), 404

@app.route('/images/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

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
        msgs.sort(key=lambda m: m.get('ts', 0), reverse=True)
        return jsonify(msgs)

    # POST a message
    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception:
        data = {}
    author = (data.get('author') or '').strip()
    text = (data.get('text') or '').strip()

    if not text:
        return jsonify({'success': False, 'msg': 'Empty message'}), 400
    if len(author) > 50:
        author = author[:50]
    if len(text) > 2000:
        text = text[:2000]

    msg = {
        'id': uuid.uuid4().hex,
        'author': author,
        'text': text,
        'ts': int(time.time())
    }
    msgs = load_messages()
    msgs.append(msg)
    save_messages(msgs)
    return jsonify({'success': True})

@app.route('/api/messages/delete', methods=['POST'])
def api_messages_delete():
    # Allow admins and message moderators to delete individual messages
    if not logged_in() or (not is_admin() and not is_msgmod()):
        return jsonify({'success': False, 'msg': 'Not authorized'}), 403

    payload = request.get_json(silent=True) or {}
    msg_id = payload.get('id')
    if not msg_id:
        return jsonify({'success': False, 'msg': 'Missing id'}), 400

    msgs = load_messages()
    before = len(msgs)
    msgs = [m for m in msgs if m.get('id') != msg_id]
    if len(msgs) == before:
        return jsonify({'success': False, 'msg': 'Message not found'}), 404

    save_messages(msgs)
    return jsonify({'success': True})

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
