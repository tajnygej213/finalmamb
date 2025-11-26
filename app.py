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
                is_admin BOOLEAN DEFAULT FALSE
            )
        ''')
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data JSON
            )
        ''')
        print("Generated documents table created/verified")

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

    try:
        conn = get_db()
        cur = conn.cursor(row_factory=dict_row)
        cur.execute('SELECT * FROM users WHERE username = %s', (username, ))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if not user or user['password'] != password:
            return jsonify({'error': 'Invalid credentials'}), 401

        if not user['has_access']:
            return jsonify({'error':
                            'Access denied. Contact administrator'}), 403

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
            SELECT d.id, u.username, d.name, d.surname, d.pesel, d.created_at
            FROM generated_documents d
            JOIN users u ON d.user_id = u.id
            ORDER BY d.created_at DESC
        ''')
        documents = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(documents), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Initialize database on startup (before gunicorn starts)
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False)
