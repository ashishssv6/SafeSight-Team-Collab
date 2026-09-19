import sqlite3
import hashlib
import os

DB_PATH = "safesight.db"

def hash_password(password: str) -> str:
    """Hashes a password using SHA-256."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def init_user_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            full_name TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Default Accounts
    default_users = [
        ("admin", hash_password("Admin@123"), "admin", "Chief Security Officer"),
        ("guard", hash_password("Guard@123"), "operator", "Front Desk Security Guard"),
    ]
    
    for username, pwd_hash, role, full_name in default_users:
        cursor.execute("""
            INSERT OR IGNORE INTO users (username, password_hash, role, full_name)
            VALUES (?, ?, ?, ?)
        """, (username, pwd_hash, role, full_name))
    
    conn.commit()
    conn.close()
    print("User authentication database configured successfully!")
    print("\nDefault Logins:")
    print("  [ADMIN]    Username: admin | Password: Admin@123")
    print("  [OPERATOR] Username: guard | Password: Guard@123")

def create_new_user(username, password, role, full_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    pwd_hash = hash_password(password)
    try:
        cursor.execute("""
            INSERT INTO users (username, password_hash, role, full_name)
            VALUES (?, ?, ?, ?)
        """, (username, pwd_hash, role, full_name))
        conn.commit()
        print(f"User '{username}' ({role}) created successfully.")
    except sqlite3.IntegrityError:
        print(f"Error: Username '{username}' already exists.")
    finally:
        conn.close()

if __name__ == "__main__":
    init_user_db()