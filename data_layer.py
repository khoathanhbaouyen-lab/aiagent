# data_layer.py
# Custom Data Layer for Chainlit 2.3.0+ with SQLite

import os
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, TypedDict
import asyncio

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

class SQLiteDataLayer(BaseDataLayer):
    """
    Custom Data Layer dùng SQLite để lưu trữ chat history.
    Tương thích với Chainlit 2.3.0+
    """
    
    def __init__(self, db_path: str = "memory_db/chainlit_history.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
    
    def _get_conn(self):
        """Helper: Tạo kết nối SQLite"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Khởi tạo bảng (nếu chưa có)"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Bảng threads (conversations)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS threads (
            id TEXT PRIMARY KEY,
            name TEXT,
            user_id TEXT,
            metadata TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Bảng steps (messages)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS steps (
            id TEXT PRIMARY KEY,
            thread_id TEXT,
            parent_id TEXT,
            name TEXT,
            type TEXT,
            input TEXT,
            output TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT,
            FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
        )
        """)
        
        conn.commit()
        conn.close()
        print(f"✅ [DataLayer] Database initialized at: {self.db_path}")
    
    # =========================================================
    # PHƯƠNG THỨC BẮT BUỘC (Chainlit 2.3.0+)
    # =========================================================
    
    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        """Lấy thông tin user (không dùng - trả về dummy)"""
        return PersistedUser(id=identifier, identifier=identifier, metadata={})
    
    async def create_user(self, user: PersistedUser) -> Optional[PersistedUser]:
        """Tạo user (không dùng - trả về dummy)"""
        return user
    
    async def list_threads(
        self, 
        pagination: Dict, 
        filters: Dict
    ) -> Dict:
        """
        🔥 QUAN TRỌNG NHẤT - Hiển thị sidebar history
        """
        def _list_sync():
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # Lọc theo user_id (nếu có)
            user_id = filters.get("userId")
            if user_id:
                cursor.execute(
                    "SELECT id, name, user_id, metadata, created_at FROM threads WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,)
                )
            else:
                cursor.execute("SELECT id, name, user_id, metadata, created_at FROM threads ORDER BY created_at DESC")
            
            rows = cursor.fetchall()
            conn.close()
            
            threads = []
            for row in rows:
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                threads.append({
                    "id": row["id"],
                    "name": row["name"] or "Untitled",
                    "userId": row["user_id"],
                    "createdAt": row["created_at"],
                    "metadata": metadata
                })
            
            return {
                "data": threads,
                "pageInfo": {
                    "hasNextPage": False,
                    "endCursor": None
                }
            }
        
        return await asyncio.to_thread(_list_sync)
    
    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        """Lấy 1 thread cụ thể"""
        def _get_sync():
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM threads WHERE id = ?", (thread_id,))
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}
            return ThreadDict(
                id=row["id"],
                name=row["name"],
                userId=row["user_id"],
                createdAt=row["created_at"],
                metadata=metadata
            )
        
        return await asyncio.to_thread(_get_sync)
    
    async def create_thread(
        self,
        thread: ThreadDict
    ) -> ThreadDict:
        """Tạo thread mới"""
        def _create_sync():
            conn = self._get_conn()
            cursor = conn.cursor()
            
            metadata_json = json.dumps(thread.get("metadata", {}))
            
            cursor.execute(
                "INSERT OR REPLACE INTO threads (id, name, user_id, metadata) VALUES (?, ?, ?, ?)",
                (thread["id"], thread.get("name", "Untitled"), thread.get("userId"), metadata_json)
            )
            conn.commit()
            conn.close()
            
            print(f"✅ [DataLayer] Created thread: {thread['id']}")
            return thread
        
        return await asyncio.to_thread(_create_sync)
    
    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None
    ):
        """Cập nhật thread"""
        def _update_sync():
            conn = self._get_conn()
            cursor = conn.cursor()
            
            updates = []
            params = []
            
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            
            if user_id is not None:
                updates.append("user_id = ?")
                params.append(user_id)
            
            if metadata is not None:
                updates.append("metadata = ?")
                params.append(json.dumps(metadata))
            
            if updates:
                params.append(thread_id)
                sql = f"UPDATE threads SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(sql, params)
                conn.commit()
            
            conn.close()
        
        await asyncio.to_thread(_update_sync)
    
    async def delete_thread(self, thread_id: str):
        """Xóa thread"""
        def _delete_sync():
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
            cursor.execute("DELETE FROM steps WHERE thread_id = ?", (thread_id,))
            conn.commit()
            conn.close()
        
        await asyncio.to_thread(_delete_sync)
    
    async def create_step(self, step_dict: StepDict):
        """Lưu message (step)"""
        def _create_sync():
            conn = self._get_conn()
            cursor = conn.cursor()
            
            metadata_json = json.dumps(step_dict.get("metadata", {}))
            
            cursor.execute(
                """
                INSERT OR REPLACE INTO steps 
                (id, thread_id, parent_id, name, type, input, output, metadata) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    step_dict["id"],
                    step_dict.get("threadId"),
                    step_dict.get("parentId"),
                    step_dict.get("name", ""),
                    step_dict.get("type", "user_message"),
                    step_dict.get("input", ""),
                    step_dict.get("output", ""),
                    metadata_json
                )
            )
            conn.commit()
            conn.close()
        
        await asyncio.to_thread(_create_sync)
    
    async def get_thread_author(self, thread_id: str) -> str:
        """Lấy author của thread"""
        thread = await self.get_thread(thread_id)
        return thread["userId"] if thread else ""
    
    async def delete_feedback(self, feedback: DeleteFeedbackDict):
        """Xóa feedback (không dùng)"""
        pass
    
    async def upsert_feedback(self, feedback: FeedbackDict):
        """Lưu feedback (không dùng)"""
        pass
    
    # =========================================================
    # ABSTRACT METHODS MỚI (Chainlit 2.x+)
    # =========================================================
    
    async def update_step(self, step_dict: StepDict):
        """Cập nhật step (dùng create_step)"""
        await self.create_step(step_dict)
    
    async def delete_step(self, step_id: str):
        """Xóa step"""
        def _delete_sync():
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM steps WHERE id = ?", (step_id,))
            conn.commit()
            conn.close()
        await asyncio.to_thread(_delete_sync)
    
    async def get_element(self, thread_id: str, element_id: str) -> Optional[Dict]:
        """Lấy element (không implement - trả về None)"""
        return None
    
    async def create_element(self, element: Dict):
        """Tạo element (không implement)"""
        pass
    
    async def delete_element(self, element_id: str):
        """Xóa element (không implement)"""
        pass
    
    def build_debug_url(self) -> str:
        """Build debug URL (trả về empty)"""
        return ""
