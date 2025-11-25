#!/usr/bin/env python3
import os
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# JWT Configuration
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET', 'your-secret-key-change-this')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)
jwt = JWTManager(app)

# Database Connection
def get_db():
    return psycopg2.connect(os.environ.get('DATABASE_URL'))

def init_db():
    """Initialize database with required tables"""
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
@jwt_required()
def create_user():
    admin_id = get_jwt_identity()
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if admin
        cur.execute('SELECT is_admin FROM users WHERE id = %s', (admin_id,))
        user = cur.fetchone()
        if not user or not user['is_admin']:
            return jsonify({'error': 'Admin access required'}), 403
        
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
        
        access_token = create_access_token(identity=str(user['id']))
        return jsonify({'access_token': access_token, 'username': user['username']}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/verify', methods=['GET'])
@jwt_required()
def verify():
    user_id = get_jwt_identity()
    return jsonify({'user_id': user_id}), 200

@app.route('/api/documents/save', methods=['POST'])
@jwt_required()
def save_document():
    user_id = get_jwt_identity()
    data = request.get_json()
    
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
@jwt_required()
def get_users():
    user_id = get_jwt_identity()
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if admin
        cur.execute('SELECT is_admin FROM users WHERE id = %s', (user_id,))
        user = cur.fetchone()
        if not user or not user['is_admin']:
            return jsonify({'error': 'Admin access required'}), 403
        
        cur.execute('SELECT id, username, has_access, created_at FROM users ORDER BY created_at DESC')
        users = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(users), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/users/<int:user_id>/access', methods=['PUT'])
@jwt_required()
def update_access(user_id):
    admin_id = get_jwt_identity()
    data = request.get_json()
    has_access = data.get('has_access')
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if admin
        cur.execute('SELECT is_admin FROM users WHERE id = %s', (admin_id,))
        user = cur.fetchone()
        if not user or not user['is_admin']:
            return jsonify({'error': 'Admin access required'}), 403
        
        cur.execute('UPDATE users SET has_access = %s WHERE id = %s', (has_access, user_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': 'Access updated'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/documents', methods=['GET'])
@jwt_required()
def get_all_documents():
    admin_id = get_jwt_identity()
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute('SELECT is_admin FROM users WHERE id = %s', (admin_id,))
        user = cur.fetchone()
        if not user or not user['is_admin']:
            return jsonify({'error': 'Admin access required'}), 403
        
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
    app.run(host='localhost', port=3000, debug=True)
