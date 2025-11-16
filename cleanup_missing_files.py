# cleanup_missing_files.py
# Script để xóa metadata của các file không còn tồn tại trên disk

import os
import sys
import re
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

# Load environment variables
load_dotenv()

# Cấu hình
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, "user_data", "shared_vector_db")
PUBLIC_FILES_DIR = os.path.join(BASE_DIR, "public", "files")

def cleanup_missing_files():
    """Xóa metadata của file không tồn tại"""
    
    print(f"📂 Connecting to ChromaDB at: {CHROMA_DIR}")
    
    # Initialize embeddings (needed for Chroma)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    # Initialize vectorstore
    vectorstore = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
        collection_name="shared_memory"
    )
    
    collection = vectorstore._collection
    
    # Lấy tất cả documents
    all_data = collection.get(include=["metadatas"])
    
    ids_to_delete = []
    total_files = 0
    missing_files = 0
    
    print(f"Đang quét {len(all_data['ids'])} documents...")
    
    for doc_id, metadata in zip(all_data['ids'], all_data['metadatas']):
        if not metadata:
            continue
            
        file_type = metadata.get("file_type")
        
        # Chỉ kiểm tra file/image (không phải text notes)
        if file_type in ["image", "file", "pdf", "excel", "word"]:
            total_files += 1
            
            # Parse file path từ original_content
            original_content = metadata.get("original_content", "")
            
            path_match = re.search(r"path=([^|]+)", original_content)
            
            if path_match:
                file_path = path_match.group(1).strip()
                
                # Kiểm tra file có tồn tại không
                if not os.path.exists(file_path):
                    print(f"❌ Missing: {file_path}")
                    ids_to_delete.append(doc_id)
                    missing_files += 1
    
    print(f"\n📊 Thống kê:")
    print(f"   - Tổng số file/ảnh: {total_files}")
    print(f"   - File không tồn tại: {missing_files}")
    print(f"   - File còn tồn tại: {total_files - missing_files}")
    
    if ids_to_delete:
        print(f"\n⚠️  Sẽ xóa {len(ids_to_delete)} metadata của file không tồn tại.")
        confirm = input("Xác nhận xóa? (y/n): ")
        
        if confirm.lower() == 'y':
            # Xóa theo batch (ChromaDB giới hạn batch size)
            batch_size = 100
            for i in range(0, len(ids_to_delete), batch_size):
                batch = ids_to_delete[i:i+batch_size]
                collection.delete(ids=batch)
                print(f"   Đã xóa {len(batch)} metadata...")
            
            print(f"✅ Đã xóa {len(ids_to_delete)} metadata!")
        else:
            print("❌ Hủy thao tác.")
    else:
        print("\n✅ Không có file nào bị missing. Database sạch!")

if __name__ == "__main__":
    cleanup_missing_files()
