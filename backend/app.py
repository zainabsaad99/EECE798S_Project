from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import mysql.connector
import os
from werkzeug.security import generate_password_hash, check_password_hash
import logging
import sys
from datetime import datetime
import tempfile
import shutil
import time
import threading
from pathlib import Path
from dotenv import load_dotenv
import json
import requests
from linkedin_agent import (
    run_agent_sequence,
    generate_linkedin_post,
    fetch_trends_firecrawl,
    save_post_to_google_sheet,
    trigger_phantombuster_autopost,
    clear_google_sheet,
    scrape_profile_tool,
    extract_keywords_tool,
    infer_style_tool
)
from content_agent import (
    generate_social_content_and_images,
    SUPPORTED_PLATFORMS,
    DEFAULT_LOGO_POSITION,
    DEFAULT_LOGO_SCALE,
)
from proposal_agent import (
    generate_proposal_content_and_images,
)
from gap_analysis import run_gap_analysis
from trend_service import generate_trends_from_keywords


DEFAULT_GAP_KEYWORDS = [
    {"id": "fallback-1", "keyword": "AI copilots", "category": "Product"},
    {"id": "fallback-2", "keyword": "Zero-party data", "category": "Data"},
    {"id": "fallback-3", "keyword": "Workflow automation", "category": "Operations"},
    {"id": "fallback-4", "keyword": "Revenue analytics", "category": "Growth"},
]

DEFAULT_GAP_BUSINESSES = [
    {
        "name": "shein",
        "strapline": "Best chinese products.",
        "audience": "People who like shopping",
        "products": [
            {
                "name": "tshirt",
                "description": "Best black cotton tshirt"
            }
        ]
    }
]

# Load environment variables from .env file at project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Configure logging for Azure (structured logging to stdout)
logging.basicConfig(
    level=logging.INFO if os.getenv('FLASK_ENV') == 'production' else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

app = Flask(__name__)

# Configure CORS for Azure deployment
# Allow specific origins via CORS_ORIGINS env var (comma-separated)
# Defaults to '*' for local development
allowed_origins = os.getenv('CORS_ORIGINS', '*').split(',')
if allowed_origins == ['*']:
    CORS(app)  # Allow all origins (for local development)
else:
    CORS(app, origins=allowed_origins, supports_credentials=True)

DB_HOST = os.getenv('DB_HOST', 'db')  # 'db' matches the service name in docker-compose.yml
DB_PORT = os.getenv('DB_PORT', '3306')
DB_NAME = os.getenv('DB_NAME', 'NextGenAI')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
MAX_LOGO_UPLOAD_BYTES = int(os.getenv('MAX_LOGO_UPLOAD_BYTES', 5 * 1024 * 1024))
MAX_REFERENCE_IMAGE_BYTES = int(os.getenv('MAX_REFERENCE_IMAGE_BYTES', 10 * 1024 * 1024))

def get_db_connection():
    # Azure MySQL requires SSL connection
    # For local development with docker-compose, SSL is disabled
    # For Azure MySQL, SSL is required
    use_ssl = 'database.azure.com' in DB_HOST
    
    conn = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        ssl_disabled=not use_ssl
    )
    return conn


