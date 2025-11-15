# api_server.py
# Mini HTTP API Server để xử lý DELETE/EDIT từ CustomElements
# Chạy song song với Chainlit trên port 8001

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sqlite3

app = Flask(__name__)
CORS(app)  # Cho phép CORS để CustomElement có thể gọi

# Cấu hình (phải giống app.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_FILES_DIR = os.path.join(BASE_DIR, "public", "files")

def get_vectorstore_connection():
    """Kết nối tới ChromaDB (SQLite backend)"""
    # Sửa đường dẫn này cho đúng với cấu trúc của bạn
    db_path = os.path.join(BASE_DIR, "user_data", "shared_vector_db", "chroma.sqlite3")
    return sqlite3.connect(db_path)

@app.route('/api/delete-file', methods=['POST'])
def delete_file():
    """API để xóa file từ CustomElement"""
    try:
        data = request.json
        doc_id = data.get('doc_id')
        file_path = data.get('file_path')
        
        if not doc_id or not file_path:
            return jsonify({"error": "Missing doc_id or file_path"}), 400
        
        # 1. Xóa metadata từ vectorstore
        try:
            conn = get_vectorstore_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM embeddings WHERE id = ?", (doc_id,))
            conn.commit()
            conn.close()
            print(f"✅ [API] Đã xóa metadata: {doc_id}")
        except Exception as e:
            print(f"⚠️ [API] Lỗi xóa metadata: {e}")
        
        # 2. Xóa file trên disk
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"✅ [API] Đã xóa file: {file_path}")
        except Exception as e:
            print(f"⚠️ [API] Lỗi xóa file: {e}")
        
        return jsonify({"success": True, "message": "Đã xóa thành công"})
        
    except Exception as e:
        print(f"❌ [API] Lỗi delete_file: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/edit-file', methods=['POST'])
def edit_file():
    """API để sửa tên/note của file"""
    try:
        data = request.json
        doc_id = data.get('doc_id')
        new_name = data.get('new_name')
        new_note = data.get('new_note')
        
        if not doc_id:
            return jsonify({"error": "Missing doc_id"}), 400
        
        # Cập nhật metadata trong vectorstore
        # (Logic này phức tạp hơn, cần update content trong ChromaDB)
        # Tạm thời return success
        
        return jsonify({"success": True, "message": "Đã cập nhật (chức năng đang phát triển)"})
        
    except Exception as e:
        print(f"❌ [API] Lỗi edit_file: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/download-file', methods=['GET'])
def download_file():
    """API để tải file gốc (không bị zip)"""
    try:
        file_path = request.args.get('file_path')
        filename_param = request.args.get('filename')  # optional: original filename from client
        
        # DEBUG: In ra để kiểm tra
        print(f"[DEBUG Download] Received file_path: {file_path}")
        print(f"[DEBUG Download] File exists: {os.path.exists(file_path) if file_path else 'None'}")
        
        if not file_path or not os.path.exists(file_path):
            print(f"[DEBUG Download] ERROR: File not found or path is None")
            return jsonify({"error": "File not found"}), 404
        
        # Lấy tên file gốc (ưu tiên tên gốc truyền lên nếu có)
        filename = filename_param or os.path.basename(file_path)
        
        # Detect mimetype
        import mimetypes
        mimetype, _ = mimetypes.guess_type(filename)
        if not mimetype:
            mimetype = 'application/octet-stream'
        
        # Stream file trực tiếp về browser với mimetype đúng
        from flask import send_file
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
        
    except Exception as e:
        print(f"❌ [API] Lỗi download_file: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    print("🚀 API Server đang chạy trên http://localhost:8001")
    print("   - DELETE: POST /api/delete-file")
    print("   - EDIT:   POST /api/edit-file")
    app.run(host='0.0.0.0', port=8001, debug=False)
