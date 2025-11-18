# user_auth_postgres.py
# PostgreSQL User Authentication Helper

import json
from typing import Optional, Dict, List
from werkzeug.security import generate_password_hash, check_password_hash
from postgres_utils import execute_query, get_connection, release_connection

def init_users_table():
    """
    Initialize users table in PostgreSQL.
    """
    execute_query("""
        CREATE TABLE IF NOT EXISTS app_users (
            email TEXT PRIMARY KEY, 
            password_hash TEXT NOT NULL,
            name TEXT,
            is_admin INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    execute_query("CREATE INDEX IF NOT EXISTS idx_users_email ON app_users(email);")
    print("✅ [Auth PostgreSQL] Users table initialized")

def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email."""
    rows = execute_query(
        "SELECT * FROM app_users WHERE email = %s LIMIT 1;",
        (email.lower(),),
        fetch=True
    )
    return dict(rows[0]) if rows else None

def create_user(email: str, password: str, name: str = "", is_admin: bool = False) -> bool:
    """Create a new user."""
    try:
        password_hash = generate_password_hash(password)
        execute_query(
            """
            INSERT INTO app_users (email, password_hash, name, is_admin, is_active)
            VALUES (%s, %s, %s, %s, 1);
            """,
            (email.lower(), password_hash, name, 1 if is_admin else 0)
        )
        print(f"✅ [Auth] Created user: {email}")
        return True
    except Exception as e:
        print(f"❌ [Auth] Error creating user {email}: {e}")
        return False

def authenticate_user(email: str, password: str) -> Optional[Dict]:
    """Authenticate user with email and password."""
    user = get_user_by_email(email)
    if user and check_password_hash(user["password_hash"], password):
        return user
    return None

def update_user(email: str, **kwargs) -> bool:
    """Update user fields."""
    try:
        updates = []
        params = []
        
        if "name" in kwargs:
            updates.append("name = %s")
            params.append(kwargs["name"])
        if "is_admin" in kwargs:
            updates.append("is_admin = %s")
            params.append(1 if kwargs["is_admin"] else 0)
        if "is_active" in kwargs:
            updates.append("is_active = %s")
            params.append(1 if kwargs["is_active"] else 0)
        if "password" in kwargs:
            updates.append("password_hash = %s")
            params.append(generate_password_hash(kwargs["password"]))
        
        if not updates:
            return False
        
        params.append(email.lower())
        query = f"UPDATE app_users SET {', '.join(updates)} WHERE email = %s;"
        execute_query(query, tuple(params))
        print(f"✅ [Auth] Updated user: {email}")
        return True
    except Exception as e:
        print(f"❌ [Auth] Error updating user {email}: {e}")
        return False

def delete_user(email: str) -> bool:
    """Delete user."""
    try:
        execute_query("DELETE FROM app_users WHERE email = %s;", (email.lower(),))
        print(f"✅ [Auth] Deleted user: {email}")
        return True
    except Exception as e:
        print(f"❌ [Auth] Error deleting user {email}: {e}")
        return False

def list_all_users() -> List[Dict]:
    """List all users."""
    rows = execute_query("SELECT * FROM app_users ORDER BY email;", fetch=True)
    return [dict(row) for row in rows]

def sync_users_from_api(users_data: List[Dict]) -> int:
    """
    Sync users from API data.
    Returns number of users synced.
    """
    synced_count = 0
    for user_data in users_data:
        email = user_data.get("email", "").lower()
        if not email:
            continue
        
        # Check if user exists
        existing = get_user_by_email(email)
        if existing:
            # Update existing user
            update_user(
                email,
                name=user_data.get("name", ""),
                is_active=user_data.get("is_active", 1) == 1
            )
        else:
            # Create new user with default password
            create_user(
                email,
                password="1",  # Default password
                name=user_data.get("name", ""),
                is_admin=user_data.get("is_admin", 0) == 1
            )
        synced_count += 1
    
    print(f"✅ [Auth] Synced {synced_count} users from API")
    return synced_count
