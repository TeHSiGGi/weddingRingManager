import sqlite3
from flask import g

# Database file
DATABASE = 'database.db'

# Get the database connection
# If the connection does not exist, create it
# Set the row factory to return rows as dictionaries
# Return the connection
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # To return rows as dictionaries
    return db

# Initialize the database
# Create tables if they do not exist
def init_db():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id TEXT PRIMARY KEY,
            recordTimestamp INTEGER,
            length INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            recordTimestamp INTEGER,
            length INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY,
            autoRing BOOLEAN DEFAULT 0,
            autoRingMinSpan INTEGER DEFAULT 60,
            autoRingMaxSpan INTEGER DEFAULT 600,
            ringOnTime INTEGER DEFAULT 1,
            ringOffTime INTEGER DEFAULT 1,
            messages BOOLEAN DEFAULT 1,
            randomMessages BOOLEAN DEFAULT 1,
            ringCount INTEGER DEFAULT 4
        )
    ''')
    cursor.execute('''
        INSERT OR IGNORE INTO config (id) VALUES (1)
    ''')
    db.commit()

# Query the database
# Return the result of the query
# If one is set to True, return the first result
# If one is set to False, return all results
def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

# Execute DB action
def execute_db(query, args=()):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(query, args)
    db.commit()
    return cursor

# Close the database connection
# If the connection exists, close it
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
