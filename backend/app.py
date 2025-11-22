from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import mysql.connector
import os
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from datetime import datetime
import tempfile
import shutil
from pathlib import Path
from dotenv import load_dotenv
import json
from linkedin_agent import (
    run_agent_sequence,
    generate_linkedin_post,
    fetch_trends_firecrawl,
    save_post_to_google_sheet,
    trigger_phantombuster_autopost,
    clear_google_sheet
)

# Load environment variables from .env file at project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend requests

DB_HOST = os.getenv('DB_HOST', 'db')  # 'db' matches the service name in docker-compose.yml
DB_PORT = os.getenv('DB_PORT', '3306')
DB_NAME = os.getenv('DB_NAME', 'Hackathon')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')

def get_db_connection():
    conn = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn



# ----------------------------- SIGNUP -----------------------------
@app.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json(silent=True) or request.form
        full_name = data.get('full_name')
        email = data.get('email')
        password = data.get('password')

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
                "redirect": "/account"
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
@app.route('/api/linkedin/run-agent', methods=['POST'])
def linkedin_run_agent():
    """Run the LinkedIn agent sequence"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['openai_api_key', 'phantom_api_key', 'firecrawl_api_key', 
                          'session_cookie', 'user_agent', 'user_profile_url']
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            return jsonify({"success": False, "message": f"Missing required fields: {', '.join(missing)}"}), 400
        
        # If style_profile_url is not provided, use user_profile_url as default
        style_profile_url = data.get('style_profile_url', '').strip()
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
        
        # If manual topic is provided, optionally refine trends first
        topic = data.get('topic', '').strip()
        manual_topic = data.get('manual_topic', '').strip()
        
        if manual_topic:
            # Optionally fetch refined trends for manual topic
            if data.get('firecrawl_api_key') and data.get('keywords'):
                try:
                    trends = fetch_trends_firecrawl(
                        firecrawl_api_key=data['firecrawl_api_key'],
                        openai_api_key=data['openai_api_key'],
                        keywords=data.get('keywords', []),
                        topic=manual_topic
                    )
                    if trends:
                        topic = trends[0].title if trends else manual_topic
                except Exception as e:
                    app.logger.warning(f"Error fetching trends for manual topic: {e}")
                    topic = manual_topic
            else:
                topic = manual_topic
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
                        if chunk.choices[0].delta.content:
                            yield f"data: {json.dumps({'chunk': chunk.choices[0].delta.content})}\n\n"
                    
                    yield f"data: {json.dumps({'done': True})}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
            return Response(stream_with_context(generate()), mimetype='text/event-stream')
        else:
            # Generate post (non-streaming)
            post = generate_linkedin_post(
                openai_key=data['openai_api_key'],
                topic=topic,
                style_notes=data['style_notes'],
                keywords=data.get('keywords', [])
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
            "message": f"Post saved to sheet. Worksheet id {ws_id}, current row count {row_count}."
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
        
        # Clear the sheet after posting if requested
        if data.get('clear_sheet_after_post', False) and data.get('service_account_json'):
            try:
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
                
                clear_google_sheet(
                    sheet_url=data['sheet_url'],
                    service_account_json_path=sa_path
                )
                
                # Cleanup
                try:
                    shutil.rmtree(tmpdir)
                except:
                    pass
            except Exception as e:
                app.logger.warning(f"Failed to clear sheet after posting: {e}")
        
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
        # Path to the service account file in project root
        # File is at: EECE798S_Project\linkedin-agent-478216-f37f2b2ce601.json
        project_root = Path(__file__).parent.parent
        sa_file_path = project_root / 'linkedin-agent-478216-f37f2b2ce601.json'
        
        if sa_file_path.exists():
            with open(sa_file_path, 'r') as f:
                content = f.read()
            return content, 200, {'Content-Type': 'application/json'}
        else:
            app.logger.warning(f"Service account file not found at: {sa_file_path}")
            # Try alternative path
            alt_path = project_root.parent / 'linkedin-agent-478216-f37f2b2ce601.json'
            if alt_path.exists():
                with open(alt_path, 'r') as f:
                    content = f.read()
                return content, 200, {'Content-Type': 'application/json'}
            return jsonify({"error": f"Service account file not found. Checked: {sa_file_path}, {alt_path}"}), 404
    except Exception as e:
        app.logger.exception("Error serving service account file")
        return jsonify({"error": str(e)}), 500


# ----------------------------- RUN APP -----------------------------
if __name__ == '__main__':
    # Database initialization is handled by docker-compose via schema.sql
    app.run(host='0.0.0.0', port=5000, debug=True)
