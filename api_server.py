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
    """API để tải file gốc (không bị zip) - SỬA LỖI: Xử lý khi file_path là thư mục"""
    try:
        file_path = request.args.get('file_path')
        filename_param = request.args.get('filename')  # optional: original filename from client 
        
        # DEBUG: In ra để kiểm tra
        print(f"\n[DEBUG Download] ========== START ==========")
        print(f"[DEBUG Download] Received file_path: '{file_path}'")
        print(f"[DEBUG Download] Received filename: '{filename_param}'")
        
        if not file_path:
            print(f"[DEBUG Download] ERROR: file_path is None or empty")
            return jsonify({"error": "file_path parameter is missing"}), 400
        
        # ===== SỬA LỖI: XỬ LÝ KHI file_path LÀ THƯ MỤC HOẶC FILE KHÔNG TỒN TẠI =====
        # Chuẩn hóa đường dẫn (chuyển / thành \ trên Windows)
        file_path = os.path.normpath(file_path)
        print(f"[DEBUG Download] Normalized file_path: '{file_path}'")
        
        if os.path.isdir(file_path):
            print(f"[DEBUG Download] WARNING: file_path is a DIRECTORY: '{file_path}'")
            print(f"[DEBUG Download] Trying to find file in public/files using filename: '{filename_param}'")
            
            # Nếu file_path là thư mục, tìm file trong thư mục public/files
            # bằng cách dùng filename_param
            if filename_param:
                # Thử tìm file trong PUBLIC_FILES_DIR
                potential_path = os.path.join(PUBLIC_FILES_DIR, filename_param)
                print(f"[DEBUG Download] Checking potential path: '{potential_path}'")
                
                if os.path.isfile(potential_path):
                    print(f"[DEBUG Download] Found file at: '{potential_path}'")
                    file_path = potential_path
                else:
                    # Thử tìm file có tên tương tự trong PUBLIC_FILES_DIR
                    print(f"[DEBUG Download] Searching for similar files in PUBLIC_FILES_DIR...")
                    found = False
                    for f in os.listdir(PUBLIC_FILES_DIR):
                        if filename_param.lower() in f.lower():
                            file_path = os.path.join(PUBLIC_FILES_DIR, f)
                            print(f"[DEBUG Download] Found similar file: '{file_path}'")
                            found = True
                            break
                    
                    if not found:
                        print(f"[DEBUG Download] ERROR: Could not find file in PUBLIC_FILES_DIR")
                        return jsonify({
                            "error": f"Path is a directory and could not find file: {filename_param}"
                        }), 400
            else:
                print(f"[DEBUG Download] ERROR: Path is a directory and no filename provided")
                return jsonify({"error": f"Path is a directory: {file_path}"}), 400
        
        # Kiểm tra xem file có tồn tại không, nếu không thì tìm trong PUBLIC_FILES_DIR
        if not os.path.exists(file_path):
            print(f"[DEBUG Download] WARNING: File does not exist at: '{file_path}'")
            if filename_param:
                # Lấy chỉ tên file từ file_path (bỏ đường dẫn)
                basename = os.path.basename(file_path)
                potential_path = os.path.join(PUBLIC_FILES_DIR, basename)
                print(f"[DEBUG Download] Trying with basename in PUBLIC_FILES_DIR: '{potential_path}'")
                
                if os.path.isfile(potential_path):
                    print(f"[DEBUG Download] Found file at: '{potential_path}'")
                    file_path = potential_path
                else:
                    print(f"[DEBUG Download] File still not found. Searching for similar files...")
                    found = False
                    for f in os.listdir(PUBLIC_FILES_DIR):
                        if basename.lower() in f.lower() or filename_param.lower() in f.lower():
                            file_path = os.path.join(PUBLIC_FILES_DIR, f)
                            print(f"[DEBUG Download] Found similar file: '{file_path}'")
                            found = True
                            break
                    
                    if not found:
                        print(f"[DEBUG Download] ERROR: Could not find file anywhere")
                        return jsonify({"error": f"File not found: {file_path}"}), 404
        # ===== KẾT THÚC SỬA LỖI =====
        
        print(f"[DEBUG Download] Final file_path: '{file_path}'")
        print(f"[DEBUG Download] File exists: {os.path.exists(file_path)}")
        print(f"[DEBUG Download] Is file: {os.path.isfile(file_path)}")
            
        if not os.path.exists(file_path):
            print(f"[DEBUG Download] ERROR: File not found at: {file_path}")
            return jsonify({"error": f"File not found: {file_path}"}), 404
            
        if not os.path.isfile(file_path):
            print(f"[DEBUG Download] ERROR: Path is not a file!")
            return jsonify({"error": f"Path is not a file: {file_path}"}), 400
        
        # Lấy tên file gốc (ưu tiên tên gốc truyền lên nếu có)
        filename = filename_param or os.path.basename(file_path)
        
        # ===== SỬA LỖI: THÊM EXTENSION VÀO FILENAME =====
        # Nếu filename không có extension, lấy từ file_path
        if filename and '.' not in filename:
            ext = os.path.splitext(file_path)[1]
            if ext:
                filename = filename + ext
                print(f"[DEBUG Download] Added extension: '{ext}' to filename")
        
        print(f"[DEBUG Download] Final filename: '{filename}'")
        
        # Detect mimetype
        import mimetypes
        mimetype, _ = mimetypes.guess_type(filename)
        if not mimetype:
            mimetype = 'application/octet-stream'
        
        print(f"[DEBUG Download] Mimetype: {mimetype}")
        print(f"[DEBUG Download] Sending file...")
        
        # Stream file trực tiếp về browser với mimetype đúng
        from flask import send_file
        result = send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
        
        print(f"[DEBUG Download] ========== SUCCESS ==========\n")
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
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
