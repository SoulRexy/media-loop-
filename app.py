from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
import os
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Change this!

# Configuration
ADMIN_PASSWORD = 'admin123'  # Change this password!
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'mov'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ==================== PUBLIC ROUTES ====================

@app.route('/')
def index():
    """Public view - just shows the media loop"""
    return render_template('public.html')

@app.route('/get_media')
def get_media():
    """Returns current media info"""
    files = os.listdir(UPLOAD_FOLDER)
    media_files = [f for f in files if allowed_file(f)]

    if not media_files:
        return {'status': 'no_media'}

    # Get the current media (you can change logic to rotate through multiple)
    current = media_files[0] if media_files else None

    if current:
        ext = current.rsplit('.', 1)[1].lower()
        media_type = 'video' if ext in {'mp4', 'webm', 'mov'} else 'image'
        return {
            'status': 'ok',
            'filename': current,
            'type': media_type
        }
    return {'status': 'no_media'}

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ==================== ADMIN ROUTES ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['password'] == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin'))
        else:
            error = 'Wrong password!'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    """Admin panel to upload and manage media"""
    files = os.listdir(UPLOAD_FOLDER)
    media_files = [f for f in files if allowed_file(f)]
    return render_template('admin.html', files=media_files)

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('admin'))

    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('admin'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    return redirect(url_for('admin'))

@app.route('/delete/<filename>')
@login_required
def delete_file(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
