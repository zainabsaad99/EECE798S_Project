from flask import Flask, render_template, request, jsonify, session, url_for, redirect
import requests
import re
import os
import logging
from dotenv import load_dotenv
from pathlib import Path
from functools import wraps
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file at project root
# Go up one level from frontend/ to project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-123-abc!@#')
# Backend URL for server-side requests - MUST be set via PUBLIC_BACKEND_URL environment variable
BACKEND_API_URL = os.environ.get('PUBLIC_BACKEND_URL')
if not BACKEND_API_URL:
    raise ValueError("PUBLIC_BACKEND_URL environment variable is required but not set!")

logger.info(f"🔵 [CONFIG] BACKEND_API_URL: {BACKEND_API_URL}")
Fetch_Website_API_URL = os.environ.get('FETCH_WEBSITE_URL', 'http://fetch_website:3001')
LLM_API_URL = os.environ.get('LLM_API_URL', 'http://trend_keywords:3002')
TRENDS_SEARCH_URL = os.environ.get('TRENDS_SEARCH_URL', 'http://trends_search:3003')
# PUBLIC_BACKEND_URL for client-side JavaScript (same as BACKEND_API_URL)
PUBLIC_BACKEND_URL = os.environ.get('PUBLIC_BACKEND_URL')
if not PUBLIC_BACKEND_URL:
    raise ValueError("PUBLIC_BACKEND_URL environment variable is required but not set!")

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
    # If user is logged in, redirect to dashboard
    if user:
        return redirect(url_for('home'))
    return render_template('index.html', user=user)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            logger.info("🔵 [FRONTEND SIGNUP] Request received")
            
            # Get request data
            if request.is_json:
                data = request.get_json()
            else:
                data = request.form.to_dict()
            
            logger.info(f"🔵 [FRONTEND SIGNUP] Data received: {data}")
            logger.info(f"🔵 [FRONTEND SIGNUP] Backend URL: {BACKEND_API_URL}")
            
            # Validate backend URL is set
            if not BACKEND_API_URL:
                logger.error("❌ [FRONTEND SIGNUP] BACKEND_API_URL is not set!")
                return jsonify({
                    "success": False,
                    "message": "Backend URL not configured. Please check environment variables."
                }), 500
            
            # Make request to backend
            try:
                backend_url = f"{BACKEND_API_URL}/signup"
                logger.info(f"🔵 [FRONTEND SIGNUP] Calling backend: {backend_url}")
                
                response = requests.post(backend_url, json=data, timeout=30)
                logger.info(f"🔵 [FRONTEND SIGNUP] Backend response status: {response.status_code}")
                logger.info(f"🔵 [FRONTEND SIGNUP] Backend response headers: {dict(response.headers)}")
                logger.info(f"🔵 [FRONTEND SIGNUP] Backend response text (first 500 chars): {response.text[:500]}")
                
                # Try to parse JSON response
                try:
                    result = response.json()
                    logger.info(f"🔵 [FRONTEND SIGNUP] Parsed JSON: {result}")
                    return jsonify(result), response.status_code
                except ValueError as e:
                    logger.error(f"❌ [FRONTEND SIGNUP] Failed to parse JSON: {e}")
                    logger.error(f"❌ [FRONTEND SIGNUP] Response text: {response.text}")
                    return jsonify({
                        "success": False,
                        "message": f"Backend returned invalid JSON (status {response.status_code}): {response.text[:200]}"
                    }), 500
                    
            except requests.exceptions.Timeout:
                logger.error("❌ [FRONTEND SIGNUP] Request timeout")
                return jsonify({
                    "success": False,
                    "message": "Request to backend timed out. Please try again."
                }), 504
            except requests.exceptions.ConnectionError as e:
                logger.error(f"❌ [FRONTEND SIGNUP] Connection error: {e}")
                return jsonify({
                    "success": False,
                    "message": f"Cannot connect to backend at {BACKEND_API_URL}. Please check if backend is running."
                }), 503
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ [FRONTEND SIGNUP] Request error: {e}")
                return jsonify({
                    "success": False,
                    "message": f"Error communicating with backend: {str(e)}"
                }), 500
                
        except Exception as e:
            logger.exception("❌ [FRONTEND SIGNUP] Unexpected error")
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"❌ [FRONTEND SIGNUP] Full traceback: {error_trace}")
            return jsonify({
                "success": False,
                "message": f"Unexpected error: {str(e)}"
            }), 500
            
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



