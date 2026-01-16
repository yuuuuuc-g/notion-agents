import os
import shutil


def cleanup():
    # 定义需要清理的文件和目录
    targets = {"dir": ["chroma_db"], "file": ["doc_store.db"]}

    print("🧹 Starting Exocortex Database Cleanup...")

    # 1. 清理向量数据库目录
    for d in targets["dir"]:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"✅ Deleted directory: {d}")
        else:
            print(f"ℹ️ Directory not found, skipping: {d}")

    # 2. 清理 SQLite 文档存储文件
    for f in targets["file"]:
        if os.path.exists(f):
            os.remove(f)
            print(f"✅ Deleted file: {f}")
        else:
            print(f"ℹ️ File not found, skipping: {f}")

    print("\n✨ Cleanup Complete! Your local index is now fresh.")
    print("🚀 Run 'python server.py' to rebuild a clean database.")


if __name__ == "__main__":
    cleanup()
