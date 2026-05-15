"""一次性构建 FAISS 索引。将 PDF 放入 data/books/ 后运行此脚本。"""
from src.rag.loader import load_documents
from src.rag.embedder import build_index


def main():
    print("=" * 50)
    print("开始构建知识库索引")
    print("=" * 50)
    docs = load_documents()
    build_index(docs)
    print("\n索引构建完成，可以运行 app.py 了")


if __name__ == "__main__":
    main()