@app.route('/upload-json', methods=['GET', 'POST'])
def upload_json():
    user = session.get('user')  # get logged-in user info from session
    if not user:
        return jsonify({"success": False, "message": "User not logged in."}), 401

    user_id = user.get('user_id')

    if request.method == 'POST':
        if 'json_file' not in request.files:
            return jsonify({"success": False, "message": "No file part in the request."}), 400

        file = request.files['json_file']
        if file.filename == '':
            return jsonify({"success": False, "message": "No selected file."}), 400

        if file and file.filename.endswith('.json'):
            try:
                json_data = json.load(file)
                print(f"Uploaded JSON data: {json_data}", flush=True)

                # --- Call save_uploaded_json API ---
                try:
                    response = requests.post(
                        f"{BACKEND_API_URL}/upload-json",
                        json={
                            "user_id": user_id,
                            "json_data": json_data
                        }
                    )
                    response_data = response.json()
                    status_code = response.status_code
                    
                    # Check if the upload was successful
                    if status_code == 201 and response_data.get("success"):
                        # Redirect to gap analysis page after successful upload
                        return redirect(url_for('gap_analysis'))
                    else:
                        return jsonify({"success": False, "message": response_data.get("message", "Failed to save JSON data")}), status_code
                except Exception as e:
                    return jsonify({"success": False, "message": f"Error calling save API: {e}"}), 500

            except Exception as e:
                return jsonify({"success": False, "message": f"Error processing JSON file: {e}"}), 500
        else:
            return jsonify({"success": False, "message": "Invalid file type. Please upload a JSON file."}), 400

    # GET method: render upload page
    return render_template('upload_json.html', user=user)

@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    user = session.get('user')
    if not user:
        return jsonify({"success": False, "redirect": url_for('signin')}), 401

    user_id = user.get('user_id')
    

    if request.method == 'POST':
       
        data = request.get_json() if request.is_json else request.form

        # Save the basic account info first
        try:
            
            response = requests.post(f"{BACKEND_API_URL}/account", json={**data, "user_id": user_id})
            response.raise_for_status()
        except Exception as e:
            return jsonify({"success": False, "message": f"Failed to update profile: {e}"}), 500
        

        # Check if user already has website data
        try:
            check_resp = requests.get(f"{BACKEND_API_URL}/user-has-data/{user_id}")
            check_resp.raise_for_status()
            has_data = check_resp.json().get("has_data", False)
        except Exception as e:
            print(f"Failed to check user website data: {e}", flush=True)
            return jsonify({"success": False, "message": f"Failed to check user website data: {e}"}), 500
         # Handle JSON upload via backend API
       

        # If no website data, fetch and save
        if not has_data:
            website_url = data.get("website")
            if not website_url:
                return jsonify({"success": False, "message": "Website URL is required for extraction."}), 400

            # 1️⃣ Fetch website data from extract_website endpoint
            try:
                extract_resp = requests.post(f"{Fetch_Website_API_URL}/extract-website", json={"url": website_url})
                extract_resp.raise_for_status()
                extracted_data = extract_resp.json().get("data")
                if not extracted_data:
                    return jsonify({"success": False, "message": "No data extracted from website."}), 500
            except Exception as e:
                return jsonify({"success": False, "message": f"Website extraction failed: {e}"}), 500
            print(f"Extracted data: {extracted_data}", flush=True)
            # 2️⃣ Save extracted website data
            try:
                save_resp = requests.post(f"{BACKEND_API_URL}/save-website-data", json={
                    "user_id": user_id,
                    "extracted": extracted_data
                })
                save_resp.raise_for_status()
                save_result = save_resp.json()
            except Exception as e:
                return jsonify({"success": False, "message": f"Failed to save website data: {e}"}), 500
            print("Website data fetched and saved successfully.", flush=True)
            print(f"Save result: {save_result}", flush=True)
          
            # Get user websites again after saving Without products
            websites_data = []
            response = requests.get(f"{BACKEND_API_URL}/get-websites/{user_id}")
            if response.status_code == 200:
                websites_data = response.json().get("data", [])
                print(f"Websites data: {websites_data}", flush=True)
            print(f"Websites to process: {websites_data}", flush=True)

            # extract Keywords using LLM in batch from website contents
            try:
                llm_response = requests.post(f"{LLM_API_URL}/extract-phrases-batch", json={"websites": websites_data})
                llm_response.raise_for_status()
                llm_results = llm_response.json().get("results", [])
            except Exception as e:
                return jsonify({"success": False, "message": f"LLM extraction failed: {e}"}), 500
            print(f"LLM results: {llm_results}", flush=True)
            
            # Update backend
            update_results = []
           
            # for each result, update the trend keywords in backend
            for result in llm_results:   
                website_id = result.get("website_id")
                trend_keywords = result.get("trend_keywords", [])
                try:
                    update_resp = requests.put(
                        f"{BACKEND_API_URL}/update-trend-keywords/{website_id}",
                        json={"trend_keywords": trend_keywords}
                    )
                    updated = update_resp.status_code == 200
                except Exception as e:
                    print(f"[ERROR] Updating website {website_id}: {e}", flush=True)
                    updated = False

                update_results.append({
                    "website_id": website_id,
                    "domain": result.get("domain"),
                    "updated": updated,
                    "trend_keywords": trend_keywords
                })
        


        #this part not needed use to test only 
        response = requests.get(f"{BACKEND_API_URL}/get-websites/{user_id}")
        if response.status_code == 200:
                wbebsites_data = response.json().get("data", [])
        print(f"Websites to process: {wbebsites_data}", flush=True)
        
        # response = requests.get(f"{BACKEND_API_URL}/get-trend-keywords-by-user/{user_id}")
        # if response.status_code == 200:
        #         keywords = response.json().get("data", [])
        #         print(f"keywords: {keywords}", flush=True)
        # first_keyword = keywords[0]["trend_keywords"][0]
        # print(first_keyword,flush=True)

        # llm_response = requests.post(
        #         f"{LLM_API_URL}/generate-trends",
        #         json={"keywords": [first_keyword]}   # <-- SEND AS LIST WITH ONE STRING
        #     )
        
        # llm_response.raise_for_status()

        # trend_results = llm_response.json()
        # print(f"[TRENDS GENERATED]: {trend_results}", flush=True)   
        # If website data exists, no extraction needed
        return jsonify({"success": True, "message": "Profile updated. Website data already exists."}), 200

    # GET request - render profile
    try:
        profile_resp = requests.get(f"{BACKEND_API_URL}/account", json={"user_id": user_id})
        profile_resp.raise_for_status()
        profile = profile_resp.json().get("user")
        return render_template('account.html', user=profile)
    except Exception as e:
        return jsonify({"success": False, "message": f"Could not load profile: {e}"}), 400

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
            # Pass backend URL to template for JavaScript
            return render_template('home.html', user=user_data, backend_url=PUBLIC_BACKEND_URL)
        else:
            return redirect(url_for('signin'))
    except Exception as e:
        print(f"Error fetching user data: {e}")
        return redirect(url_for('signin'))


