import sqlite3
from flask import g

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('devices.db')
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    with open('schema.sql', 'r') as f:
        db.executescript(f.read())

def query_devices(search=None, category=None, status=None):
    db = get_db()
    query = 'SELECT * FROM devices WHERE 1=1'
    params = []
    if search:
        query += ' AND (name LIKE ? OR location LIKE ? OR supervisor LIKE ?)' 
        params += [f'%{search}%'] * 3
    if category:
        query += ' AND category = ?'
        params.append(category)
    if status:
        query += ' AND status = ?'
        params.append(status)
    return db.execute(query, params).fetchall()

def get_categories():
    db = get_db()
    rows = db.execute('SELECT DISTINCT category FROM devices').fetchall()
    return [row['category'] for row in rows]

def get_statuses():
    db = get_db()
    rows = db.execute('SELECT DISTINCT status FROM devices').fetchall()
    return [row['status'] for row in rows]

def get_all_users():
    db = get_db()
    return db.execute('SELECT * FROM usuarios').fetchall()

CATEGORIAS_FIJAS = [
    'zebra',
    'Notebook',
    'routers',
    'switch',
    'famocos'
]
