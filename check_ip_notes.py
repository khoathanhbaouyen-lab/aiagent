import chromadb
import json

client = chromadb.PersistentClient(path='./user_data/shared_vector_db')
coll = client.get_collection('shared_memory')

# Lấy tất cả ghi chú của user
results = coll.get(
    where={'user_id': 'onsm@oshima.vn'},
    include=['documents', 'metadatas']
)

print(f"Total text notes: {len(results['documents'])}")
print("\n" + "="*80)

# Tìm ghi chú có chứa IP 10.1.2.15 hoặc 10.1.2.200
for i, (doc, meta) in enumerate(zip(results['documents'], results['metadatas'])):
    if '10.1.2.15' in doc or '10.1.2.200' in doc:
        print(f"\n[NOTE {i+1}] ID: {results['ids'][i]}")
        print(f"Fact Key: {meta.get('fact_key', 'N/A')}")
        print(f"Has 10.1.2.15: {'10.1.2.15' in doc}")
        print(f"Has 10.1.2.200: {'10.1.2.200' in doc}")
        print(f"\nContent (first 800 chars):")
        print(doc[:800])
        print("\n" + "-"*80)
