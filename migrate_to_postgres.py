# migrate_to_postgres.py
# Script to migrate data from SQLite to PostgreSQL

import os
import sqlite3
import sys
from dotenv import load_dotenv

load_dotenv()

# Import PostgreSQL utilities
from postgres_utils import (
    test_connection,
    init_connection_pool,
    init_pgvector_extension,
    execute_query,
    close_connection_pool
)
from user_auth_postgres import init_users_table, create_user
from data_layer_postgres import PostgreSQLDataLayer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def migrate_users():
    """Migrate users from SQLite to PostgreSQL."""
    print("\n" + "="*60)
    print("MIGRATING USERS FROM SQLITE TO POSTGRESQL")
    print("="*60)
    
    sqlite_db = os.path.join(BASE_DIR, "user_data", "users.sqlite")
    
    if not os.path.exists(sqlite_db):
        print(f"⚠️  SQLite users database not found: {sqlite_db}")
        return 0
    
    # Initialize PostgreSQL users table
    init_users_table()
    
    # Connect to SQLite
    conn = sqlite3.connect(sqlite_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        
        migrated = 0
        for user in users:
            email = user["email"]
            password_hash = user["password_hash"]
            name = user.get("name", "")
            is_admin = user.get("is_admin", 0)
            
            # Insert into PostgreSQL
            try:
                execute_query(
                    """
                    INSERT INTO app_users (email, password_hash, name, is_admin, is_active)
                    VALUES (%s, %s, %s, %s, 1)
                    ON CONFLICT (email) DO UPDATE SET
                        password_hash = EXCLUDED.password_hash,
                        name = EXCLUDED.name,
                        is_admin = EXCLUDED.is_admin;
                    """,
                    (email.lower(), password_hash, name, is_admin)
                )
                migrated += 1
                print(f"✅ Migrated user: {email}")
            except Exception as e:
                print(f"❌ Error migrating user {email}: {e}")
        
        print(f"\n✅ Migrated {migrated}/{len(users)} users")
        return migrated
        
    except Exception as e:
        print(f"❌ Error reading SQLite users: {e}")
        return 0
    finally:
        conn.close()

def migrate_chat_history():
    """Migrate chat history from SQLite to PostgreSQL."""
    print("\n" + "="*60)
    print("MIGRATING CHAT HISTORY FROM SQLITE TO POSTGRESQL")
    print("="*60)
    
    sqlite_db = os.path.join(BASE_DIR, "memory_db", "chainlit_history.db")
    
    if not os.path.exists(sqlite_db):
        print(f"⚠️  SQLite chat history database not found: {sqlite_db}")
        return 0
    
    # Initialize PostgreSQL data layer
    data_layer = PostgreSQLDataLayer()
    
    # Connect to SQLite
    conn = sqlite3.connect(sqlite_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Migrate threads
        cursor.execute("SELECT * FROM threads")
        threads = cursor.fetchall()
        
        migrated_threads = 0
        for thread in threads:
            try:
                execute_query(
                    """
                    INSERT INTO threads (id, name, user_id, user_identifier, metadata, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    (
                        thread["id"],
                        thread.get("name"),
                        thread.get("user_id"),
                        thread.get("user_identifier"),
                        thread.get("metadata"),
                        thread.get("created_at")
                    )
                )
                migrated_threads += 1
                print(f"✅ Migrated thread: {thread['id']}")
            except Exception as e:
                print(f"❌ Error migrating thread {thread['id']}: {e}")
        
        # Migrate steps
        cursor.execute("SELECT * FROM steps")
        steps = cursor.fetchall()
        
        migrated_steps = 0
        for step in steps:
            try:
                execute_query(
                    """
                    INSERT INTO steps (id, thread_id, parent_id, name, type, input, output, metadata, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    (
                        step["id"],
                        step["thread_id"],
                        step.get("parent_id"),
                        step.get("name"),
                        step.get("type"),
                        step.get("input"),
                        step.get("output"),
                        step.get("metadata"),
                        step.get("created_at")
                    )
                )
                migrated_steps += 1
                print(f"✅ Migrated step: {step['id']}")
            except Exception as e:
                print(f"❌ Error migrating step {step['id']}: {e}")
        
        print(f"\n✅ Migrated {migrated_threads}/{len(threads)} threads")
        print(f"✅ Migrated {migrated_steps}/{len(steps)} steps")
        return migrated_threads + migrated_steps
        
    except Exception as e:
        print(f"❌ Error reading SQLite chat history: {e}")
        return 0
    finally:
        conn.close()

def main():
    """Main migration function."""
    print("\n" + "="*60)
    print("POSTGRESQL MIGRATION SCRIPT")
    print("="*60)
    print("\nThis script will migrate data from SQLite to PostgreSQL:")
    print("  1. User authentication data")
    print("  2. Chat history (threads and steps)")
    print("\n⚠️  WARNING: Make sure you have:")
    print("  - PostgreSQL server running")
    print("  - Correct credentials in .env file")
    print("  - pgvector extension installed")
    print("="*60)
    
    response = input("\nProceed with migration? (yes/no): ").strip().lower()
    if response != "yes":
        print("❌ Migration cancelled")
        return
    
    # Test PostgreSQL connection
    print("\n🔌 Testing PostgreSQL connection...")
    try:
        init_connection_pool()
        if not test_connection():
            print("❌ Cannot connect to PostgreSQL. Check your .env configuration.")
            return
        
        # Initialize pgvector
        print("\n🚀 Initializing pgvector extension...")
        init_pgvector_extension()
        
    except Exception as e:
        print(f"❌ Error connecting to PostgreSQL: {e}")
        return
    
    # Migrate users
    try:
        users_migrated = migrate_users()
    except Exception as e:
        print(f"❌ Error migrating users: {e}")
        users_migrated = 0
    
    # Migrate chat history
    try:
        history_migrated = migrate_chat_history()
    except Exception as e:
        print(f"❌ Error migrating chat history: {e}")
        history_migrated = 0
    
    # Summary
    print("\n" + "="*60)
    print("MIGRATION SUMMARY")
    print("="*60)
    print(f"Users migrated: {users_migrated}")
    print(f"Chat items migrated: {history_migrated}")
    print("\n✅ Migration complete!")
    print("\n📝 Next steps:")
    print("  1. Update .env with your PostgreSQL credentials")
    print("  2. Test the application")
    print("  3. Backup your SQLite databases")
    print("="*60)
    
    # Close connection pool
    close_connection_pool()

if __name__ == "__main__":
    main()