@app.route('/content-studio')
@login_required
def content_studio():
    """Content generation workspace"""
    user = session.get('user') or {}
    user_id = user.get('user_id')
    profile = None
    try:
        if user_id:
            response = requests.get(f'{BACKEND_API_URL}/account', json={'user_id': user_id})
            if response.status_code == 200:
                profile = response.json().get('user')
    except Exception as exc:
        print(f"Error fetching user profile for content studio: {exc}")
    backend_base = PUBLIC_BACKEND_URL.rstrip('/')
    content_api = f"{backend_base}/api/content/generate"
    return render_template('content_generation.html', user=profile or user, content_api=content_api)

@app.route('/chat-interface')
@login_required
def chat_interface():
    """Chat interface selection page with LinkedIn Chat and Content Chat options"""
    user = session.get('user') or {}
    user_id = user.get('user_id')
    profile = None
    try:
        if user_id:
            response = requests.get(f'{BACKEND_API_URL}/account', json={'user_id': user_id})
            if response.status_code == 200:
                profile = response.json().get('user')
    except Exception as exc:
        print(f"Error fetching user profile for chat interface: {exc}")
    return render_template('chat_interface.html', user=profile or user)

@app.route('/content-studio-chat')
@login_required
def content_studio_chat():
    """Chat-based content generation workspace"""
    user = session.get('user') or {}
    user_id = user.get('user_id')
    profile = None
    try:
        if user_id:
            response = requests.get(f'{BACKEND_API_URL}/account', json={'user_id': user_id})
            if response.status_code == 200:
                profile = response.json().get('user')
    except Exception as exc:
        print(f"Error fetching user profile for content studio chat: {exc}")
    backend_base = PUBLIC_BACKEND_URL.rstrip('/')
    content_api = f"{backend_base}/api/content/generate"
    return render_template('content_studio_chat.html', user=profile or user, content_api=content_api)

@app.route('/proposal-content')
@login_required
def proposal_content():
    user = session.get('user') or {}
    user_id = user.get('user_id')
    profile = None
    try:
        if user_id:
            response = requests.get(f'{BACKEND_API_URL}/account', json={'user_id': user_id})
            if response.status_code == 200:
                profile = response.json().get('user')
    except Exception as exc:
        print(f"Error fetching user profile for proposal content: {exc}")
    backend_base = PUBLIC_BACKEND_URL.rstrip('/')
    proposal_api = f"{backend_base}/api/proposal/generate"
    return render_template('proposal_content.html', user=profile or user, content_api=proposal_api)
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
        'backend_url': PUBLIC_BACKEND_URL,  # Backend URL for client-side requests
    }
    return render_template('linkedin_agent.html', user=user_data, env_config=env_config, user_linkedin_data=user_linkedin_data)


