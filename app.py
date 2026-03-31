from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
import os
import uuid
import json
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Change this!

# Configuration
ADMIN_PASSWORD = 'admin123'  # Change this password!
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
PENDING_FOLDER = os.path.join(BASE_DIR, 'pending')
LINKS_FILE = os.path.join(BASE_DIR, 'share_links.json')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'mov'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PENDING_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_links():
    if os.path.exists(LINKS_FILE):
        with open(LINKS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_links(links):
    with open(LINKS_FILE, 'w') as f:
        json.dump(links, f)

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
    try:
        files = os.listdir(UPLOAD_FOLDER)
        media_files = [f for f in files if allowed_file(f)]
    except Exception as e:
        print(f"Error listing files: {e}")
        return {'status': 'error', 'message': str(e)}

    if not media_files:
        return {'status': 'no_media'}

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
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/pending/<filename>')
def pending_file(filename):
    return send_from_directory(PENDING_FOLDER, filename)

# ==================== SHARE LINK ROUTES ====================

@app.route('/share/<link_id>')
def share_upload(link_id):
    """Public upload page via share link"""
    links = load_links()
    if link_id not in links:
        return "Invalid or expired link", 404

    return render_template('share_upload.html', link_id=link_id)

@app.route('/share/<link_id>/upload', methods=['POST'])
def share_upload_file(link_id):
    """Handle upload from share link"""
    links = load_links()
    if link_id not in links:
        return {'status': 'error', 'message': 'Invalid link'}, 400

    if 'file' not in request.files:
        return redirect(url_for('share_upload', link_id=link_id))

    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('share_upload', link_id=link_id))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Save to pending folder
        file.save(os.path.join(PENDING_FOLDER, filename))
        # Mark link as used
        del links[link_id]
        save_links(links)
        return render_template('share_success.html')

    return redirect(url_for('share_upload', link_id=link_id))

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
    # Get main media files
    files = os.listdir(UPLOAD_FOLDER)
    media_files = [f for f in files if allowed_file(f)]

    # Get pending files
    try:
        pending_files = [f for f in os.listdir(PENDING_FOLDER) if allowed_file(f)]
    except:
        pending_files = []

    return render_template('admin.html', files=media_files, pending=pending_files)

@app.route('/create_link')
@login_required
def create_share_link():
    """Create a one-time share link"""
    link_id = str(uuid.uuid4())[:8]
    links = load_links()
    links[link_id] = {'used': False}
    save_links(links)
    share_url = request.host_url + url_for('share_upload', link_id=link_id)
    return render_template('admin.html', files=os.listdir(UPLOAD_FOLDER),
                           pending=os.listdir(PENDING_FOLDER) if os.path.exists(PENDING_FOLDER) else [],
                           share_url=share_url)

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
        file.save(os.path.join(UPLOAD_FOLDER, filename))

    return redirect(url_for('admin'))

@app.route('/delete/<filename>')
@login_required
def delete_file(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    return redirect(url_for('admin'))

@app.route('/delete_pending/<filename>')
@login_required
def delete_pending_file(filename):
    filepath = os.path.join(PENDING_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    return redirect(url_for('admin'))

@app.route('/approve/<filename>')
@login_required
def approve_file(filename):
    """Move file from pending to main uploads"""
    src = os.path.join(PENDING_FOLDER, filename)
    dst = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(src):
        # Remove existing file with same name in main folder
        if os.path.exists(dst):
            os.remove(dst)
        os.rename(src, dst)
    return redirect(url_for('admin'))

@app.route('/switch/<filename>')
@login_required
def switch_media(filename):
    """Switch to play a specific media file"""
    src = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(src):
        # Rename to make it first alphabetically (hack to make it play first)
        # Better: prepend with underscore or number
        new_name = f"_current_{filename}"
        # Remove old _current_ files
        for f in os.listdir(UPLOAD_FOLDER):
            if f.startswith('_current_'):
                os.remove(os.path.join(UPLOAD_FOLDER, f))
        # Rename current file
        os.rename(src, os.path.join(UPLOAD_FOLDER, new_name))
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
