
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, redirect, url_for, session, render_template, request
from authlib.integrations.flask_client import OAuth
from datetime import datetime
import pytz
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))
app.config['SESSION_COOKIE_NAME'] = 'google-login-session'

# OAuth setup
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

def get_indian_time():
    india = pytz.timezone('Asia/Kolkata')
    return datetime.now(india).strftime('%Y-%m-%d %H:%M:%S')

@app.route('/')
def index():
    user = session.get('user')
    indian_time = get_indian_time()
    return render_template('index.html', user=user, indian_time=indian_time)

@app.route('/login')
def login():
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    token = google.authorize_access_token()
    # Use parse_id_token with fixed issuer values for claim validation
    user_info = google.parse_id_token(token,nonce=None,
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
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
