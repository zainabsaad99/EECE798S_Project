from flask import Flask, render_template, request, jsonify, session, url_for, redirect
import requests
import re

app = Flask(__name__)
app.secret_key = 'dev-key-123-abc!@#'
BACKEND_API_URL = "http://backend:5000"  # adjust if not using Docker

def validate_email_format(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

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
            session['user'] = response.json()
        return jsonify(response.json()), response.status_code
    return render_template('signin.html')

@app.route('/account', methods=['GET', 'POST'])
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
    return jsonify({"success": True, "redirect": url_for('signin')})

@app.route('/home')
def home():
    try:
        # Get user data from backend
        response = requests.get(f'{BACKEND_API_URL}/user/{session["user_id"]}')
        
        if response.status_code == 200:
            user = response.json()
            return render_template('home.html', user=user)
        else:
            return redirect(url_for('signin'))
    except Exception as e:
        print(f"Error fetching user data: {e}")
        return redirect(url_for('signin'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Backend API URL
BACKEND_URL = os.environ.get('BACKEND_URL', 'http://backend:5000')

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('signin'))
        return f(*args, **kwargs)
    return decorated_function

# Home page
@app.route('/')
def index():
    return render_template('index.html')

# Sign up page (GET)
@app.route('/signup', methods=['GET'])
def signup():
    return render_template('signup.html')

# Sign up handler (POST)
@app.route('/signup', methods=['POST'])
def signup_post():
    try:
        data = request.get_json()
        
        # Call backend API to create user
        response = requests.post(f'{BACKEND_URL}/signup', json=data)
        result = response.json()
        
        if response.status_code == 201:
            # Store user info in session
            session['user_id'] = result['user']['id']
            session['user_email'] = result['user']['email']
            return jsonify({'success': True, 'redirect': url_for('account')})
        else:
            return jsonify({'success': False, 'message': result.get('error', 'Sign up failed')})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# Sign in page (GET)
@app.route('/signin', methods=['GET'])
def signin():
    return render_template('signin.html')

# Sign in handler (POST)
@app.route('/signin', methods=['POST'])
def signin_post():
    try:
        data = request.get_json()
        
        # Call backend API to authenticate
        response = requests.post(f'{BACKEND_URL}/login', json=data)
        result = response.json()
        
        if response.status_code == 200:
            # Store user info in session
            session['user_id'] = result['user']['id']
            session['user_email'] = result['user']['email']
            return jsonify({'success': True, 'redirect': url_for('account')})
        else:
            return jsonify({'success': False, 'message': result.get('error', 'Invalid credentials')})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# Sign out
@app.route('/signout')
def signout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/home')
@login_required
def home():
    try:
        # Get user data from backend
        response = requests.get(f'{BACKEND_URL}/user/{session["user_id"]}')
        
        if response.status_code == 200:
            user = response.json()
            return render_template('home.html', user=user)
        else:
            return redirect(url_for('signin'))
    except Exception as e:
        print(f"Error fetching user data: {e}")
        return redirect(url_for('signin'))

# Account page
@app.route('/account')
@login_required
def account():
    try:
        # Get user data from backend
        response = requests.get(f'{BACKEND_URL}/user/{session["user_id"]}')
        
        if response.status_code == 200:
            user = response.json()
            return render_template('account.html', user=user)
        else:
            return redirect(url_for('signin'))
    except Exception as e:
        print(f"Error fetching user data: {e}")
        return redirect(url_for('signin'))

# Update account (POST)
@app.route('/account', methods=['POST'])
@login_required
def account_update():
    try:
        data = request.get_json()
        
        # Call backend API to update user
        response = requests.put(
            f'{BACKEND_URL}/user/{session["user_id"]}',
            json=data
        )
        result = response.json()
        
        if response.status_code == 200:
            return jsonify({'success': True, 'message': 'Profile updated successfully'})
        else:
            return jsonify({'success': False, 'message': result.get('error', 'Update failed')})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