@app.route('/linkedin-agent-chat')
@login_required
def linkedin_agent_chat():
    """Chat-based LinkedIn content agent experience."""
    try:
        user = session.get('user')
        user_id = user.get('user_id') if user else None

        if not user_id:
            return render_template(
                'linkedin_agent_chat.html',
                user=None,
                env_config={},
                user_linkedin_data=None,
                error_message="Please sign in to access the LinkedIn Chat Agent."
            )

        user_data = None
        user_linkedin_url = ''

        response = requests.get(f'{BACKEND_API_URL}/account', json={'user_id': user_id})
        if response.status_code == 200:
            user_data = response.json().get('user', {})
            user_linkedin_url = user_data.get('linkedin', '')

        if not user_linkedin_url:
            return render_template(
                'linkedin_agent_chat.html',
                user=user_data,
                env_config={},
                user_linkedin_data=None,
                error_message="Please add your LinkedIn Profile URL in your account settings first."
            )

        user_linkedin_data = None
        try:
            response = requests.get(f'{BACKEND_API_URL}/api/linkedin/user-data', params={'user_id': user_id})
            if response.status_code == 200:
                user_linkedin_data = response.json()
        except Exception as exc:
            print(f"Error fetching user LinkedIn data for chat agent: {exc}")

        has_data = (
            user_linkedin_data
            and user_linkedin_data.get('success')
            and user_linkedin_data.get('keywords')
            and len(user_linkedin_data.get('keywords', [])) > 0
            and user_linkedin_data.get('tone_of_writing')
        )

        if not has_data:
            return render_template(
                'linkedin_agent_chat.html',
                user=user_data,
                env_config={},
                user_linkedin_data=None,
                error_message="Your LinkedIn profile is being analyzed. Please wait a few minutes and refresh the page."
            )

    except Exception as exc:
        print(f"Error in linkedin_agent_chat route: {exc}")
        return render_template(
            'linkedin_agent_chat.html',
            user=None,
            env_config={},
            user_linkedin_data=None,
            error_message="An error occurred. Please try again."
        )

    default_sheet_url = 'https://docs.google.com/spreadsheets/d/10OsJwVQAboMx3LKfoZhQLRQ9w9UuekvNG1_oaZNgOMM/edit?usp=sharing'
    env_config = {
        'openai_api_key': os.environ.get('OPENAI_API_KEY', ''),
        'phantombuster_api_key': os.environ.get('PHANTOMBUSTER_API_KEY', ''),
        'firecrawl_api_key': os.environ.get('FIRECRAWL_API_KEY', ''),
        'user_agent': os.environ.get('USER_AGENT', ''),
        'google_sheet_url': os.environ.get('GOOGLE_SHEET_URL', default_sheet_url),
        'linkedin_session_cookie': os.environ.get('LINKEDIN_SESSION_COOKIE', ''),
        'user_linkedin_url': user_linkedin_url,
        'user_id': user_id,
        'backend_url': PUBLIC_BACKEND_URL,  # Backend URL for client-side requests
    }

    return render_template(
        'linkedin_agent_chat.html',
        user=user_data,
        env_config=env_config,
        user_linkedin_data=user_linkedin_data
    )

@app.route('/gap-analysis')
@login_required
def gap_analysis():
    user = session.get('user') or {}
    user_id = user.get('user_id')
    profile = None
    try:
        if user_id:
            response = requests.get(f'{BACKEND_API_URL}/account', json={'user_id': user_id})
            if response.status_code == 200:
                profile = response.json().get('user')
                if profile and profile.get('id'):
                    user_id = profile.get('id')
    except Exception as exc:
        print(f"Error fetching user profile for gap analysis: {exc}")
    backend_base = PUBLIC_BACKEND_URL.rstrip('/')
    gap_api = f"{backend_base}/api/gap-analysis"
    # keywords_api = f"{backend_base}/api/gap/keywords"
    keywords_api = f"{backend_base}/get-trend-keywords-list/{user_id}"
    
    business_api = f"{backend_base}/get-json/{user_id}"
    trends_api = f"{backend_base}/api/gap/trends"
    print(f"trend api {keywords_api}", flush=True)
    return render_template(
        'gap_analysis.html',
        user=profile or user,
        user_id=user_id,
        gap_api=gap_api,
        gap_keywords_api=keywords_api,
        gap_business_api=business_api,
        gap_trends_api=trends_api,
    )

# Health check endpoint for Azure Container Apps
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Azure Container Apps"""
    return jsonify({
        "status": "healthy",
        "service": "frontend"
    }), 200

if __name__ == '__main__':
    # Use production settings when FLASK_ENV is set to production
    debug_mode = os.getenv('FLASK_ENV', 'development') != 'production'
    app.run(debug=debug_mode, host='0.0.0.0', port=3000)