def track_activity(user_id, activity_type, activity_subtype=None, metadata=None):
    """Track user activity in the database"""
    if not user_id:
        return
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        metadata_json = json.dumps(metadata) if metadata else None
        cursor.execute(
            "INSERT INTO user_activities (user_id, activity_type, activity_subtype, metadata) VALUES (%s, %s, %s, %s)",
            (user_id, activity_type, activity_subtype, metadata_json)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        app.logger.warning(f"Failed to track activity: {e}")


def _parse_platforms(raw_value):
    if isinstance(raw_value, list):
        return raw_value
    if isinstance(raw_value, str):
        try:
            loaded = json.loads(raw_value)
            if isinstance(loaded, list):
                return loaded
        except Exception:
            pass
        return [item.strip() for item in raw_value.split(',') if item.strip()]
    return []


def _parse_size_overrides(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            pass
    return None


def _safe_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def _parse_keywords_blob(value):
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        pass
    tokens = []
    for token in text.replace('\n', ',').split(','):
        cleaned = token.strip().strip('`')
        if cleaned:
            tokens.append(cleaned)
    return tokens


# ----------------------------- SIGNUP -----------------------------
@app.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json(silent=True) or request.form
        full_name = data.get('full_name')
        email = data.get('email')
        password = data.get('password')
        linkedin_url = data.get('linkedin', '').strip()

        if not all([full_name, email, password]):
            return jsonify({"success": False, "message": "All fields are required."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Email already registered."}), 409

        hashed = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (full_name, email, password) VALUES (%s, %s, %s);",
            (full_name, email, hashed)
        )
        user_id = cursor.lastrowid
        conn.commit()

        return jsonify({"success": True, "message": "User registered successfully.", "redirect": "/signin"}), 201
    except Exception as e:
        app.logger.exception("Signup failed")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass


def scrape_and_save_user_data(user_id: int, linkedin_url: str, phantom_api_key: str, session_cookie: str, user_agent: str, openai_api_key: str):
    """Scrape user's LinkedIn profile and save keywords and tone to database"""
    try:
        # Scrape profile
        scrape_result = scrape_profile_tool(
            phantom_api_key=phantom_api_key,
            session_cookie=session_cookie,
            user_agent=user_agent,
            profile_url=linkedin_url
        )
        
        posts = scrape_result.get('posts', [])
        if not posts:
            app.logger.warning(f"No posts found for user {user_id}")
            return
        
        # Extract keywords
        keywords_result = extract_keywords_tool(
            openai_api_key=openai_api_key,
            posts=posts
        )
        keywords = keywords_result.get('keywords', [])
        
        # Extract tone/style
        style_result = infer_style_tool(
            openai_api_key=openai_api_key,
            posts=posts
        )
        tone = style_result.get('style_notes', '')
        
        # Save to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        keywords_json = json.dumps(keywords)
        
        cursor.execute(
            """INSERT INTO user_linkedin_data (user_id, keywords, tone_of_writing) 
               VALUES (%s, %s, %s)
               ON DUPLICATE KEY UPDATE keywords=%s, tone_of_writing=%s, updated_at=CURRENT_TIMESTAMP""",
            (user_id, keywords_json, tone, keywords_json, tone)
        )
        conn.commit()
        
        app.logger.info(f"Successfully saved LinkedIn data for user {user_id}")
        
        cursor.close()
        conn.close()
    except Exception as e:
        app.logger.exception(f"Error scraping and saving user data for user {user_id}: {e}")


# ----------------------------- SIGNIN -----------------------------
@app.route('/signin', methods=['POST'])
def signin():
    try:
        data = request.get_json(silent=True) or request.form
        email, password = data.get('email'), data.get('password')

        if not email or not password:
            return jsonify({"success": False, "message": "All fields are required."}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            return jsonify({
                "success": True,
                "user_id": user['id'],
                "email": user['email'],
                "full_name": user['full_name'],
                "redirect": "/home"
            }), 200

        return jsonify({"success": False, "message": "Invalid credentials."}), 401
    except Exception as e:
        app.logger.exception("Signin failed")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass


# ----------------------------- ACCOUNT -----------------------------
@app.route('/account', methods=['GET', 'POST'])
def account():
    try:
        data = request.get_json(silent=True) or request.form
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({"success": False, "message": "Missing user_id"}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # --- UPDATE ---
        if request.method == 'POST':
            update_fields = {
                'full_name': data.get('full_name'),
                'company': data.get('company'),
                'job_title': data.get('job_title'),
                'phone': data.get('phone'),
                'website': data.get('website'),
                'linkedin': data.get('linkedin'),
                'industry': data.get('industry'),
                'company_size': data.get('company_size'),
                'marketing_goals': data.get('marketing_goals')
            }

            # Check if LinkedIn URL is being updated
            linkedin_updated = False
            # Safely handle None for linkedin - use 'or' to convert None to empty string
            new_linkedin_url = (update_fields.get('linkedin') or '').strip()
            if new_linkedin_url:
                # Get current LinkedIn URL to compare
                cursor.execute("SELECT linkedin FROM users WHERE id=%s", (user_id,))
                current_user = cursor.fetchone()
                current_linkedin = current_user.get('linkedin', '') if current_user else ''
                linkedin_updated = new_linkedin_url != current_linkedin

            set_clauses, values = [], []
            for field, value in update_fields.items():
                if value not in [None, ""]:
                    set_clauses.append(f"{field}=%s")
                    values.append(value)

            if not set_clauses:
                return jsonify({"success": False, "message": "No data to update."}), 400

            values.append(user_id)
            cursor.execute(f"UPDATE users SET {', '.join(set_clauses)} WHERE id=%s", values)
            conn.commit()

            # If LinkedIn URL was updated, trigger scraping and wait for completion
            if linkedin_updated and new_linkedin_url:
                try:
                    phantom_api_key = os.environ.get('PHANTOMBUSTER_API_KEY', '')
                    session_cookie = os.environ.get('LINKEDIN_SESSION_COOKIE', '')
                    user_agent = os.environ.get('USER_AGENT', '')
                    openai_api_key = os.environ.get('OPENAI_API_KEY', '')
                    
                    if all([phantom_api_key, session_cookie, user_agent, openai_api_key]):
                        app.logger.info(f"LinkedIn URL updated for user {user_id}, starting scrape and extraction")
                        # Run scraping synchronously - wait for completion
                        scrape_and_save_user_data(user_id, new_linkedin_url, phantom_api_key, session_cookie, user_agent, openai_api_key)
                        return jsonify({
                            "success": True, 
                            "message": "Profile updated successfully! LinkedIn profile analyzed and keywords/tone extracted.",
                            "linkedin_processed": True
                        }), 200
                    else:
                        # LinkedIn URL saved successfully, but analysis will happen later when API keys are configured
                        return jsonify({
                            "success": True,
                            "message": "Profile saved successfully! Your LinkedIn URL has been saved. Profile analysis will be performed automatically when you use the LinkedIn Agent feature.",
                            "linkedin_processed": False
                        }), 200
                except Exception as e:
                    app.logger.error(f"Error scraping LinkedIn profile after update: {e}")
                    return jsonify({
                        "success": True,  # Still return success since the URL was saved
                        "message": f"Profile saved successfully! LinkedIn URL saved. Profile analysis will be performed when you use the LinkedIn Agent.",
                        "linkedin_processed": False
                    }), 200
            
            return jsonify({"success": True, "message": "Profile updated successfully!"}), 200

        # --- GET ---
        cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404

        created_at = user.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except Exception:
                try:
                    created_at = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    created_at = None

        user["created_at_formatted"] = created_at.strftime("%B %Y") if created_at else "N/A"
        return jsonify({"success": True, "user": user}), 200

    except mysql.connector.Error as err:
        app.logger.error(f"MySQL Error: {err}")
        return jsonify({"success": False, "message": "Database schema issue. Please run migrations."}), 500
    except Exception as e:
        app.logger.exception("Account route failed")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass


# ----------------------------- LINKEDIN AGENT -----------------------------
@app.route('/api/linkedin/user-data', methods=['GET'])
def linkedin_user_data():
    """Get user's saved keywords and tone from database"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"success": False, "message": "Missing user_id"}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute(
            "SELECT keywords, tone_of_writing FROM user_linkedin_data WHERE user_id=%s",
            (user_id,)
        )
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result:
            keywords = result.get('keywords')
            if isinstance(keywords, str):
                try:
                    keywords = json.loads(keywords)
                except:
                    keywords = []
            return jsonify({
                "success": True,
                "keywords": keywords or [],
                "tone_of_writing": result.get('tone_of_writing') or ''
            }), 200
        else:
            return jsonify({
                "success": True,
                "keywords": [],
                "tone_of_writing": ""
            }), 200
            
    except Exception as e:
        app.logger.exception("Error fetching user LinkedIn data")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/linkedin/regenerate-user-data', methods=['POST'])
def linkedin_regenerate_user_data():
    """Regenerate keywords and tone from user's LinkedIn profile with streaming progress"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        stream = data.get('stream', False)
        
        if not user_id:
            return jsonify({"success": False, "message": "Missing user_id"}), 400
        
        # Get user's LinkedIn URL
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT linkedin FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user or not user.get('linkedin'):
            return jsonify({"success": False, "message": "LinkedIn URL not found. Please set it in your account settings."}), 400
        
        linkedin_url = user.get('linkedin')
        
        # Get API keys from request or environment
        phantom_api_key = data.get('phantom_api_key') or os.environ.get('PHANTOMBUSTER_API_KEY', '')
        session_cookie = data.get('session_cookie') or os.environ.get('LINKEDIN_SESSION_COOKIE', '')
        user_agent = data.get('user_agent') or os.environ.get('USER_AGENT', '')
        openai_api_key = data.get('openai_api_key') or os.environ.get('OPENAI_API_KEY', '')
        
        if not all([phantom_api_key, session_cookie, user_agent, openai_api_key]):
            return jsonify({
                "success": False, 
                "message": "Missing required API keys. Please configure PHANTOMBUSTER_API_KEY, LINKEDIN_SESSION_COOKIE, USER_AGENT, and OPENAI_API_KEY."
            }), 400
        
        if stream:
            # Streaming version with progress updates
            def generate_progress():
                try:
                    yield f"data: {json.dumps({'progress': 'Starting LinkedIn profile scrape...'})}\n\n"
                    
                    from linkedin_agent import launch_linkedin_scrape, fetch_container_output_for_json_url, download_posts_json
                    import time
                    
                    yield f"data: {json.dumps({'progress': 'Launching PhantomBuster scrape...'})}\n\n"
                    container_id = launch_linkedin_scrape(
                        phantom_api_key=phantom_api_key,
                        session_cookie=session_cookie,
                        user_agent=user_agent,
                        profile_url=linkedin_url,
                    )
                    
                    yield f"data: {json.dumps({'progress': 'Scrape launched! Waiting for results... This usually takes 2-3 minutes.'})}\n\n"
                    
                    # Poll with progress updates
                    import time as time_module
                    from linkedin_agent import PHANTOM_FETCH_OUTPUT_URL, DEFAULT_POLL_SECONDS, DEFAULT_MAX_WAIT_SECONDS
                    import re
                    from linkedin_agent import _http_get_text
                    
                    headers = {"x-phantombuster-key": phantom_api_key}
                    deadline = time_module.time() + DEFAULT_MAX_WAIT_SECONDS
                    primary_pat = re.compile(r"JSON saved at\s+(https?://\S+?)\s+result\.json", re.IGNORECASE)
                    fallback_pat = re.compile(r"(https?://\S*?result\.json)", re.IGNORECASE)
                    found_url = None
                    poll_count = 0
                    last_progress_time = time_module.time()
                    start_time = time_module.time()
                    
                    while time_module.time() < deadline and not found_url:
                        url_with_id = f"{PHANTOM_FETCH_OUTPUT_URL}?id={container_id}"
                        text = _http_get_text(url_with_id, headers=headers, debug=False)
                        m = primary_pat.search(text)
                        if m:
                            base = m.group(1).rstrip("/")
                            found_url = f"{base}/result.json"
                            break
                        m2 = fallback_pat.search(text)
                        if m2:
                            found_url = m2.group(1)
                            break
                        
                        poll_count += 1
                        elapsed = int(time_module.time() - start_time)
                        
                        # Send progress updates every 15-20 seconds
                        if time_module.time() - last_progress_time >= 15:
                            if elapsed < 60:
                                yield f"data: {json.dumps({'progress': f'Scraping in progress... ({elapsed}s elapsed)'})}\n\n"
                            elif elapsed < 120:
                                yield f"data: {json.dumps({'progress': f'Still scraping... This usually takes 2-3 minutes ({elapsed}s elapsed)'})}\n\n"
                            else:
                                yield f"data: {json.dumps({'progress': f'Scraping taking longer than usual... Please wait ({elapsed}s elapsed)'})}\n\n"
                            last_progress_time = time_module.time()
                        
                        time_module.sleep(DEFAULT_POLL_SECONDS)
                    
                    if not found_url:
                        raise TimeoutError("Could not locate result.json url in PhantomBuster output")
                    
                    yield f"data: {json.dumps({'progress': 'Scrape completed! Downloading posts...'})}\n\n"
                    posts_objects = download_posts_json(found_url)
                    # Convert PostItem objects to dictionaries
                    posts = [p.__dict__ for p in posts_objects]
                    yield f"data: {json.dumps({'progress': f'Downloaded {len(posts)} posts! Analyzing content...'})}\n\n"
                    
                    if not posts:
                        yield f"data: {json.dumps({'progress': 'No posts found in profile.', 'error': 'No posts found', 'done': True})}\n\n"
                        return
                    
                    # Extract keywords
                    yield f"data: {json.dumps({'progress': 'Extracting keywords from your posts using AI...'})}\n\n"
                    keywords_result = extract_keywords_tool(
                        openai_api_key=openai_api_key,
                        posts=posts
                    )
                    keywords = keywords_result.get('keywords', [])
                    yield f"data: {json.dumps({'progress': f'Found {len(keywords)} keywords! Extracting writing style...'})}\n\n"
                    
                    # Extract tone/style
                    yield f"data: {json.dumps({'progress': 'Analyzing writing style and tone using AI...'})}\n\n"
                    style_result = infer_style_tool(
                        openai_api_key=openai_api_key,
                        posts=posts
                    )
                    tone = style_result.get('style_notes', '')
                    yield f"data: {json.dumps({'progress': 'Writing style extracted! Saving to database...'})}\n\n"
                    
                    # Save to database
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    keywords_json = json.dumps(keywords)
                    cursor.execute(
                        """INSERT INTO user_linkedin_data (user_id, keywords, tone_of_writing) 
                           VALUES (%s, %s, %s)
                           ON DUPLICATE KEY UPDATE keywords=%s, tone_of_writing=%s, updated_at=CURRENT_TIMESTAMP""",
                        (user_id, keywords_json, tone, keywords_json, tone)
                    )
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
                    yield f"data: {json.dumps({'progress': 'Keywords and tone saved successfully!', 'done': True, 'keywords': keywords, 'tone_of_writing': tone})}\n\n"
                except GeneratorExit:
                    return
                except Exception as e:
                    app.logger.exception(f"Error in regeneration stream: {e}")
                    yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
            
            return Response(stream_with_context(generate_progress()), mimetype='text/event-stream')
        
        # Non-streaming version (original)
        try:
            scrape_and_save_user_data(user_id, linkedin_url, phantom_api_key, session_cookie, user_agent, openai_api_key)
            
            # Fetch updated data
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT keywords, tone_of_writing FROM user_linkedin_data WHERE user_id=%s",
                (user_id,)
            )
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result:
                keywords = result.get('keywords')
                if isinstance(keywords, str):
                    try:
                        keywords = json.loads(keywords)
                    except:
                        keywords = []
                return jsonify({
                    "success": True,
                    "message": "Keywords and tone regenerated successfully!",
                    "keywords": keywords or [],
                    "tone_of_writing": result.get('tone_of_writing') or ''
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "message": "Regeneration completed but no data was saved."
                }), 500
                
        except Exception as e:
            app.logger.exception(f"Error during regeneration: {e}")
            return jsonify({
                "success": False,
                "message": f"Error regenerating data: {str(e)}"
            }), 500
        
    except Exception as e:
        app.logger.exception("Error regenerating user LinkedIn data")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/linkedin/fetch-trends-only', methods=['POST'])
def linkedin_fetch_trends_only():
    """Fetch trends using saved keywords or provided keywords"""
    try:
        data = request.get_json()
        
        required_fields = ['firecrawl_api_key', 'openai_api_key']
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            return jsonify({"success": False, "message": f"Missing required fields: {', '.join(missing)}"}), 400
        
        keywords = data.get('keywords', [])
        if not keywords:
            return jsonify({"success": False, "message": "Keywords are required"}), 400
        
        trends = fetch_trends_firecrawl(
            firecrawl_api_key=data['firecrawl_api_key'],
            openai_api_key=data['openai_api_key'],
            keywords=keywords,
            topic=data.get('topic')
        )
        
        return jsonify({
            "success": True,
            "trends": [item.model_dump() for item in trends]
        }), 200
        
    except Exception as e:
        app.logger.exception("Trend fetching failed")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/linkedin/run-agent', methods=['POST'])
def linkedin_run_agent():
    """Run the LinkedIn agent sequence - simplified if user has saved keywords/tone"""
    try:
        data = request.get_json()
        
        # Check if streaming is requested
        stream = data.get('stream', False)
        
        # Check if user has saved keywords/tone (skip full agent sequence)
        user_id = data.get('user_id')
        use_saved_data = data.get('use_saved_data', False)
        style_profile_url = data.get('style_profile_url', '').strip()
        
        # If use_saved_data is true, we should NOT run the full agent sequence
        # We only scrape style profile (if provided) and use saved keywords
        if use_saved_data and user_id:
            # Use saved keywords and tone, just fetch trends
            # IMPORTANT: We do NOT scrape user_profile_url - only style_profile_url if provided
            app.logger.info(f"Using saved data for user {user_id}, style_profile_url: {style_profile_url}")
            
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT keywords, tone_of_writing FROM user_linkedin_data WHERE user_id=%s",
                (user_id,)
            )
            saved_data = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not saved_data:
                return jsonify({
                    "success": False,
                    "message": "No saved data found. Please regenerate keywords and tone first."
                }), 400
            
            if saved_data:
                keywords = saved_data.get('keywords')
                if isinstance(keywords, str):
                    try:
                        keywords = json.loads(keywords)
                    except:
                        keywords = []
                
                tone = saved_data.get('tone_of_writing', '')
                
                # If streaming is requested, use streaming endpoint
                if stream:
                    def generate_progress():
                        # Initialize tone from saved data (will be updated if style URL is processed)
                        current_tone = tone
                        try:
                            # If style profile URL provided, scrape it for tone
                            if style_profile_url:
                                yield f"data: {json.dumps({'progress': 'Starting style profile scrape...'})}\n\n"
                                
                                try:
                                    phantom_api_key = data.get('phantom_api_key')
                                    session_cookie = data.get('session_cookie')
                                    user_agent = data.get('user_agent')
                                    openai_api_key = data.get('openai_api_key')
                                    
                                    if all([phantom_api_key, session_cookie, user_agent, openai_api_key]):
                                        # Scrape style profile and get tone with progress updates
                                        from linkedin_agent import launch_linkedin_scrape, fetch_container_output_for_json_url, download_posts_json
                                        import time as time_module
                                        from linkedin_agent import PHANTOM_FETCH_OUTPUT_URL, DEFAULT_POLL_SECONDS, DEFAULT_MAX_WAIT_SECONDS
                                        import re
                                        from linkedin_agent import _http_get_text
                                        
                                        yield f"data: {json.dumps({'progress': 'Launching PhantomBuster scrape for style profile...'})}\n\n"
                                        app.logger.info(f"Scraping style profile URL: {style_profile_url}")
                                        container_id = launch_linkedin_scrape(
                                            phantom_api_key=phantom_api_key,
                                            session_cookie=session_cookie,
                                            user_agent=user_agent,
                                            profile_url=style_profile_url
                                        )
                                        
                                        yield f"data: {json.dumps({'progress': 'Style profile scrape launched! Waiting for results... This usually takes 2-3 minutes.'})}\n\n"
                                        
                                        # Poll with progress updates
                                        headers = {"x-phantombuster-key": phantom_api_key}
                                        deadline = time_module.time() + DEFAULT_MAX_WAIT_SECONDS
                                        primary_pat = re.compile(r"JSON saved at\s+(https?://\S+?)\s+result\.json", re.IGNORECASE)
                                        fallback_pat = re.compile(r"(https?://\S*?result\.json)", re.IGNORECASE)
                                        found_url = None
                                        poll_count = 0
                                        last_progress_time = time_module.time()
                                        start_time = time_module.time()
                                        
                                        while time_module.time() < deadline and not found_url:
                                            url_with_id = f"{PHANTOM_FETCH_OUTPUT_URL}?id={container_id}"
                                            text = _http_get_text(url_with_id, headers=headers, debug=False)
                                            m = primary_pat.search(text)
                                            if m:
                                                base = m.group(1).rstrip("/")
                                                found_url = f"{base}/result.json"
                                                break
                                            m2 = fallback_pat.search(text)
                                            if m2:
                                                found_url = m2.group(1)
                                                break
                                            
                                            poll_count += 1
                                            elapsed = int(time_module.time() - start_time)
                                            
                                            # Send progress updates every 15-20 seconds
                                            if time_module.time() - last_progress_time >= 15:
                                                if elapsed < 60:
                                                    yield f"data: {json.dumps({'progress': f'Scraping style profile... ({elapsed}s elapsed)'})}\n\n"
                                                elif elapsed < 120:
                                                    yield f"data: {json.dumps({'progress': f'Still scraping style profile... This usually takes 2-3 minutes ({elapsed}s elapsed)'})}\n\n"
                                                else:
                                                    yield f"data: {json.dumps({'progress': f'Style profile scraping taking longer than usual... Please wait ({elapsed}s elapsed)'})}\n\n"
                                                last_progress_time = time_module.time()
                                            
                                            time_module.sleep(DEFAULT_POLL_SECONDS)
                                        
                                        if not found_url:
                                            raise TimeoutError("Could not locate result.json url in PhantomBuster output")
                                        
                                        yield f"data: {json.dumps({'progress': 'Style profile scraped! Downloading posts...'})}\n\n"
                                        posts_objects = download_posts_json(found_url)
                                        # Convert PostItem objects to dictionaries
                                        posts = [p.__dict__ for p in posts_objects]
                                        app.logger.info(f"Style profile scraped, found {len(posts)} posts")
                                        
                                        if posts:
                                            yield f"data: {json.dumps({'progress': f'Downloaded {len(posts)} posts! Analyzing writing style...'})}\n\n"
                                            yield f"data: {json.dumps({'progress': 'Extracting writing style using AI...'})}\n\n"
                                            style_result = infer_style_tool(
                                                openai_api_key=openai_api_key,
                                                posts=posts
                                            )
                                            current_tone = style_result.get('style_notes', current_tone)
                                            yield f"data: {json.dumps({'progress': 'Writing style extracted successfully!', 'style_notes': current_tone})}\n\n"
                                        else:
                                            yield f"data: {json.dumps({'progress': 'No posts found in style profile. Using saved style.'})}\n\n"
                                except Exception as e:
                                    app.logger.warning(f"Error scraping style profile, using saved tone: {e}")
                                    yield f"data: {json.dumps({'progress': f'Error scraping profile: {str(e)}. Using saved style.'})}\n\n"
                            
                            # Fetch trends with progress updates
                            yield f"data: {json.dumps({'progress': 'Fetching trends based on your interests...'})}\n\n"
                            yield f"data: {json.dumps({'progress': 'Searching for trending topics using Firecrawl...'})}\n\n"
                            trends = fetch_trends_firecrawl(
                                firecrawl_api_key=data.get('firecrawl_api_key'),
                                openai_api_key=data.get('openai_api_key'),
                                keywords=keywords,
                                topic=None
                            )
                            yield f"data: {json.dumps({'progress': f'Found {len(trends)} trending topics! Processing results...'})}\n\n"
                            
                            yield f"data: {json.dumps({'progress': 'Trends fetched successfully!', 'done': True, 'keywords': keywords, 'style_notes': current_tone, 'trends': [item.model_dump() for item in trends]})}\n\n"
                        except GeneratorExit:
                            # Client disconnected
                            return
                        except Exception as e:
                            app.logger.exception("Error in streaming agent")
                            try:
                                yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
                            except (GeneratorExit, RuntimeError):
                                return
                    
                    return Response(stream_with_context(generate_progress()), mimetype='text/event-stream')
                
                # Non-streaming version (original)
                # If style profile URL provided, scrape it for tone
                if style_profile_url:
                    try:
                        phantom_api_key = data.get('phantom_api_key')
                        session_cookie = data.get('session_cookie')
                        user_agent = data.get('user_agent')
                        openai_api_key = data.get('openai_api_key')
                        
                        if all([phantom_api_key, session_cookie, user_agent, openai_api_key]):
                            # Scrape style profile and get tone
                            scrape_result = scrape_profile_tool(
                                phantom_api_key=phantom_api_key,
                                session_cookie=session_cookie,
                                user_agent=user_agent,
                                profile_url=style_profile_url
                            )
                            posts = scrape_result.get('posts', [])
                            if posts:
                                style_result = infer_style_tool(
                                    openai_api_key=openai_api_key,
                                    posts=posts
                                )
                                tone = style_result.get('style_notes', tone)
                    except Exception as e:
                        app.logger.warning(f"Error scraping style profile, using saved tone: {e}")
                
                # Fetch trends
                trends = fetch_trends_firecrawl(
                    firecrawl_api_key=data.get('firecrawl_api_key'),
                    openai_api_key=data.get('openai_api_key'),
                    keywords=keywords,
                    topic=None
                )
                
                return jsonify({
                    "success": True,
                    "keywords": keywords,
                    "style_notes": tone,
                    "trends": [item.model_dump() for item in trends],
                    "use_saved_data": True
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "message": "No saved data found. Please regenerate keywords and tone first."
                }), 400
        
        # Original full agent sequence (if not using saved data)
        # This should NOT be called when use_saved_data is true
        # Guard: If use_saved_data was true, we should have returned above
        if use_saved_data:
            app.logger.error("use_saved_data is true but code reached full agent sequence - this should not happen")
            return jsonify({
                "success": False,
                "message": "Invalid request: use_saved_data is true but no saved data was processed."
            }), 400
        
        # Validate required fields for full agent sequence
        required_fields = ['openai_api_key', 'phantom_api_key', 'firecrawl_api_key', 
                          'session_cookie', 'user_agent', 'user_profile_url']
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            return jsonify({"success": False, "message": f"Missing required fields: {', '.join(missing)}"}), 400
        
        # If style_profile_url is not provided, use user_profile_url as default
        if not style_profile_url:
            style_profile_url = data['user_profile_url']
            app.logger.info(f"Style profile URL not provided, using user profile URL: {style_profile_url}")
        
        # Handle service account JSON file if provided
        sa_path = None
        if 'service_account_json' in data and data['service_account_json']:
            try:
                # If it's a base64 encoded string, decode and save
                import base64
                sa_json_content = data['service_account_json']
                if isinstance(sa_json_content, str) and sa_json_content.startswith('data:'):
                    # Handle data URL format
                    sa_json_content = base64.b64decode(sa_json_content.split(',')[1]).decode('utf-8')
                elif isinstance(sa_json_content, dict):
                    # If it's already a dict, convert to JSON string
                    import json as json_lib
                    sa_json_content = json_lib.dumps(sa_json_content)
                
                tmpdir = tempfile.mkdtemp(prefix="sajson_")
                sa_path = os.path.join(tmpdir, "service_account.json")
                with open(sa_path, 'w') as f:
                    f.write(sa_json_content)
            except Exception as e:
                app.logger.error(f"Error saving service account JSON: {e}")
                return jsonify({"success": False, "message": f"Error processing service account JSON: {str(e)}"}), 400
        
        # Run agent sequence
        result = run_agent_sequence(
            openai_api_key=data['openai_api_key'],
            phantom_api_key=data['phantom_api_key'],
            firecrawl_api_key=data['firecrawl_api_key'],
            session_cookie=data['session_cookie'],
            user_agent=data['user_agent'],
            user_profile_url=data['user_profile_url'],
            style_profile_url=style_profile_url,
            debug=True
        )
        
        if result.get('success'):
            result['sa_path'] = sa_path  # Store path for later use
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        app.logger.exception("LinkedIn agent failed")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/linkedin/generate-post', methods=['POST'])
def linkedin_generate_post():
    """Generate a LinkedIn post with streaming support"""
    try:
        data = request.get_json()
        
        required_fields = ['openai_api_key', 'topic', 'style_notes']
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            return jsonify({"success": False, "message": f"Missing required fields: {', '.join(missing)}"}), 400
        
        # If manual topic is provided, use it directly without fetching trends
        topic = data.get('topic', '').strip()
        manual_topic = data.get('manual_topic', '').strip()
        
        if manual_topic:
            # Use manual topic directly - don't fetch trends
            # This ensures the post focuses exactly on what the user typed
            topic = manual_topic
            app.logger.info(f"Using manual topic directly (no trend fetching): {topic}")
        elif not topic:
            return jsonify({"success": False, "message": "Topic is required"}), 400
        
        # Check if streaming is requested
        stream = data.get('stream', False)
        
        if stream:
            # Return streaming response
            from openai import OpenAI
            
            client = OpenAI(api_key=data['openai_api_key'])
            
            sys_prompt = (
                "You are a LinkedIn copywriter. Write a polished LinkedIn post about the given topic "
                "and do NOT introduce unrelated topics. Focus only on the provided topic. "
                "If other keywords are provided, ignore them and write only about the topic. "
                "Start with a strong hook. Use two or three short paragraphs, each with a single clear idea. "
                "Include a simple call to action near the end. Finish with six to ten relevant hashtags on a separate line. "
                "Keep the entire post under about 1300 characters."
            )
            user_content = (
                f"Topic: {topic}\n\n"
                f"Style guidance:\n{data['style_notes'] or 'Neutral professional tone with clear structure and no specific constraints.'}\n\n"
                "Note: Do NOT use any user interest keywords or other profile keywords. Write only about the topic above."
            )
            
            def generate():
                try:
                    stream_response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        temperature=0.6,
                        stream=True
                    )
                    
                    for chunk in stream_response:
                        try:
                            if chunk.choices[0].delta.content:
                                yield f"data: {json.dumps({'chunk': chunk.choices[0].delta.content})}\n\n"
                        except GeneratorExit:
                            # Client disconnected, stop streaming
                            return
                        except Exception as e:
                            # Log chunk processing errors but continue
                            app.logger.warning(f"Error processing chunk: {e}")
                    
                    yield f"data: {json.dumps({'done': True})}\n\n"
                except GeneratorExit:
                    # Normal exception when stream is closed by client
                    # Don't log this as an error, just return
                    return
                except Exception as e:
                    # Log other exceptions and try to send error to client
                    app.logger.error(f"Error in post generation stream: {e}")
                    try:
                        yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    except (GeneratorExit, RuntimeError):
                        # Generator was closed or connection lost
                        return
            
            return Response(stream_with_context(generate()), mimetype='text/event-stream')
        else:
            # Generate post (non-streaming)
            post = generate_linkedin_post(
                openai_key=data['openai_api_key'],
                topic=topic,
                style_notes=data['style_notes'],
                keywords=data.get('keywords', [])
            )
            
            # Track activity
            user_id = data.get('user_id')
            if user_id:
                track_activity(
                    user_id=user_id,
                    activity_type='content_generation',
                    activity_subtype='linkedin_post',
                    metadata={'topic': topic[:100] if topic else None}
                )
            
            return jsonify({"success": True, "post": post}), 200
        
    except Exception as e:
        app.logger.exception("Post generation failed")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/linkedin/fetch-trends', methods=['POST'])
def linkedin_fetch_trends():
    """Fetch trends using Firecrawl"""
    try:
        data = request.get_json()
        
        required_fields = ['firecrawl_api_key', 'openai_api_key']
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            return jsonify({"success": False, "message": f"Missing required fields: {', '.join(missing)}"}), 400
        
        trends = fetch_trends_firecrawl(
            firecrawl_api_key=data['firecrawl_api_key'],
            openai_api_key=data['openai_api_key'],
            keywords=data.get('keywords', []),
            topic=data.get('topic')
        )
        
        return jsonify({
            "success": True,
            "trends": [item.model_dump() for item in trends]
        }), 200
        
    except Exception as e:
        app.logger.exception("Trend fetching failed")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/linkedin/save-to-sheet', methods=['POST'])
def linkedin_save_to_sheet():
    """Save post to Google Sheet"""
    try:
        data = request.get_json()
        
        required_fields = ['sheet_url', 'content', 'service_account_json']
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            return jsonify({"success": False, "message": f"Missing required fields: {', '.join(missing)}"}), 400
        
        # Save service account JSON to temp file
        import base64
        sa_json_content = data['service_account_json']
        if isinstance(sa_json_content, str) and sa_json_content.startswith('data:'):
            sa_json_content = base64.b64decode(sa_json_content.split(',')[1]).decode('utf-8')
        elif isinstance(sa_json_content, dict):
            import json as json_lib
            sa_json_content = json_lib.dumps(sa_json_content)
        
        tmpdir = tempfile.mkdtemp(prefix="sajson_")
        sa_path = os.path.join(tmpdir, "service_account.json")
        with open(sa_path, 'w') as f:
            f.write(sa_json_content)
        
        # Save to sheet
        ws_id, row_count = save_post_to_google_sheet(
            sheet_url=data['sheet_url'],
            content=data['content'],
            service_account_json_path=sa_path
        )
        
        # Cleanup
        try:
            shutil.rmtree(tmpdir)
        except:
            pass
        
        return jsonify({
            "success": True,
            "worksheet_id": ws_id,
            "row_count": row_count,
            "message": "post saved"
        }), 200
        
    except Exception as e:
        app.logger.exception("Save to sheet failed")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/linkedin/autopost', methods=['POST'])
def linkedin_autopost():
    """Trigger PhantomBuster autopost"""
    try:
        data = request.get_json()
        
        required_fields = ['phantom_api_key', 'session_cookie', 'user_agent', 'sheet_url']
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            return jsonify({"success": False, "message": f"Missing required fields: {', '.join(missing)}"}), 400
        
        result = trigger_phantombuster_autopost(
            phantom_api_key=data['phantom_api_key'],
            session_cookie=data['session_cookie'],
            user_agent=data['user_agent'],
            sheet_url=data['sheet_url'],
            number_of_posts_per_launch=data.get('number_of_posts_per_launch', 1)
        )
        
        # Track LinkedIn post activity - track if we successfully called PhantomBuster
        # (the actual posting happens asynchronously, but we've successfully scheduled it)
        user_id = data.get('user_id')
        app.logger.info(f"Autopost request - user_id: {user_id}, type: {type(user_id)}")
        
        if user_id:
            try:
                # Convert user_id to int if it's a string
                user_id_int = int(user_id) if isinstance(user_id, str) else user_id
                track_activity(
                    user_id=user_id_int,
                    activity_type='linkedin_post',
                    activity_subtype='posted',
                    metadata={
                        'sheet_url': data['sheet_url'],
                        'number_of_posts': data.get('number_of_posts_per_launch', 1),
                        'phantom_result': result
                    }
                )
                app.logger.info(f"Successfully tracked LinkedIn post activity for user {user_id_int}")
            except Exception as e:
                app.logger.error(f"Failed to track LinkedIn post activity for user {user_id}: {e}", exc_info=True)
        else:
            app.logger.warning(f"No user_id provided in autopost request. Data keys: {list(data.keys())}")
        
        # Schedule sheet clearing after 10 minutes if requested
        if data.get('clear_sheet_after_post', False) and data.get('service_account_json'):
            try:
                import base64
                sa_json_content = data['service_account_json']
                if isinstance(sa_json_content, str) and sa_json_content.startswith('data:'):
                    sa_json_content = base64.b64decode(sa_json_content.split(',')[1]).decode('utf-8')
                elif isinstance(sa_json_content, dict):
                    import json as json_lib
                    sa_json_content = json_lib.dumps(sa_json_content)
                
                # Save service account JSON to a persistent temp file for delayed clearing
                tmpdir = tempfile.mkdtemp(prefix="sajson_delayed_")
                sa_path = os.path.join(tmpdir, "service_account.json")
                with open(sa_path, 'w') as f:
                    f.write(sa_json_content)
                
                # Schedule clearing after 10 minutes (600 seconds)
                def delayed_clear_sheet():
                    try:
                        app.logger.info(f"Scheduled sheet clearing for {data['sheet_url']} after 10 minutes")
                        time.sleep(600)  # Wait 10 minutes
                        clear_google_sheet(
                            sheet_url=data['sheet_url'],
                            service_account_json_path=sa_path
                        )
                        app.logger.info(f"Sheet cleared successfully after 10 minutes: {data['sheet_url']}")
                        # Cleanup temp directory after clearing
                        try:
                            shutil.rmtree(tmpdir)
                        except:
                            pass
                    except Exception as e:
                        app.logger.error(f"Failed to clear sheet after 10 minutes: {e}")
                        # Cleanup on error
                        try:
                            shutil.rmtree(tmpdir)
                        except:
                            pass
                
                # Start background thread for delayed clearing
                clear_thread = threading.Thread(target=delayed_clear_sheet, daemon=True)
                clear_thread.start()
                app.logger.info(f"Scheduled sheet clearing in 10 minutes for {data['sheet_url']}")
                
            except Exception as e:
                app.logger.warning(f"Failed to schedule sheet clearing: {e}")
        
        return jsonify({"success": True, "autopost_response": result}), 200
        
    except Exception as e:
        app.logger.exception("Autopost failed")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/linkedin/clear-sheet', methods=['POST'])
def linkedin_clear_sheet():
    """Clear all data from Google Sheet"""
    try:
        data = request.get_json()
        
        required_fields = ['sheet_url', 'service_account_json']
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            return jsonify({"success": False, "message": f"Missing required fields: {', '.join(missing)}"}), 400
        
        # Save service account JSON to temp file
        import base64
        sa_json_content = data['service_account_json']
        if isinstance(sa_json_content, str) and sa_json_content.startswith('data:'):
            sa_json_content = base64.b64decode(sa_json_content.split(',')[1]).decode('utf-8')
        elif isinstance(sa_json_content, dict):
            import json as json_lib
            sa_json_content = json_lib.dumps(sa_json_content)
        
        tmpdir = tempfile.mkdtemp(prefix="sajson_")
        sa_path = os.path.join(tmpdir, "service_account.json")
        with open(sa_path, 'w') as f:
            f.write(sa_json_content)
        
        # Clear sheet
        clear_google_sheet(
            sheet_url=data['sheet_url'],
            service_account_json_path=sa_path
        )
        
        # Cleanup
        try:
            shutil.rmtree(tmpdir)
        except:
            pass
        
        return jsonify({
            "success": True,
            "message": "Sheet cleared successfully"
        }), 200
        
    except Exception as e:
        app.logger.exception("Clear sheet failed")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/linkedin/service-account-file', methods=['GET'])
def linkedin_service_account_file():
    """Serve the default service account JSON file"""
    try:
        # First, try to read from environment variable (for Azure deployment)
        google_creds_env = os.getenv('GOOGLE_CREDENTIALS_JSON')
        if google_creds_env:
            try:
                import base64
                # Decode base64 if needed
                if google_creds_env.startswith('data:'):
                    content = base64.b64decode(google_creds_env.split(',')[1]).decode('utf-8')
                else:
                    # Try to decode as base64, if it fails, use as-is
                    try:
                        content = base64.b64decode(google_creds_env).decode('utf-8')
                    except:
                        content = google_creds_env
                app.logger.info("Found service account JSON in environment variable")
                return content, 200, {'Content-Type': 'application/json'}
            except Exception as e:
                app.logger.warning(f"Failed to decode GOOGLE_CREDENTIALS_JSON: {e}")
        
        # Try multiple possible paths (for local development)
        possible_paths = [
            # In Docker container (copied to /app)
            Path(__file__).parent / 'linkedin-agent-478216-f37f2b2ce601.json',
            # Project root (for local development)
            Path(__file__).parent.parent / 'linkedin-agent-478216-f37f2b2ce601.json',
            # Alternative project root
            Path(__file__).parent.parent.parent / 'linkedin-agent-478216-f37f2b2ce601.json',
        ]
        
        for sa_file_path in possible_paths:
            if sa_file_path.exists():
                app.logger.info(f"Found service account file at: {sa_file_path}")
                with open(sa_file_path, 'r') as f:
                    content = f.read()
                return content, 200, {'Content-Type': 'application/json'}
        
        # If not found, log all attempted paths
        app.logger.warning(f"Service account file not found. Checked paths: {possible_paths}")
        return jsonify({"error": f"Service account file not found. Checked: {possible_paths}"}), 404
    except Exception as e:
        app.logger.exception("Error serving service account file")
        return jsonify({"error": str(e)}), 500


@app.route('/api/content/generate', methods=['POST'])
def api_generate_content():
    """
    Generate social content + associated image data via OpenAI.
    Payload expects brand_summary, campaign_goal, target_audience, platforms (list).
    """
    is_multipart = request.content_type and 'multipart/form-data' in request.content_type.lower()
    if is_multipart:
        payload = request.form.to_dict()
    else:
        payload = request.get_json(silent=True) or {}

    logo_file = request.files.get('logo_file') if request.files else None
    reference_image_file = request.files.get('reference_image') if request.files else None
    
    # Debug logging
    if reference_image_file:
        app.logger.info(f"Reference image file received in request: {reference_image_file.filename}")
    else:
        app.logger.info("No reference image file in request")

    platforms = _parse_platforms(payload.get('platforms'))
    required_fields = ['brand_summary', 'campaign_goal', 'target_audience']
    missing = [field for field in required_fields if not (payload.get(field) and str(payload.get(field)).strip())]
    if not platforms:
        missing.append('platforms')

    if missing:
        return jsonify({"success": False, "message": f"Missing required fields: {', '.join(missing)}"}), 400

    size_overrides = _parse_size_overrides(payload.get('platform_image_sizes'))
    logo_position = (payload.get('logo_position') or DEFAULT_LOGO_POSITION).lower()
    logo_scale = _safe_float(payload.get('logo_scale'), DEFAULT_LOGO_SCALE)
    image_size = payload.get('image_size') or os.getenv('OPENAI_IMAGE_SIZE', '1024x1024')

    logo_bytes = None
    if logo_file:
        logo_bytes = logo_file.read()
        if len(logo_bytes) > MAX_LOGO_UPLOAD_BYTES:
            return jsonify({"success": False, "message": "Logo file too large. Max 5MB."}), 400

    reference_image_bytes = None
    reference_image_name = None
    if reference_image_file:
        reference_image_bytes = reference_image_file.read()
        app.logger.info(f"Reference image received: {len(reference_image_bytes)} bytes, filename: {reference_image_file.filename}")
        if len(reference_image_bytes) > MAX_REFERENCE_IMAGE_BYTES:
            return jsonify({"success": False, "message": "Reference image too large. Max 10MB."}), 400
        if len(reference_image_bytes) == 0:
            app.logger.warning("Reference image file is empty, ignoring it")
            reference_image_bytes = None
        else:
            reference_image_name = reference_image_file.filename or "reference.png"

    proposal_context = payload.get('proposal_context')
    if isinstance(proposal_context, str):
        try:
            proposal_context = json.loads(proposal_context)
        except json.JSONDecodeError:
            proposal_context = None

    outputs = payload.get('outputs')
    if isinstance(outputs, str):
        try:
            outputs = json.loads(outputs)
        except json.JSONDecodeError:
            outputs = []
    if not isinstance(outputs, list):
        outputs = []

    try:
        num_posts = int(payload.get('num_posts_per_platform', 3))
    except (TypeError, ValueError):
        num_posts = 3

    try:
        plan = generate_social_content_and_images(
            brand_summary=payload['brand_summary'],
            campaign_goal=payload['campaign_goal'],
            target_audience=payload['target_audience'],
            platforms=platforms,
            num_posts_per_platform=num_posts,
            extra_instructions=payload.get('extra_instructions', ''),
            proposal_context=proposal_context,
            outputs=outputs,
            image_size=image_size,
            platform_image_sizes=size_overrides,
            logo_bytes=logo_bytes,
            logo_position=logo_position,
            logo_scale=logo_scale,
            reference_image_bytes=reference_image_bytes,
            reference_image_name=reference_image_name,
        )
        
        # Track activity
        user_id = payload.get('user_id')
        if user_id:
            total_posts = sum(len(p.get('posts', [])) for p in plan.get('platforms', []))
            track_activity(
                user_id=user_id,
                activity_type='content_generation',
                activity_subtype='social_content',
                metadata={
                    'platforms': platforms,
                    'num_posts': total_posts,
                    'num_platforms': len(platforms)
                }
            )
    except ValueError as err:
        return jsonify({"success": False, "message": str(err), "supported_platforms": SUPPORTED_PLATFORMS}), 400
    except RuntimeError as err:
        return jsonify({"success": False, "message": str(err)}), 500
    except Exception as err:
        app.logger.exception("Content generation failed")
        return jsonify({"success": False, "message": "Content generation failed."}), 500

    return jsonify({"success": True, "plan": plan}), 200

@app.route('/api/proposal/generate', methods=['POST'])
def api_generate_proposal_content():
    """
    Generate proposal-based social content + associated image data via OpenAI.
    Similar to content generation but with proposal context and narrative.
    Payload expects brand_summary, campaign_goal, target_audience, platforms (list),
    proposal_narrative (optional), and proposal_context (optional).
    """
    try:
        app.logger.info("=== PROPOSAL GENERATION REQUEST START ===")
        app.logger.info(f"Content-Type: {request.content_type}")
        
        is_multipart = request.content_type and 'multipart/form-data' in request.content_type.lower()
        app.logger.info(f"Is multipart: {is_multipart}")
        
        if is_multipart:
            payload = request.form.to_dict()
            app.logger.info(f"Form data keys: {list(payload.keys())}")
        else:
            payload = request.get_json(silent=True) or {}
            app.logger.info(f"JSON payload keys: {list(payload.keys())}")
        
        app.logger.info(f"Payload: {json.dumps(payload, indent=2, default=str)}")

        logo_file = request.files.get('logo_file') if request.files else None
        reference_image_file = request.files.get('reference_image') if request.files else None
        app.logger.info(f"Logo file: {logo_file.filename if logo_file else None}")
        app.logger.info(f"Reference image file: {reference_image_file.filename if reference_image_file else None}")

        platforms = _parse_platforms(payload.get('platforms'))
        app.logger.info(f"Parsed platforms: {platforms}")
        
        required_fields = ['brand_summary', 'campaign_goal', 'target_audience']
        missing = [field for field in required_fields if not (payload.get(field) and str(payload.get(field)).strip())]
        if not platforms:
            missing.append('platforms')

        if missing:
            app.logger.error(f"Missing required fields: {missing}")
            return jsonify({"success": False, "message": f"Missing required fields: {', '.join(missing)}"}), 400

        size_overrides = _parse_size_overrides(payload.get('platform_image_sizes'))
        logo_position = (payload.get('logo_position') or DEFAULT_LOGO_POSITION).lower()
        logo_scale = _safe_float(payload.get('logo_scale'), DEFAULT_LOGO_SCALE)
        image_size = payload.get('image_size') or os.getenv('OPENAI_IMAGE_SIZE', '1024x1024')

        logo_bytes = None
        if logo_file:
            logo_bytes = logo_file.read()
            if len(logo_bytes) > MAX_LOGO_UPLOAD_BYTES:
                return jsonify({"success": False, "message": "Logo file too large. Max 5MB."}), 400

        reference_image_bytes = None
        reference_image_name = None
        if reference_image_file:
            reference_image_bytes = reference_image_file.read()
            if len(reference_image_bytes) > MAX_REFERENCE_IMAGE_BYTES:
                return jsonify({"success": False, "message": "Reference image too large. Max 10MB."}), 400
            if len(reference_image_bytes) == 0:
                reference_image_bytes = None
            else:
                reference_image_name = reference_image_file.filename or "reference.png"

        # Parse proposal context
        proposal_context = payload.get('proposal_context')
        app.logger.info(f"Raw proposal_context type: {type(proposal_context)}")
        if isinstance(proposal_context, str):
            try:
                proposal_context = json.loads(proposal_context)
                app.logger.info(f"Parsed proposal_context from JSON string")
            except json.JSONDecodeError as e:
                app.logger.warning(f"Failed to parse proposal_context JSON: {e}")
                proposal_context = None
        if proposal_context and not isinstance(proposal_context, dict):
            app.logger.warning(f"proposal_context is not a dict: {type(proposal_context)}")
            proposal_context = None
        app.logger.info(f"Final proposal_context: {json.dumps(proposal_context, indent=2, default=str) if proposal_context else None}")

        # Get proposal narrative (similar to ad_text in content studio)
        proposal_narrative = payload.get('proposal_narrative', '').strip()
        app.logger.info(f"proposal_narrative from payload: {proposal_narrative[:100] if proposal_narrative else None}")
        if not proposal_narrative:
            # Fallback to ad_text if proposal_narrative not provided
            proposal_narrative = payload.get('ad_text', '').strip()
            app.logger.info(f"Using ad_text as proposal_narrative: {proposal_narrative[:100] if proposal_narrative else None}")

        outputs = payload.get('outputs')
        app.logger.info(f"Raw outputs: {outputs}, type: {type(outputs)}")
        if isinstance(outputs, str):
            try:
                outputs = json.loads(outputs)
                app.logger.info(f"Parsed outputs from JSON string: {outputs}")
            except json.JSONDecodeError as e:
                app.logger.warning(f"Failed to parse outputs JSON: {e}")
                outputs = []
        if not isinstance(outputs, list):
            app.logger.warning(f"outputs is not a list: {type(outputs)}, setting to []")
            outputs = []
        app.logger.info(f"Final outputs: {outputs}")

        try:
            num_posts = int(payload.get('num_posts_per_platform', 3))
        except (TypeError, ValueError) as e:
            app.logger.warning(f"Failed to parse num_posts_per_platform: {e}, using default 3")
            num_posts = 3
        app.logger.info(f"num_posts_per_platform: {num_posts}")

        app.logger.info("Calling generate_proposal_content_and_images...")
        try:
            plan = generate_proposal_content_and_images(
                brand_summary=payload['brand_summary'],
                campaign_goal=payload['campaign_goal'],
                target_audience=payload['target_audience'],
                platforms=platforms,
                proposal_narrative=proposal_narrative,
                proposal_context=proposal_context,
                num_posts_per_platform=num_posts,
                extra_instructions=payload.get('extra_instructions', ''),
                outputs=outputs,
                image_size=image_size,
                platform_image_sizes=size_overrides,
                logo_bytes=logo_bytes,
                logo_position=logo_position,
                logo_scale=logo_scale,
                reference_image_bytes=reference_image_bytes,
                reference_image_name=reference_image_name,
            )
            app.logger.info("generate_proposal_content_and_images completed successfully")
            app.logger.info(f"Plan structure: platforms={len(plan.get('platforms', []))}")
            if plan.get('platforms'):
                first_platform = plan['platforms'][0]
                app.logger.info(f"First platform: {first_platform.get('name')}, posts: {len(first_platform.get('posts', []))}")
            
            # Track activity
            user_id = payload.get('user_id')
            if user_id:
                total_posts = sum(len(p.get('posts', [])) for p in plan.get('platforms', []))
                track_activity(
                    user_id=user_id,
                    activity_type='content_generation',
                    activity_subtype='proposal_content',
                    metadata={
                        'platforms': platforms,
                        'num_posts': total_posts,
                        'num_platforms': len(platforms)
                    }
                )
        except ValueError as err:
            app.logger.error(f"ValueError in proposal generation: {str(err)}")
            return jsonify({"success": False, "message": str(err), "supported_platforms": SUPPORTED_PLATFORMS}), 400
        except RuntimeError as err:
            app.logger.error(f"RuntimeError in proposal generation: {str(err)}")
            return jsonify({"success": False, "message": str(err)}), 500
        except Exception as err:
            app.logger.exception("Proposal content generation failed")
            return jsonify({"success": False, "message": f"Proposal content generation failed: {str(err)}"}), 500

        app.logger.info("=== PROPOSAL GENERATION REQUEST SUCCESS ===")
        return jsonify({"success": True, "plan": plan}), 200
    except Exception as outer_err:
        app.logger.exception("Unexpected error in api_generate_proposal_content")
        return jsonify({"success": False, "message": f"Unexpected error: {str(outer_err)}"}), 500

@app.route('/api/gap/keywords', methods=['GET'])
def gap_keywords():
    user_id = request.args.get('user_id')
    if not user_id:
        payload = request.get_json(silent=True) or {}
        user_id = payload.get('user_id')
    if not user_id:
        return jsonify({"success": False, "message": "user_id is required"}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, keyword, category, importance
            FROM user_keywords
            WHERE user_id=%s
            ORDER BY COALESCE(importance, 0) DESC, keyword ASC
            """,
            (user_id,)
        )
        rows = cursor.fetchall()
        return jsonify({"success": True, "keywords": rows}), 200
    except mysql.connector.Error as db_err:
        if db_err.errno == 1146:  # table missing
            app.logger.warning("user_keywords table missing; returning defaults")
            return jsonify({"success": True, "keywords": DEFAULT_GAP_KEYWORDS}), 200
        app.logger.exception("Failed to load gap keywords (db)")
        return jsonify({"success": False, "message": str(db_err)}), 500
    except Exception as err:
        app.logger.exception("Failed to load gap keywords")
        return jsonify({"success": False, "message": str(err)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


@app.route('/api/gap/businesses', methods=['GET'])
def gap_businesses():
    user_id = request.args.get('user_id')
    if not user_id:
        payload = request.get_json(silent=True) or {}
        user_id = payload.get('user_id')
    if not user_id:
        return jsonify({"success": False, "message": "user_id is required"}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404

        cursor.execute(
            """
            SELECT business_name, business_strapline, business_audience,
                   product_name, product_description, pricing, product_keywords
            FROM user_products
            WHERE user_id=%s
            ORDER BY business_name, product_name
            """,
            (user_id,)
        )
        rows = cursor.fetchall()
        default_business = user.get('company') or user.get('full_name') or 'My Business'
        default_audience = user.get('industry') or 'General audience'
        default_strapline = user.get('marketing_goals') or f"{default_business} catalog"
        businesses = {}

        for row in rows:
            name = row.get('business_name') or default_business
            biz = businesses.setdefault(
                name,
                {
                    "name": name,
                    "strapline": row.get('business_strapline') or default_strapline,
                    "audience": row.get('business_audience') or default_audience,
                    "products": [],
                },
            )
            if not biz.get('strapline'):
                biz['strapline'] = row.get('business_strapline') or default_strapline
            if not biz.get('audience'):
                biz['audience'] = row.get('business_audience') or default_audience
            biz['products'].append(
                {
                    "name": row.get('product_name') or 'Unnamed Product',
                    "description": row.get('product_description') or '',
                    "pricing": row.get('pricing') or '',
                    "keywords": _parse_keywords_blob(row.get('product_keywords')),
                }
            )

        business_list = list(businesses.values())
        total_products = sum(len(biz['products']) for biz in business_list)

        return jsonify({
            "success": True,
            "businesses": business_list,
            "meta": {
                "total_businesses": len(business_list),
                "total_products": total_products,
            },
        }), 200
    except mysql.connector.Error as db_err:
        if db_err.errno == 1146:
            app.logger.warning("user_products table missing; returning defaults")
            return jsonify({
                "success": True,
                "businesses": DEFAULT_GAP_BUSINESSES,
                "meta": {
                    "total_businesses": len(DEFAULT_GAP_BUSINESSES),
                    "total_products": sum(len(biz["products"]) for biz in DEFAULT_GAP_BUSINESSES),
                },
            }), 200
        app.logger.exception("Failed to load business catalog (db)")
        return jsonify({"success": False, "message": str(db_err)}), 500
    except Exception as err:
        app.logger.exception("Failed to load business catalog")
        return jsonify({"success": False, "message": str(err)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass

@app.route('/api/gap/trends', methods=['POST'])
def gap_trends():
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    keywords = data.get('keywords') or []
    keyword_ids = data.get('keyword_ids') or []


    keywords = [kw.strip() for kw in keywords if isinstance(kw, str) and kw.strip()]
    if not keywords:
        return jsonify({"success": False, "message": "Select at least one keyword"}), 400

    try:
        final_output = generate_trends_from_keywords(keywords)
    except RuntimeError as err:
        return jsonify({"success": False, "message": str(err)}), 500
    except Exception as err:
        app.logger.exception("Trend generation failed")
        return jsonify({"success": False, "message": "Trend generation failed."}), 500

    return jsonify(final_output), 200


@app.route('/api/gap-analysis', methods=['POST'])
def api_gap_analysis():
    payload = request.get_json(silent=True) or {}
    businesses = payload.get('businesses')
    trends = payload.get('trends')
    if not isinstance(businesses, list) or not businesses:
        return jsonify({"success": False, "message": "Provide businesses as a non-empty list."}), 400
    if not isinstance(trends, list) or not trends:
        return jsonify({"success": False, "message": "Provide trends as a non-empty list."}), 400
 
    try:
        analysis = run_gap_analysis(
            businesses=businesses,
            trends=trends,
            additional_context=payload.get('context', ''),
            generate_product_proposals=bool(payload.get('generate_proposals')),
        )
        
        # Track activity
        user_id = payload.get('user_id')
        if user_id:
            track_activity(
                user_id=user_id,
                activity_type='gap_analysis',
                activity_subtype='analysis_run',
                metadata={
                    'num_businesses': len(businesses),
                    'num_trends': len(trends),
                    'generate_proposals': bool(payload.get('generate_proposals'))
                }
            )
    except ValueError as err:
        return jsonify({"success": False, "message": str(err)}), 400
    except RuntimeError as err:
        return jsonify({"success": False, "message": str(err)}), 500
    except Exception as err:
        app.logger.exception("Gap analysis failed")
        return jsonify({"success": False, "message": "Gap analysis failed."}), 500
 
    return jsonify({"success": True, "analysis": analysis}), 200

# ----------------------------- WEBSITES -----------------------------
@app.route('/user-has-data/<int:user_id>', methods=['GET'])
def api_user_has_data(user_id):
    """
    API endpoint to check if a user already has website data.
    Returns JSON: {"user_id": ..., "has_data": True/False}
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT 1 FROM websites WHERE user_id = %s LIMIT 1"
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()
        has_data = result is not None

        return jsonify({"user_id": user_id, "has_data": has_data}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

# save website data
@app.route('/save-website-data', methods=['POST'])
def save_website_data():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        extracted = data.get("extracted")

        if not user_id or not extracted:
            return jsonify({"success": False, "message": "Missing user_id or extracted data"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert into websites WITHOUT RETURNING
        insert_query = """
            INSERT INTO websites (
                user_id, domain, company_name, industry, company_mission,
                location, target_market, primary_keywords, secondary_keywords,
                trending_topics, industry_terms, target_audience,
                value_propositions, content_themes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(insert_query, (
            user_id,
            extracted.get("domain"),
            extracted.get("company_name"),
            extracted.get("industry"),
            extracted.get("company_mission"),
            extracted.get("location"),
            json.dumps(extracted.get("target_market") or []),
            json.dumps(extracted.get("primary_keywords") or []),
            json.dumps(extracted.get("secondary_keywords") or []),
            json.dumps(extracted.get("trending_topics") or []),
            json.dumps(extracted.get("industry_terms") or []),
            extracted.get("target_audience"),
            json.dumps(extracted.get("value_propositions") or []),
            json.dumps(extracted.get("content_themes") or [])
        ))

        # MySQL way to get inserted ID
        website_id = cursor.lastrowid

        # Insert products
        product_insert_query = """
            INSERT INTO products (
                website_id, category, name, description,
                features, pricing, keywords
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        for category, products in extracted.get("products_by_category", {}).items():
            for product in products:
                cursor.execute(product_insert_query, (
                    website_id,
                    category,
                    product.get("name"),
                    product.get("description"),
                    json.dumps(product.get("features") or []),
                    product.get("pricing"),
                    json.dumps(product.get("keywords") or [])
                ))

        conn.commit()

        return jsonify({
            "success": True,
            "message": "Website data stored successfully",
            "website_id": website_id
        }), 201

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

# update trend_keywords for a specific website
@app.route('/update-trend-keywords/<int:website_id>', methods=['PUT'])
def update_trend_keywords(website_id):
    """Update trend_keywords for a specific website"""
    try:
        data = request.get_json()
        trend_keywords = data.get('trend_keywords', [])
        
        # Validate that trend_keywords is a list
        if not isinstance(trend_keywords, list):
            return jsonify({"success": False, "message": "trend_keywords must be a list"}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if website exists
        cursor.execute("SELECT id FROM websites WHERE id = %s", (website_id,))
        if not cursor.fetchone():
            return jsonify({"success": False, "message": "Website not found"}), 404
        
        # Update trend_keywords
        cursor.execute(
            "UPDATE websites SET trend_keywords = %s WHERE id = %s",
            (json.dumps(trend_keywords), website_id)
        )
        
        conn.commit()
        
        return jsonify({
            "success": True,
            "message": "Trend keywords updated successfully",
            "website_id": website_id,
            "trend_keywords": trend_keywords
        }), 200
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

# get all websites for a user WITHOUT products
@app.route('/get-websites/<int:user_id>', methods=['GET'])
def get_websites(user_id):
    """Get all websites for a user WITHOUT products"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT 
                id, domain, company_name, industry, company_mission,
                location, target_market, primary_keywords, secondary_keywords,
                trending_topics, industry_terms, target_audience,
                value_propositions, content_themes, created_at
            FROM websites
            WHERE user_id = %s
            ORDER BY created_at DESC
        """
        
        cursor.execute(query, (user_id,))
        websites = cursor.fetchall()
        
        # Parse JSON fields
        for site in websites:
            for field in ['target_market', 'primary_keywords', 'secondary_keywords', 
                         'trending_topics', 'industry_terms', 'value_propositions', 'content_themes']:
                if site.get(field):
                    site[field] = json.loads(site[field])
        
        return jsonify({
            "success": True,
            "count": len(websites),
            "data": websites
        }), 200
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

# get trend_keywords for a specific users
@app.route('/get-trend-keywords-by-user/<int:user_id>', methods=['GET'])
def get_trend_keywords_by_user(user_id):
    """Get trend_keywords for all websites owned by a specific user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT id AS website_id, domain, trend_keywords FROM websites WHERE user_id = %s",
            (user_id,)
        )

        websites = cursor.fetchall()

        if not websites:
            return jsonify({"success": False, "message": "No websites found for this user"}), 404

        # Parse JSON fields
        for site in websites:
            if site.get('trend_keywords'):
                site['trend_keywords'] = json.loads(site['trend_keywords'])
            else:
                site['trend_keywords'] = []

        return jsonify({
            "success": True,
            "data": websites
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

@app.route('/get-trend-keywords-list/<int:user_id>', methods=['GET'])
def get_trend_keywords_by_user_list(user_id):
    """Return trend_keywords in the same format as /api/gap/keywords"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT id AS website_id, domain, trend_keywords FROM websites WHERE user_id = %s",
            (user_id,)
        )
        websites = cursor.fetchall()

        if not websites:
            # Still return success:true and empty list (same pattern)
            return jsonify({"success": True, "keywords": []}), 200

        keywords_output = []
        for site in websites:
            trend_keywords = site["trend_keywords"]
            if trend_keywords:
                trend_keywords = json.loads(trend_keywords)
            else:
                trend_keywords = []

            keywords_output.append({
                "website_id": site["website_id"],
                "domain": site["domain"],
                "trend_keywords": trend_keywords
            })

        return jsonify({
            "success": True,
            "keywords": keywords_output
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass


# return all websites for a user WITH products grouped by category
@app.route('/get-websites-with-products/<int:user_id>', methods=['GET'])
def get_websites_with_products(user_id):
    """Get all websites for a user WITH products grouped by category"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get websites
        website_query = """
            SELECT 
                id, domain, company_name, industry, company_mission,
                location, target_market, primary_keywords, secondary_keywords,
                trending_topics, industry_terms, target_audience,
                value_propositions, content_themes, created_at
            FROM websites
            WHERE user_id = %s
            ORDER BY created_at DESC
        """
        
        cursor.execute(website_query, (user_id,))
        websites = cursor.fetchall()
        
        # Get products for each website
        product_query = """
            SELECT 
                category, name, description, features, pricing, keywords
            FROM products
            WHERE website_id = %s
            ORDER BY category, name
        """
        
        for site in websites:
            # Parse JSON fields
            for field in ['target_market', 'primary_keywords', 'secondary_keywords', 
                         'trending_topics', 'industry_terms', 'value_propositions', 'content_themes']:
                if site.get(field):
                    site[field] = json.loads(site[field])
            
            # Get products for this website
            cursor.execute(product_query, (site['id'],))
            products = cursor.fetchall()
            
            # Parse product JSON fields and group by category
            products_by_category = {}
            for product in products:
                if product.get('features'):
                    product['features'] = json.loads(product['features'])
                if product.get('keywords'):
                    product['keywords'] = json.loads(product['keywords'])
                
                category = product.get('category', 'Uncategorized')
                if category not in products_by_category:
                    products_by_category[category] = []
                
                products_by_category[category].append(product)
            
            site['products_by_category'] = products_by_category
        
        return jsonify({
            "success": True,
            "count": len(websites),
            "data": websites
        }), 200
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

# take user_id and return list of website IDs
def get_website_ids_by_user(user_id):
    """Return a list of website IDs for a given user_id."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM websites WHERE user_id = %s", (user_id,))
        rows = cursor.fetchall()
        website_ids = [row[0] for row in rows]
        return website_ids
    except Exception as e:
        app.logger.exception("Failed to fetch website IDs")
        return []
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass


@app.route('/upload-json', methods=['POST'])
def save_uploaded_json():
    """Save uploaded JSON data to the user_json_uploads table"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        json_data = data.get("json_data")
        print(json_data, flush=   True)

        if not user_id or not json_data:
            return jsonify({"success": False, "message": "Missing user_id or json_data"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Save JSON data to user_json_uploads table
        insert_query = """
            INSERT INTO user_json_uploads (user_id, json_data)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE json_data=%s, updated_at=CURRENT_TIMESTAMP
        """
        cursor.execute(insert_query, (user_id, json.dumps(json_data), json.dumps(json_data)))

        conn.commit()

        return jsonify({
            "success": True,
            "message": "JSON data stored successfully",
            "user_id": user_id
        }), 201

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass


@app.route('/get-json/<int:user_id>', methods=['GET'])
def get_uploaded_json(user_id):
    """Retrieve the uploaded JSON for a specific user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT json_data FROM user_json_uploads WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()

        if not row or not row[0]:
            return jsonify({"success": False, "message": "No JSON data found for this user"}), 404
        try:
            payload = json.loads(row[0])
        except Exception:
            payload = row[0]

        if isinstance(payload, dict) and "businesses" in payload:
            business_list = payload.get("businesses") or []
        else:
            business_list = payload if isinstance(payload, list) else []

        total_products = 0
        for biz in business_list:
            if isinstance(biz, dict):
                products = biz.get("products") or []
                total_products += len(products) if isinstance(products, list) else 0

        meta = {
            "total_businesses": len(business_list),
            "total_products": total_products,
        }
        return jsonify({"success": True, "businesses": business_list, "meta": meta})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

# ----------------------------- DASHBOARD API -----------------------------
@app.route('/api/dashboard/stats', methods=['GET'])
def dashboard_stats():
    """Get dashboard statistics for a user"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"success": False, "message": "user_id is required"}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get user info
        cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        # Get LinkedIn data
        cursor.execute(
            "SELECT keywords, tone_of_writing, updated_at FROM user_linkedin_data WHERE user_id=%s",
            (user_id,)
        )
        linkedin_data = cursor.fetchone()
        
        # Parse keywords
        keywords = []
        if linkedin_data and linkedin_data.get('keywords'):
            try:
                if isinstance(linkedin_data['keywords'], str):
                    keywords = json.loads(linkedin_data['keywords'])
                else:
                    keywords = linkedin_data['keywords']
            except:
                keywords = []
        
        # Get activity stats
        cursor.execute("""
            SELECT 
                activity_type,
                activity_subtype,
                COUNT(*) as count,
                DATE(created_at) as date
            FROM user_activities
            WHERE user_id = %s
            GROUP BY activity_type, activity_subtype, DATE(created_at)
            ORDER BY date DESC
            LIMIT 100
        """, (user_id,))
        activities = cursor.fetchall()
        
        # Calculate totals
        cursor.execute("""
            SELECT 
                activity_type,
                COUNT(*) as total_count
            FROM user_activities
            WHERE user_id = %s
            GROUP BY activity_type
        """, (user_id,))
        activity_totals = cursor.fetchall()
        
        # Get LinkedIn posts count
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM user_activities
            WHERE user_id = %s AND activity_type = 'linkedin_post' AND activity_subtype = 'posted'
        """, (user_id,))
        linkedin_posts_result = cursor.fetchone()
        linkedin_posts_count = linkedin_posts_result['count'] if linkedin_posts_result else 0
        
        # Get proposals count
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM user_activities
            WHERE user_id = %s AND activity_type = 'content_generation' AND activity_subtype = 'proposal_content'
        """, (user_id,))
        proposals_result = cursor.fetchone()
        proposals_count = proposals_result['count'] if proposals_result else 0
        
        # Get platform usage from metadata
        cursor.execute("""
            SELECT metadata
            FROM user_activities
            WHERE user_id = %s 
            AND activity_type = 'content_generation'
            AND metadata IS NOT NULL
        """, (user_id,))
        content_activities = cursor.fetchall()
        
        # Extract platforms from metadata
        platform_counts = {}
        for activity in content_activities:
            try:
                meta = json.loads(activity['metadata']) if isinstance(activity['metadata'], str) else activity['metadata']
                platforms = meta.get('platforms', [])
                for platform in platforms:
                    platform_counts[platform] = platform_counts.get(platform, 0) + 1
            except:
                pass
        
        # Get daily activity for last 7 days
        cursor.execute("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as count
            FROM user_activities
            WHERE user_id = %s
            AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        """, (user_id,))
        daily_activity = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Calculate profile completion
        profile_fields = ['full_name', 'email', 'company', 'job_title', 'linkedin', 'industry', 'marketing_goals']
        completed_fields = sum(1 for field in profile_fields if user.get(field))
        profile_completion = int((completed_fields / len(profile_fields)) * 100)
        
        # Build response
        stats = {
            'user': {
                'name': user.get('full_name'),
                'email': user.get('email'),
                'company': user.get('company'),
                'industry': user.get('industry'),
                'created_at': user.get('created_at').isoformat() if user.get('created_at') else None
            },
            'profile': {
                'completion': profile_completion,
                'linkedin_configured': bool(user.get('linkedin')),
                'keywords_count': len(keywords),
                'has_tone': bool(linkedin_data and linkedin_data.get('tone_of_writing')),
                'linkedin_updated_at': linkedin_data.get('updated_at').isoformat() if linkedin_data and linkedin_data.get('updated_at') else None
            },
            'activity': {
                'total_activities': sum(a['total_count'] for a in activity_totals),
                'by_type': {a['activity_type']: a['total_count'] for a in activity_totals},
                'platform_usage': platform_counts,
                'daily_activity': [
                    {
                        'date': str(d['date']),
                        'count': d['count']
                    } for d in daily_activity
                ],
                'linkedin_posts_count': linkedin_posts_count,
                'proposals_count': proposals_count
            },
            'keywords': keywords[:10]  # Top 10 keywords
        }
        
        return jsonify({"success": True, "stats": stats}), 200
        
    except Exception as e:
        app.logger.exception("Dashboard stats failed")
        return jsonify({"success": False, "message": str(e)}), 500

# ----------------------------- HEALTH CHECK -----------------------------
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Azure Container Apps"""
    try:
        # Check database connection
        conn = get_db_connection()
        conn.close()
        return jsonify({
            "status": "healthy",
            "service": "backend",
            "database": "connected"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "service": "backend",
            "error": str(e)
        }), 503

# ----------------------------- RUN APP -----------------------------
if __name__ == '__main__':
    # Database initialization is handled by docker-compose via schema.sql
    # Use production settings when FLASK_ENV is set to production
    debug_mode = os.getenv('FLASK_ENV', 'development') != 'production'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
