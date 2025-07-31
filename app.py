import os
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify, flash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key')
UPLOAD_FOLDER = os.path.join('images')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Passcodes from .env
USER_PASSCODE = os.environ.get('USER_PASSCODE')
ADMIN_PASSCODE = os.environ.get('ADMIN_PASSCODE')
GUEST_PASSCODE = os.environ.get('GUEST_PASSCODE')

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_images_sorted_by_date(folder):
    images = []
    for fname in os.listdir(folder):
        path = os.path.join(folder, fname)
        if os.path.isfile(path):
            ctime = os.path.getctime(path)
            images.append((fname, ctime))
    images.sort(key=lambda x: x[1], reverse=True)  # Newest first
    return [fname for fname, _ in images]

# Session helpers
def logged_in():
    return 'is_admin' in session or 'is_guest' in session

def is_admin():
    return session.get('is_admin', False)

def is_guest():
    return session.get('is_guest', False)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/passcode', methods=['GET', 'POST'])
def passcode():
    if request.method == 'POST':
        code = request.form.get('code')
        if code == ADMIN_PASSCODE:
            session['is_admin'] = True
            session['is_guest'] = False
            return redirect(url_for('admin'))
        elif code == USER_PASSCODE:
            session['is_admin'] = False
            session['is_guest'] = False
            return redirect(url_for('images'))
        elif code == GUEST_PASSCODE:
            session['is_admin'] = False
            session['is_guest'] = True
            return redirect(url_for('view_gallery'))
        else:
            flash("Incorrect passcode.", "danger")
            return render_template('passcode.html')
    return render_template('passcode.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/images')
def images():
    # User can upload/view, but not admin/guest
    if not logged_in() or is_admin() or is_guest():
        return redirect(url_for('passcode'))
    image_files = get_images_sorted_by_date(app.config['UPLOAD_FOLDER'])
    return render_template('images.html', images=image_files)

@app.route('/admin')
def admin():
    # Only admin can access
    if not logged_in() or not is_admin():
        return redirect(url_for('passcode'))
    image_files = get_images_sorted_by_date(app.config['UPLOAD_FOLDER'])
    return render_template('admin.html', images=image_files)

@app.route('/view')
def view_gallery():
    # Only guest can access
    if not logged_in() or not is_guest():
        return redirect(url_for('passcode'))
    image_files = get_images_sorted_by_date(app.config['UPLOAD_FOLDER'])
    return render_template('view.html', images=image_files)

@app.route('/upload_image', methods=['POST'])
def upload_image():
    # Only allow normal user (not admin or guest) to upload
    if not logged_in() or is_admin() or is_guest():
        return jsonify({'success': False, 'msg': 'Unauthorized'}), 403
    if 'images' not in request.files:
        return jsonify({'success': False, 'msg': 'No file part'}), 400
    files = request.files.getlist('images')
    saved_files = []
    for file in files:
        if file and file.filename:
            filename = secure_filename(file.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            # Prevent overwriting by appending a number if file exists
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
    # Only admin can delete
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

# Optional: error handler for 404
@app.errorhandler(404)
def not_found(e):
    return render_template('index.html'), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
