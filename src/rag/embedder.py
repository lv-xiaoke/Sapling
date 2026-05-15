import os
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import FAISS
from src.shared.config import DASHSCOPE_API_KEY, EMBEDDING_MODEL, FAISS_INDEX_DIR


def get_embeddings():
    return DashScopeEmbeddings(
        model=EMBEDDING_MODEL,
        dashscope_api_key=DASHSCOPE_API_KEY,
    )


def build_index(documents, save_path: str | None = None):
    """构建 FAISS 索引并持久化。"""
    if save_path is None:
        save_path = FAISS_INDEX_DIR

    embeddings = get_embeddings()
    print(f"正在为 {len(documents)} 个文档块生成向量...")
    vectorstore = FAISS.from_documents(documents, embeddings)
    os.makedirs(save_path, exist_ok=True)
    vectorstore.save_local(save_path)
    print(f"索引已保存到: {save_path}")
    return vectorstore


def load_index(load_path: str | None = None):
    """从本地加载已持久化的 FAISS 索引。"""
    if load_path is None:
        load_path = FAISS_INDEX_DIR

    index_file = os.path.join(load_path, "index.faiss")
    if not os.path.exists(index_file):
        return None

    embeddings = get_embeddings()
    vectorstore = FAISS.load_local(
        load_path, embeddings, allow_dangerous_deserialization=True
    )
    print(f"从 {load_path} 加载了已有索引")
    return vectorstore


def get_or_create_index(documents=None, force_rebuild=False):
    """获取已有索引，如果不存在或强制重建则新建。"""
    if not force_rebuild:
        existing = load_index()
        if existing is not None:
            return existing

    if documents is None:
        raise ValueError("索引不存在，需要提供 documents 参数来构建")

    return build_index(documents)
