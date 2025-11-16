# data_layer_postgres.py
# PostgreSQL Data Layer for Chainlit 2.3.0+

import os
import json
from datetime import datetime
from typing import Dict, List, Optional, TypedDict
import asyncio
from postgres_utils import execute_query, get_connection, release_connection

# Import BaseDataLayer only
try:
    from chainlit.data import BaseDataLayer
except ImportError:
    from chainlit.data.base import BaseDataLayer

# Define custom TypedDict classes (compatible with all Chainlit versions)
class ThreadDict(TypedDict, total=False):
    id: str
    name: Optional[str]
    userId: Optional[str]
    userIdentifier: Optional[str]
    metadata: Optional[Dict]
    createdAt: Optional[str]

class PersistedUser(TypedDict, total=False):
    id: str
    identifier: str
    metadata: Optional[Dict]
    createdAt: Optional[str]

class StepDict(TypedDict, total=False):
    id: str
    threadId: str
    parentId: Optional[str]
    name: str
    type: str
    input: str
    output: str
    metadata: Dict
    createdAt: str

class FeedbackDict(TypedDict, total=False):
    id: str
    forId: str
    value: int
    comment: Optional[str]

class DeleteFeedbackDict(TypedDict):
    id: str

class PostgreSQLDataLayer(BaseDataLayer):
    """
    Custom Data Layer using PostgreSQL for Chainlit 2.3.0+
    Implements all required abstract methods from BaseDataLayer.
    """
    
    def __init__(self):
        """Initialize PostgreSQL Data Layer and create tables if needed."""
        print("🔧 [PostgreSQL DataLayer] Initializing...")
        self._init_tables()
        print("✅ [PostgreSQL DataLayer] Database initialized")
    
    def _init_tables(self):
        """Create required tables in PostgreSQL if they don't exist."""
        
        # Users table
        execute_query("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                identifier TEXT UNIQUE NOT NULL,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Threads table
        execute_query("""
            CREATE TABLE IF NOT EXISTS threads (
                id TEXT PRIMARY KEY,
                name TEXT,
                user_id TEXT,
                user_identifier TEXT,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        execute_query("CREATE INDEX IF NOT EXISTS idx_threads_user_id ON threads(user_id);")
        
        # Steps table
        execute_query("""
            CREATE TABLE IF NOT EXISTS steps (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                parent_id TEXT,
                name TEXT,
                type TEXT,
                input TEXT,
                output TEXT,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
            );
        """)
        execute_query("CREATE INDEX IF NOT EXISTS idx_steps_thread_id ON steps(thread_id);")
        
        # Feedback table
        execute_query("""
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                for_id TEXT NOT NULL,
                value INTEGER,
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        execute_query("CREATE INDEX IF NOT EXISTS idx_feedback_for_id ON feedback(for_id);")
    
    # ============================================================
    # USER METHODS
    # ============================================================
    
    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        """Get user by identifier."""
        def _get():
            rows = execute_query(
                "SELECT * FROM users WHERE identifier = %s LIMIT 1;",
                (identifier,),
                fetch=True
            )
            if rows:
                row = rows[0]
                return PersistedUser(
                    id=row["id"],
                    identifier=row["identifier"],
                    metadata=row.get("metadata"),
                    createdAt=row.get("created_at").isoformat() if row.get("created_at") else None
                )
            return None
        
        return await asyncio.to_thread(_get)
    
    async def create_user(self, user: PersistedUser) -> Optional[PersistedUser]:
        """Create a new user."""
        def _create():
            execute_query(
                """
                INSERT INTO users (id, identifier, metadata, created_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (identifier) DO UPDATE SET metadata = EXCLUDED.metadata;
                """,
                (
                    user["id"],
                    user["identifier"],
                    json.dumps(user.get("metadata")) if user.get("metadata") else None,
                    datetime.fromisoformat(user["createdAt"]) if user.get("createdAt") else datetime.now()
                )
            )
            return user
        
        return await asyncio.to_thread(_create)
    
    # ============================================================
    # THREAD METHODS
    # ============================================================
    
    async def get_thread_author(self, thread_id: str) -> str:
        """Get the author (user identifier) of a thread."""
        def _get():
            rows = execute_query(
                "SELECT user_identifier FROM threads WHERE id = %s LIMIT 1;",
                (thread_id,),
                fetch=True
            )
            return rows[0]["user_identifier"] if rows else "unknown"
        
        return await asyncio.to_thread(_get)
    
    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        """Get thread by ID."""
        def _get():
            rows = execute_query(
                "SELECT * FROM threads WHERE id = %s LIMIT 1;",
                (thread_id,),
                fetch=True
            )
            if rows:
                row = rows[0]
                return ThreadDict(
                    id=row["id"],
                    name=row.get("name"),
                    userId=row.get("user_id"),
                    userIdentifier=row.get("user_identifier"),
                    metadata=row.get("metadata"),
                    createdAt=row.get("created_at").isoformat() if row.get("created_at") else None
                )
            return None
        
        return await asyncio.to_thread(_get)
    
    async def create_thread(self, thread: ThreadDict) -> Optional[ThreadDict]:
        """Create a new thread."""
        def _create():
            execute_query(
                """
                INSERT INTO threads (id, name, user_id, user_identifier, metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    metadata = EXCLUDED.metadata;
                """,
                (
                    thread["id"],
                    thread.get("name"),
                    thread.get("userId"),
                    thread.get("userIdentifier"),
                    json.dumps(thread.get("metadata")) if thread.get("metadata") else None,
                    datetime.fromisoformat(thread["createdAt"]) if thread.get("createdAt") else datetime.now()
                )
            )
            return thread
        
        return await asyncio.to_thread(_create)
    
    async def update_thread(self, thread_id: str, name: Optional[str] = None, 
                           user_id: Optional[str] = None, metadata: Optional[Dict] = None, 
                           tags: Optional[List[str]] = None) -> Optional[ThreadDict]:
        """Update thread metadata/name."""
        def _update():
            # Build dynamic update query
            updates = []
            params = []
            
            if name is not None:
                updates.append("name = %s")
                params.append(name)
            if user_id is not None:
                updates.append("user_id = %s")
                params.append(user_id)
            if metadata is not None:
                updates.append("metadata = %s")
                params.append(json.dumps(metadata))
            
            if not updates:
                return None
            
            params.append(thread_id)
            query = f"UPDATE threads SET {', '.join(updates)} WHERE id = %s;"
            execute_query(query, tuple(params))
            
            # Fetch and return updated thread
            rows = execute_query(
                "SELECT * FROM threads WHERE id = %s LIMIT 1;",
                (thread_id,),
                fetch=True
            )
            if rows:
                row = rows[0]
                return ThreadDict(
                    id=row["id"],
                    name=row.get("name"),
                    userId=row.get("user_id"),
                    userIdentifier=row.get("user_identifier"),
                    metadata=row.get("metadata"),
                    createdAt=row.get("created_at").isoformat() if row.get("created_at") else None
                )
            return None
        
        return await asyncio.to_thread(_update)
    
    async def delete_thread(self, thread_id: str):
        """Delete a thread and all associated steps."""
        def _delete():
            execute_query("DELETE FROM threads WHERE id = %s;", (thread_id,))
        
        await asyncio.to_thread(_delete)
    
    async def list_threads(self, pagination: Dict, filters: Dict) -> Dict:
        """List threads with pagination and filters."""
        def _list():
            # Build WHERE clause from filters
            where_clauses = []
            params = []
            
            if filters.get("userId"):
                where_clauses.append("user_id = %s")
                params.append(filters["userId"])
            if filters.get("search"):
                where_clauses.append("name ILIKE %s")
                params.append(f"%{filters['search']}%")
            
            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            
            # Count total
            count_query = f"SELECT COUNT(*) as count FROM threads {where_sql};"
            count_result = execute_query(count_query, tuple(params), fetch=True)
            total = count_result[0]["count"] if count_result else 0
            
            # Fetch threads with pagination
            limit = pagination.get("limit", 20)
            offset = pagination.get("offset", 0)
            
            data_query = f"""
                SELECT * FROM threads {where_sql}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s;
            """
            params.extend([limit, offset])
            rows = execute_query(data_query, tuple(params), fetch=True)
            
            threads = []
            for row in rows:
                threads.append(ThreadDict(
                    id=row["id"],
                    name=row.get("name"),
                    userId=row.get("user_id"),
                    userIdentifier=row.get("user_identifier"),
                    metadata=row.get("metadata"),
                    createdAt=row.get("created_at").isoformat() if row.get("created_at") else None
                ))
            
            return {
                "data": threads,
                "pageInfo": {
                    "hasNextPage": (offset + limit) < total,
                    "startCursor": str(offset),
                    "endCursor": str(offset + len(threads))
                }
            }
        
        return await asyncio.to_thread(_list)
    
    # ============================================================
    # STEP METHODS
    # ============================================================
    
    async def create_step(self, step: StepDict):
        """Create a new step in a thread."""
        def _create():
            execute_query(
                """
                INSERT INTO steps (id, thread_id, parent_id, name, type, input, output, metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    output = EXCLUDED.output,
                    metadata = EXCLUDED.metadata;
                """,
                (
                    step["id"],
                    step["threadId"],
                    step.get("parentId"),
                    step.get("name"),
                    step.get("type"),
                    step.get("input"),
                    step.get("output"),
                    json.dumps(step.get("metadata")) if step.get("metadata") else None,
                    datetime.fromisoformat(step["createdAt"]) if step.get("createdAt") else datetime.now()
                )
            )
        
        await asyncio.to_thread(_create)
    
    async def get_steps(self, thread_id: str) -> List[StepDict]:
        """Get all steps for a thread."""
        def _get():
            rows = execute_query(
                "SELECT * FROM steps WHERE thread_id = %s ORDER BY created_at ASC;",
                (thread_id,),
                fetch=True
            )
            steps = []
            for row in rows:
                steps.append(StepDict(
                    id=row["id"],
                    threadId=row["thread_id"],
                    parentId=row.get("parent_id"),
                    name=row.get("name"),
                    type=row.get("type"),
                    input=row.get("input"),
                    output=row.get("output"),
                    metadata=row.get("metadata"),
                    createdAt=row.get("created_at").isoformat() if row.get("created_at") else None
                ))
            return steps
        
        return await asyncio.to_thread(_get)
    
    async def update_step(self, step: StepDict):
        """Update an existing step."""
        def _update():
            execute_query(
                """
                UPDATE steps SET
                    name = %s,
                    type = %s,
                    input = %s,
                    output = %s,
                    metadata = %s
                WHERE id = %s;
                """,
                (
                    step.get("name"),
                    step.get("type"),
                    step.get("input"),
                    step.get("output"),
                    json.dumps(step.get("metadata")) if step.get("metadata") else None,
                    step["id"]
                )
            )
        
        await asyncio.to_thread(_update)
    
    async def delete_step(self, step_id: str):
        """Delete a step."""
        def _delete():
            execute_query("DELETE FROM steps WHERE id = %s;", (step_id,))
        
        await asyncio.to_thread(_delete)
    
    # ============================================================
    # FEEDBACK METHODS
    # ============================================================
    
    async def upsert_feedback(self, feedback: FeedbackDict):
        """Create or update feedback."""
        def _upsert():
            execute_query(
                """
                INSERT INTO feedback (id, for_id, value, comment, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    value = EXCLUDED.value,
                    comment = EXCLUDED.comment;
                """,
                (
                    feedback["id"],
                    feedback["forId"],
                    feedback["value"],
                    feedback.get("comment"),
                    datetime.now()
                )
            )
        
        await asyncio.to_thread(_upsert)
    
    async def delete_feedback(self, feedback_id: str):
        """Delete feedback."""
        def _delete():
            execute_query("DELETE FROM feedback WHERE id = %s;", (feedback_id,))
        
        await asyncio.to_thread(_delete)
    
    # ============================================================
    # ELEMENT METHODS (Optional - Stub implementations)
    # ============================================================
    
    async def create_element(self, element: Dict):
        """Stub: Create element (not implemented for PostgreSQL)."""
        pass
    
    async def get_element(self, thread_id: str, element_id: str) -> Optional[Dict]:
        """Stub: Get element (not implemented for PostgreSQL)."""
        return None
    
    async def delete_element(self, element_id: str):
        """Stub: Delete element (not implemented for PostgreSQL)."""
        pass
