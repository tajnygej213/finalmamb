#!/usr/bin/env python3
import os
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg
from psycopg.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Database Connection
def get_db():
    return psycopg.connect(os.environ.get('DATABASE_URL'))

def init_db():
    """Initialize database with required tables"""
    if not os.environ.get('DATABASE_URL'):
        print("DATABASE_URL not set - skipping database initialization")
        return
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Users table
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
        
        # Generated documents table
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
        
        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")

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
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Create user with access enabled by default
        cur.execute('INSERT INTO users (username, password, has_access) VALUES (%s, %s, %s)', 
                   (username, password, True))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': 'User created successfully'}), 201
    except psycopg2.IntegrityError:
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
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if not user or user['password'] != password:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if not user['has_access']:
            return jsonify({'error': 'Access denied. Contact administrator'}), 403
        
        return jsonify({'user_id': user['id'], 'username': user['username'], 'is_admin': user['is_admin']}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/save', methods=['POST'])
def save_document():
    data = request.get_json()
    user_id = data.get('user_id')
    
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO generated_documents (user_id, name, surname, pesel, data)
            VALUES (%s, %s, %s, %s, %s)
        ''', (user_id, data.get('name'), data.get('surname'), data.get('pesel'), str(data)))
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
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute('SELECT id, username, has_access, created_at FROM users ORDER BY created_at DESC')
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
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute('UPDATE users SET has_access = %s WHERE id = %s', (has_access, user_id))
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
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
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

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False)
