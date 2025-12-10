#!/usr/bin/env python3
import os
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_file, send_from_directory, Response
from flask_cors import CORS
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Serve static files from /assets/
@app.route('/assets/<path:filename>')
def serve_assets(filename):
    try:
        return send_from_directory('assets', filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

# Serve HTML files with proper caching headers
def serve_html(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        response = Response(content, mimetype='text/html; charset=utf-8')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
    except Exception as e:
        return jsonify({'error': f'Cannot load {filename}: {str(e)}'}), 500


# Database Connection
def get_db():
    return psycopg.connect(os.environ.get('DATABASE_URL'))


def init_db():
    """Initialize database with required tables"""
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("WARNING: DATABASE_URL not set - skipping database initialization")
        return

    try:
        print(f"Connecting to database...")
        conn = psycopg.connect(db_url)
        cur = conn.cursor()
        print("Connection successful")

        # Users table
        print("Creating users table...")
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                has_access BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_admin BOOLEAN DEFAULT FALSE,
                hwid VARCHAR(255)
            )
        ''')
        conn.commit()
        print("Users table created/verified")

        # Generated documents table
        print("Creating generated_documents table...")
        cur.execute('''
            CREATE TABLE IF NOT EXISTS generated_documents (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                name VARCHAR(255),
                surname VARCHAR(255),
                pesel VARCHAR(11),
                access_code VARCHAR(12),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data JSON
            )
        ''')
        conn.commit()
        print("Generated documents table created/verified")

        # One-time codes table
        print("Creating one_time_codes table...")
        cur.execute('''
            CREATE TABLE IF NOT EXISTS one_time_codes (
                id SERIAL PRIMARY KEY,
                code VARCHAR(12) UNIQUE NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        print("One-time codes table created/verified")

        # Seed admin user if not exists
        print("Checking for admin user...")
        try:
            cur.execute('INSERT INTO users (username, password, has_access, is_admin) VALUES (%s, %s, %s, %s)',
                       ('mamba', 'MangoMango67', True, True))
            conn.commit()
            print("✓ Admin user 'mamba' created successfully!")
        except psycopg.IntegrityError:
            print("✓ Admin user 'mamba' already exists")
        
        cur.close()
        conn.close()
        print("✓ Database initialization completed successfully!")
    except Exception as e:
        print(f"ERROR: Database initialization failed: {e}")
        import traceback
        traceback.print_exc()


# Serve HTML files with correct MIME types
@app.route('/')
def index():
    return serve_html('admin-login.html')


@app.route('/admin-login.html')
def admin_login_page():
    return serve_html('admin-login.html')


@app.route('/login.html')
def login_page():
    return serve_html('login.html')


@app.route('/gen.html')
def gen_page():
    return serve_html('gen.html')


@app.route('/manifest.json')
def manifest():
    try:
        with open('manifest.json', 'r', encoding='utf-8') as f:
            content = f.read()
        response = Response(content, mimetype='application/manifest+json')
        response.headers['Cache-Control'] = 'public, max-age=3600'
        return response
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/admin.html')
def admin_page():
    return serve_html('admin.html')


# Seed database with admin user
@app.route('/api/seed', methods=['POST'])
def seed():
    try:
        conn = get_db()
        cur = conn.cursor(row_factory=dict_row)
        
        # Try to create admin user
        try:
            cur.execute(
                'INSERT INTO users (username, password, has_access, is_admin) VALUES (%s, %s, %s, %s)',
                ('mamba', 'MangoMango67', True, True))
            conn.commit()
            print("Admin user 'mamba' created")
        except psycopg.IntegrityError:
            print("Admin user already exists")
        
        cur.close()
        conn.close()
        return jsonify({'message': 'Database seeded successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Routes
@app.route('/api/auth/create-user', methods=['POST'])
def create_user():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    try:
        conn = get_db()
        cur = conn.cursor(row_factory=dict_row)

        # Create user with access enabled by default
        cur.execute(
            'INSERT INTO users (username, password, has_access) VALUES (%s, %s, %s)',
            (username, password, True))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': 'User created successfully'}), 201
    except psycopg.IntegrityError:
        return jsonify({'error': 'Username already exists'}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    hwid = data.get('hwid')  # Optional - only for regular users

    try:
        conn = get_db()
        cur = conn.cursor(row_factory=dict_row)
        cur.execute('SELECT * FROM users WHERE username = %s', (username, ))
        user = cur.fetchone()

        if not user or user['password'] != password:
            cur.close()
            conn.close()
            return jsonify({'error': 'Invalid credentials'}), 401

        if not user['has_access']:
            cur.close()
            conn.close()
            return jsonify({'error':
                            'Access denied. Contact administrator'}), 403

        # HWID validation - only for non-admin users (regular users with HWID)
        if hwid:
            # User sent HWID - validate it
            if user['hwid']:
                if user['hwid'] != hwid:
                    cur.close()
                    conn.close()
                    return jsonify({'error': 'Device not authorized. Login from registered device only'}), 403
            else:
                # First login with HWID - save it
                cur.execute('UPDATE users SET hwid = %s WHERE id = %s', (hwid, user['id']))
                conn.commit()

        cur.close()
        conn.close()
        return jsonify({
            'user_id': user['id'],
            'username': user['username'],
            'is_admin': user['is_admin']
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/documents/save', methods=['POST'])
def save_document():
    data = request.get_json()
    user_id = data.get('user_id')

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            '''
            INSERT INTO generated_documents (user_id, name, surname, pesel, data)
            VALUES (%s, %s, %s, %s, %s)
        ''',
            (user_id, data.get('name'), data.get('surname'), data.get('pesel'),
             str(data)))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': 'Document saved'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/create-and-get-id', methods=['POST'])
def create_document_with_id():
    """Save document with full data and return only document ID for secure sharing"""
    data = request.get_json()
    user_id = data.get('user_id')  # Can be None for guest/one-time use
    access_code = data.get('access_code')  # One-time code if used

    try:
        conn = get_db()
        cur = conn.cursor(row_factory=dict_row)
        
        # Save all document data to database
        import json
        print(f"DEBUG: Inserting document for user_id={user_id}, name={data.get('name')}, code={access_code}")
        cur.execute(
            '''
            INSERT INTO generated_documents (user_id, name, surname, pesel, access_code, data)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        ''',
            (user_id, data.get('name'), data.get('surname'), data.get('pesel'),
             access_code, json.dumps(data)))
        
        result = cur.fetchone()
        document_id = result['id'] if result else None
        print(f"DEBUG: Insert result: {result}, document_id={document_id}")
        
        # Fallback if RETURNING doesn't work on Railway
        if not document_id:
            pesel = data.get('pesel')
            print("DEBUG: RETURNING didn't return ID, fetching latest...")
            cur.execute('SELECT id FROM generated_documents WHERE pesel = %s ORDER BY id DESC LIMIT 1', (pesel,))
            result = cur.fetchone()
            document_id = result['id'] if result else None
            print(f"DEBUG: Fallback result: {result}, document_id={document_id}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"DEBUG: Returning document_id={document_id}")
        return jsonify({'document_id': document_id}), 201
    except Exception as e:
        print(f"ERROR in create_document_with_id: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/<int:document_id>', methods=['GET'])
def get_document(document_id):
    """Retrieve document data by ID"""
    try:
        conn = get_db()
        cur = conn.cursor(row_factory=dict_row)
        cur.execute('SELECT data FROM generated_documents WHERE id = %s', (document_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if not result:
            return jsonify({'error': 'Document not found'}), 404
        
        import json
        document_data = json.loads(result['data']) if isinstance(result['data'], str) else result['data']
        return jsonify(document_data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/users', methods=['GET'])
def get_users():
    try:
        conn = get_db()
        cur = conn.cursor(row_factory=dict_row)

        cur.execute(
            'SELECT id, username, has_access, created_at FROM users ORDER BY created_at DESC'
        )
        users = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(users), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/users/<int:user_id>/access', methods=['PUT'])
def update_access(user_id):
    data = request.get_json()
    has_access = data.get('has_access')

    try:
        conn = get_db()
        cur = conn.cursor(row_factory=dict_row)

        cur.execute('UPDATE users SET has_access = %s WHERE id = %s',
                    (has_access, user_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': 'Access updated'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/documents', methods=['GET'])
def get_all_documents():
    try:
        conn = get_db()
        cur = conn.cursor(row_factory=dict_row)

        cur.execute('''
            SELECT d.id, u.username, d.name, d.surname, d.pesel, d.access_code, d.created_at
            FROM generated_documents d
            LEFT JOIN users u ON d.user_id = u.id
            ORDER BY d.created_at DESC
        ''')
        documents = cur.fetchall()
        cur.close()
        conn.close()
        
        # Convert to list of dicts with ISO datetime
        result = []
        for doc in documents:
            doc_dict = dict(doc) if hasattr(doc, 'keys') else doc
            if isinstance(doc_dict.get('created_at'), str):
                doc_dict['created_at'] = doc_dict['created_at']
            result.append(doc_dict)
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/documents/<int:document_id>', methods=['PUT'])
def update_document(document_id):
    data = request.get_json()
    name = data.get('name')
    surname = data.get('surname')
    pesel = data.get('pesel')
    adress1 = data.get('adress1')
    adress2 = data.get('adress2')
    birthPlace = data.get('birthPlace')
    image = data.get('image')
    
    try:
        conn = get_db()
        cur = conn.cursor(row_factory=dict_row)
        
        # Get current document data
        cur.execute('SELECT data FROM generated_documents WHERE id = %s', (document_id,))
        result = cur.fetchone()
        
        if not result:
            return jsonify({'error': 'Document not found'}), 404
        
        # Update document data with new values
        import json
        doc_data = json.loads(result['data']) if isinstance(result['data'], str) else result['data']
        doc_data['name'] = name
        doc_data['surname'] = surname
        doc_data['pesel'] = pesel
        if adress1:
            doc_data['adress1'] = adress1
        if adress2:
            doc_data['adress2'] = adress2
        if birthPlace:
            doc_data['birthPlace'] = birthPlace
        if image:
            doc_data['image'] = image
        
        cur.execute('UPDATE generated_documents SET name = %s, surname = %s, pesel = %s, data = %s WHERE id = %s',
                    (name, surname, pesel, json.dumps(doc_data), document_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': 'Document updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/documents/<int:document_id>', methods=['DELETE'])
def delete_document(document_id):
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute('DELETE FROM generated_documents WHERE id = %s', (document_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': 'Document deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# One-time code generation
import random
import string

@app.route('/api/admin/generate-codes', methods=['POST'])
def generate_codes():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request body'}), 400
        count = data.get('count', 1)
        
        try:
            count = int(count)
            if count < 1 or count > 100:
                return jsonify({'error': 'Count must be between 1 and 100'}), 400
        except:
            return jsonify({'error': 'Invalid count'}), 400
        
        conn = get_db()
        cur = conn.cursor(row_factory=dict_row)
        
        codes = []
        for i in range(count):
            attempts = 0
            while attempts < 100:
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
                cur.execute('SELECT id FROM one_time_codes WHERE code = %s', (code,))
                if not cur.fetchone():
                    break
                attempts += 1
            
            cur.execute('INSERT INTO one_time_codes (code) VALUES (%s)', (code,))
            codes.append(code)
        
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'codes': codes}), 201
    except Exception as e:
        print(f"Error generating codes: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/codes', methods=['GET'])
def get_codes():
    try:
        conn = get_db()
        cur = conn.cursor(row_factory=dict_row)
        cur.execute('SELECT id, code, used, used_at, created_at FROM one_time_codes ORDER BY created_at DESC')
        codes = cur.fetchall()
        cur.close()
        conn.close()
        
        # Convert datetime objects to strings
        codes_list = []
        for code in codes:
            codes_list.append({
                'id': code['id'],
                'code': code['code'],
                'used': code['used'],
                'used_at': code['used_at'].isoformat() if code['used_at'] else None,
                'created_at': code['created_at'].isoformat() if code['created_at'] else None
            })
        
        return jsonify({'codes': codes_list}), 200
    except Exception as e:
        print(f"Error getting codes: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/clear-codes')
def clear_codes_page():
    """Page to clear all one-time codes from database"""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('DELETE FROM one_time_codes')
        deleted_count = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        return f'''
        <!DOCTYPE html>
        <html>
        <head><title>Codes Cleared</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>Kody wyczyszczone!</h1>
            <p>Usunieto {deleted_count} kodow z bazy danych.</p>
            <a href="/admin.html">Powrot do panelu admina</a>
        </body>
        </html>
        ''', 200
    except Exception as e:
        return f'''
        <!DOCTYPE html>
        <html>
        <head><title>Error</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>Blad!</h1>
            <p>{str(e)}</p>
            <a href="/admin.html">Powrot do panelu admina</a>
        </body>
        </html>
        ''', 500


@app.route('/api/auth/validate-code', methods=['POST'])
def validate_code():
    data = request.get_json()
    code = data.get('code', '').strip().upper()
    
    if not code:
        return jsonify({'error': 'Code is required'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor(row_factory=dict_row)
        cur.execute('SELECT id FROM one_time_codes WHERE code = %s AND used = FALSE', (code,))
        code_record = cur.fetchone()
        
        if not code_record:
            cur.close()
            conn.close()
            return jsonify({'error': 'Code is invalid or already used'}), 401
        
        # Mark code as used
        cur.execute('UPDATE one_time_codes SET used = TRUE, used_at = CURRENT_TIMESTAMP WHERE id = %s', (code_record['id'],))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': 'Code validated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/webhooks/purchase', methods=['POST'])
def handle_purchase_webhook():
    """Webhook for automatic access granting after purchase"""
    data = request.get_json()
    email = data.get('email', '').lower().strip() if data.get('email') else None
    username = data.get('username', '').strip() if data.get('username') else None
    product_type = data.get('product_type', 'obywatel')  # obywatel or receipts
    webhook_secret = data.get('secret')
    
    # Simple webhook security - check secret if provided
    if webhook_secret != os.environ.get('WEBHOOK_SECRET', 'default-secret'):
        return jsonify({'error': 'Invalid webhook secret'}), 401
    
    if not email and not username:
        return jsonify({'error': 'Email or username required'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor(row_factory=dict_row)
        
        # Find user by email or username
        user = None
        if email:
            cur.execute('SELECT * FROM users WHERE email = %s OR username = %s', (email, email))
            user = cur.fetchone()
        
        if not user and username:
            cur.execute('SELECT * FROM users WHERE username = %s', (username,))
            user = cur.fetchone()
        
        # If user doesn't exist, create one
        if not user:
            if not email:
                cur.close()
                conn.close()
                return jsonify({'error': 'Email required to create new account'}), 400
            
            # Generate random password for auto-created accounts
            import secrets
            random_password = secrets.token_urlsafe(16)
            new_username = email.split('@')[0] + '_' + secrets.token_hex(4)
            
            try:
                cur.execute(
                    'INSERT INTO users (username, password, email, has_access, is_admin) VALUES (%s, %s, %s, %s, %s)',
                    (new_username, random_password, email, True, False)
                )
                conn.commit()
                cur.execute('SELECT id FROM users WHERE username = %s', (new_username,))
                user = cur.fetchone()
                print(f"[Webhook] Created new user: {new_username} for {email}")
            except psycopg.IntegrityError:
                conn.rollback()
                # User was created by concurrent request, fetch it
                cur.execute('SELECT * FROM users WHERE email = %s', (email,))
                user = cur.fetchone()
        
        # Grant access
        if user:
            cur.execute('UPDATE users SET has_access = TRUE WHERE id = %s', (user['id'],))
            conn.commit()
            print(f"[Webhook] Access granted to user: {user['username']} (email: {email})")
            
            cur.close()
            conn.close()
            return jsonify({
                'success': True,
                'message': 'Access granted successfully',
                'user_id': user['id'],
                'username': user['username']
            }), 200
        else:
            cur.close()
            conn.close()
            return jsonify({'error': 'User not found and could not be created'}), 404
            
    except Exception as e:
        print(f"[Webhook] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# Initialize database on startup (before gunicorn starts)
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
