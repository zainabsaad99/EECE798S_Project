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
    """LinkedIn Content Agent page - requires LinkedIn URL and extracted data"""
    try:
        # Get user's LinkedIn URL from database
        user = session.get('user')
        user_id = user.get('user_id') if user else None
        
        if not user_id:
            return render_template('linkedin_agent.html', 
                                 user=None, 
                                 env_config={},
                                 user_linkedin_data=None,
                                 error_message="Please sign in to access the LinkedIn Agent.")
        
        user_data = None
        user_linkedin_url = ''
        
        response = requests.get(f'{BACKEND_API_URL}/account', json={'user_id': user_id})
        if response.status_code == 200:
            user_data = response.json().get('user', {})
            user_linkedin_url = user_data.get('linkedin', '')
        
        # Check if LinkedIn URL is set
        if not user_linkedin_url:
            # Show error message
            return render_template('linkedin_agent.html', 
                                 user=user_data, 
                                 env_config={},
                                 user_linkedin_data=None,
                                 error_message="Please add your LinkedIn Profile URL in your account settings first.")
        
        # Get user's saved LinkedIn data (keywords and tone)
        user_linkedin_data = None
        try:
            response = requests.get(f'{BACKEND_API_URL}/api/linkedin/user-data', params={'user_id': user_id})
            if response.status_code == 200:
                user_linkedin_data = response.json()
        except Exception as e:
            print(f"Error fetching user LinkedIn data: {e}")
        
        # Check if keywords and tone are extracted
        has_data = (user_linkedin_data and 
                   user_linkedin_data.get('success') and 
                   user_linkedin_data.get('keywords') and 
                   len(user_linkedin_data.get('keywords', [])) > 0 and
                   user_linkedin_data.get('tone_of_writing'))
        
        if not has_data:
            # Show message that data is being processed
            return render_template('linkedin_agent.html', 
                                 user=user_data, 
                                 env_config={},
                                 user_linkedin_data=None,
                                 error_message="Your LinkedIn profile is being analyzed. Please wait a few minutes and refresh the page. If this message persists, try saving your LinkedIn URL again in account settings.")
        
    except Exception as e:
        print(f"Error in linkedin_agent route: {e}")
        return render_template('linkedin_agent.html', 
                             user=None, 
                             env_config={},
                             user_linkedin_data=None,
                             error_message="An error occurred. Please try again.")
    
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
        'user_id': user_id,  # Pass user_id to template
    }
    return render_template('linkedin_agent.html', user=user_data, env_config=env_config, user_linkedin_data=user_linkedin_data)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)
