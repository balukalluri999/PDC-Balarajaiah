from dotenv import load_dotenv
load_dotenv()
from flask import Flask, redirect, url_for, session, render_template, request, flash
from authlib.integrations.flask_client import OAuth
from datetime import datetime
import pytz
import os
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))
app.config['SESSION_COOKIE_NAME'] = 'google-login-session'

UPLOAD_FOLDER = 'static/uploads'
THUMBNAIL_FOLDER = 'static/uploads/thumbnails'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['THUMBNAIL_FOLDER'] = THUMBNAIL_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(THUMBNAIL_FOLDER):
    os.makedirs(THUMBNAIL_FOLDER)

# OAuth setup
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

# AI API configuration
AI_API_ENDPOINT = os.environ.get('https://api.sambanova.ai/v1')  # Put your AI API endpoint here
AI_API_KEY = os.environ.get('5a0172c2-94ea-4042-8abe-1f4f20f7a347')  

def get_indian_time():
    india = pytz.timezone('Asia/Kolkata')
    return datetime.now(india).strftime('%Y-%m-%d %H:%M:%S')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_thumbnail(input_path, output_path, size=(128, 128)):
    with Image.open(input_path) as img:
        img.thumbnail(size)
        img.save(output_path)

def ai_generate_prompt_from_images(image_urls):
    if not AI_API_KEY or not AI_API_ENDPOINT:
        return "Composite news thumbnail inspired by uploaded images."

    headers = {
        'Authorization': f'Bearer {AI_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'images': image_urls  # This depends on your API’s expected payload format
    }
    try:
        response = requests.post(AI_API_ENDPOINT, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        # Expected field 'caption' with description text (adjust per your API)
        return data.get('caption', "Composite news thumbnail inspired by uploaded images.")
    except Exception as e:
        print(f"AI API call failed: {e}")
        return "Composite news thumbnail inspired by uploaded images."

@app.route('/')
def index():
    user = session.get('user')
    indian_time = get_indian_time()
    uploaded_images = session.get('uploaded_images', [])
    generated_thumbnail = session.get('generated_thumbnail', None)
    return render_template('index.html', user=user, indian_time=indian_time, thumbnails=uploaded_images, generated_thumbnail=generated_thumbnail)

@app.route('/login')
def login():
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    token = google.authorize_access_token()
    user_info = google.parse_id_token(token, nonce=None,
                                      claims_options={
                                          'iss': {
                                              'values': ['https://accounts.google.com', 'accounts.google.com']
                                          }
                                      })
    session['user'] = user_info
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('uploaded_images', None)
    session.pop('generated_thumbnail', None)
    return redirect('/')

@app.route('/upload', methods=['POST'])
def upload():
    if 'user' not in session:
        flash("Please sign in first!")
        return redirect(url_for('index'))

    if 'images' not in request.files:
        flash("No files selected")
        return redirect(url_for('index'))

    files = request.files.getlist('images')
    if len(files) > 5:
        flash("You can upload up to 5 images only.")
        return redirect(url_for('index'))

    saved_thumbnails = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(upload_path)

            thumb_filename = f"thumb_{filename}"
            thumb_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumb_filename)
            create_thumbnail(upload_path, thumb_path)

            saved_thumbnails.append(url_for('static', filename=f'uploads/thumbnails/{thumb_filename}'))

    session['uploaded_images'] = saved_thumbnails
    session.pop('generated_thumbnail', None)
    flash(f"Uploaded and processed {len(saved_thumbnails)} images")
    return redirect(url_for('index'))

@app.route('/generate_thumbnail', methods=['POST'])
def generate_thumbnail():
    if 'user' not in session:
        flash("Please sign in first!")
        return redirect(url_for('index'))

    thumbnails = session.get('uploaded_images')
    if not thumbnails:
        flash("Please upload images first")
        return redirect(url_for('index'))

    # Generate AI prompt from uploaded images
    prompt = ai_generate_prompt_from_images(thumbnails)

    # Load images for thumbnail composition
    imgs = [Image.open(os.path.join(app.root_path, thumb.replace('/static/', 'static/'))) for thumb in thumbnails]

    widths, heights = zip(*(i.size for i in imgs))
    total_width = sum(widths)
    max_height = max(heights)

    combined_img = Image.new('RGB', (total_width, max_height + 80), color=(40, 40, 40))

    x_offset = 0
    for im in imgs:
        combined_img.paste(im, (x_offset, 60))
        x_offset += im.width

    draw = ImageDraw.Draw(combined_img)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    try:
        font = ImageFont.truetype(font_path, 40)
    except:
        font = ImageFont.load_default()

    draw.text((20, 10), prompt[:50] + "...", font=font, fill=(255, 120, 0))

    output_path = os.path.join(app.static_folder, 'generated_thumbnail.jpg')
    combined_img.save(output_path)

    session['generated_thumbnail'] = url_for('static', filename='generated_thumbnail.jpg')

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
