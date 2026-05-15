import os
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from src.shared.config import BOOKS_DIR, CHUNK_SIZE, CHUNK_OVERLAP


def _load_epub(filepath: str) -> list[Document]:
    """使用 ebooklib 解析 EPUB 文件为 Document 列表。"""
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup

    book = epub.read_epub(filepath)
    docs = []
    title = os.path.basename(filepath).rsplit(".", 1)[0]

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text(strip=True)
        if not text or len(text) < 50:
            continue
        doc = Document(
            page_content=text,
            metadata={"source": os.path.basename(filepath), "title": title},
        )
        docs.append(doc)

    if not docs:
        raise ValueError("EPUB 中未找到可提取的文本内容")
    return docs


def _load_pdf(filepath: str) -> list[Document]:
    loader = PyPDFLoader(filepath)
    return loader.load()


def _load_txt(filepath: str) -> list[Document]:
    loader = TextLoader(filepath, encoding="utf-8")
    return loader.load()


LOADERS = {
    ".pdf": _load_pdf,
    ".epub": _load_epub,
    ".txt": _load_txt,
}


def load_documents(books_dir: str | None = None):
    """从目录加载所有支持的文件，切分为 chunk 后返回。

    支持格式: PDF, EPUB, TXT
    """
    if books_dir is None:
        books_dir = BOOKS_DIR

    if not os.path.exists(books_dir):
        raise FileNotFoundError(f"书籍目录不存在: {books_dir}")

    files = [f for f in os.listdir(books_dir)
             if not f.startswith(".")]
    supported = [f for f in files
                 if os.path.splitext(f)[1].lower() in LOADERS]

    if not supported:
        raise FileNotFoundError(f"目录中未找到支持的文件 (PDF/EPUB/TXT): {books_dir}")

    print(f"找到 {len(supported)} 个文件")
    for f in files:
        if f not in supported:
            print(f"  跳过（不支持的格式）: {f}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "！", "？", "；", ".", " ", ""],
    )

    all_docs = []
    for fname in sorted(supported):
        fpath = os.path.join(books_dir, fname)
        ext = os.path.splitext(fname)[1].lower()
        print(f"  加载: {fname}")
        try:
            docs = LOADERS[ext](fpath)
            for doc in docs:
                doc.metadata["source"] = fname
            chunks = splitter.split_documents(docs)
            all_docs.extend(chunks)
            print(f"    → {len(chunks)} 个 chunk")
        except Exception as e:
            print(f"    ✗ 加载失败: {e}")

    print(f"\n总计: {len(all_docs)} 个 chunk")
    return all_docs
