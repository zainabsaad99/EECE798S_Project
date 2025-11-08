from flask import Flask, request, jsonify
import mysql.connector
import os
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from datetime import datetime


logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__)

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


# ----------------------------- RUN APP -----------------------------
if __name__ == '__main__':
    init_database()
    ensure_schema()
    app.run(host='0.0.0.0', port=5000, debug=True)
