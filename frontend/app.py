from flask import Flask, render_template, request, jsonify, session, url_for, redirect
import requests
import re
import os
from dotenv import load_dotenv
from pathlib import Path
from functools import wraps

# Load environment variables from .env file at project root
# Go up one level from frontend/ to project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-123-abc!@#')
BACKEND_API_URL = os.environ.get('BACKEND_URL', 'http://backend:5000')

def validate_email_format(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get('user')
        if not user:
            return redirect(url_for('signin'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    user = session.get('user')
    return render_template('index.html', user=user)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        response = requests.post(f"{BACKEND_API_URL}/signup", json=data)
        return jsonify(response.json()), response.status_code
    return render_template('signup.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        response = requests.post(f"{BACKEND_API_URL}/signin", json=data)
        if response.status_code == 200:
            result = response.json()
            session['user'] = {
                'user_id': result.get('user_id'),
                'email': result.get('email'),
                'full_name': result.get('full_name')
            }
        return jsonify(response.json()), response.status_code
    return render_template('signin.html')

@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    user = session.get('user')
    if not user:
        return jsonify({"success": False, "redirect": url_for('signin')}), 401

    user_id = user.get('user_id')

    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        response = requests.post(f"{BACKEND_API_URL}/account", json={**data, "user_id": user_id})
        return jsonify(response.json()), response.status_code

    response = requests.get(f"{BACKEND_API_URL}/account", json={"user_id": user_id})
    if response.status_code == 200:
        profile = response.json().get('user')
        return render_template('account.html', user=profile)
    return jsonify({"success": False, "message": "Could not load profile."}), 400

@app.route('/signout')
def signout():
    session.clear()
    return redirect(url_for('signin'))

@app.route('/home')
@login_required
def home():
    try:
        user = session.get('user')
        user_id = user.get('user_id') if user else None
        if not user_id:
            return redirect(url_for('signin'))
        
        # Get user data from backend
        response = requests.get(f'{BACKEND_API_URL}/account', json={'user_id': user_id})
        
        if response.status_code == 200:
            user_data = response.json().get('user')
            return render_template('home.html', user=user_data)
        else:
            return redirect(url_for('signin'))
    except Exception as e:
        print(f"Error fetching user data: {e}")
        return redirect(url_for('signin'))

# LinkedIn Agent page
@app.route('/linkedin-agent')
@login_required
def linkedin_agent():
    """LinkedIn Content Agent page"""
    try:
        # Get user's LinkedIn URL from database
        user = session.get('user')
        user_id = user.get('user_id') if user else None
        
        user_data = None
        user_linkedin_url = ''
        
        if user_id:
            response = requests.get(f'{BACKEND_API_URL}/account', json={'user_id': user_id})
            if response.status_code == 200:
                user_data = response.json().get('user', {})
                user_linkedin_url = user_data.get('linkedin', '')
    except Exception as e:
        print(f"Error fetching user LinkedIn URL: {e}")
        user_data = None
        user_linkedin_url = ''
    
    # Read API keys from environment variables (if set)
    # Default Google Sheet URL
    default_sheet_url = 'https://docs.google.com/spreadsheets/d/10OsJwVQAboMx3LKfoZhQLRQ9w9UuekvNG1_oaZNgOMM/edit?usp=sharing'
    
    env_config = {
        'openai_api_key': os.environ.get('OPENAI_API_KEY', ''),
        'phantombuster_api_key': os.environ.get('PHANTOMBUSTER_API_KEY', ''),
        'firecrawl_api_key': os.environ.get('FIRECRAWL_API_KEY', ''),
        'user_agent': os.environ.get('USER_AGENT', ''),
        'google_sheet_url': os.environ.get('GOOGLE_SHEET_URL', default_sheet_url),
        'linkedin_session_cookie': os.environ.get('LINKEDIN_SESSION_COOKIE', ''),
        'user_linkedin_url': user_linkedin_url,  # From database
    }
    return render_template('linkedin_agent.html', user=user_data, env_config=env_config)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)
