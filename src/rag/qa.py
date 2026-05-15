from langchain_community.llms import Tongyi
from langchain_classic.chains import RetrievalQA
from langchain_classic.prompts import PromptTemplate
from src.shared.config import DASHSCOPE_API_KEY, LLM_MODEL, RETRIEVAL_TOP_K, SYSTEM_PROMPT


def create_qa_chain(vectorstore):
    """基于 FAISS vectorstore 创建 RAG QA chain。"""
    llm = Tongyi(
        model=LLM_MODEL,
        dashscope_api_key=DASHSCOPE_API_KEY,
        temperature=0.7,
    )

    retriever = vectorstore.as_retriever(
        search_kwargs={"k": RETRIEVAL_TOP_K}
    )

    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template=(
            SYSTEM_PROMPT +
            "\n\n参考资料：\n{context}\n\n"
            "用户问题：{question}\n\n"
            "请回答（如果引用了资料中的建议，请标注来源书名）："
        ),
    )

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": prompt},
    )

    return qa_chain


def ask(question: str, qa_chain) -> dict:
    """提问并返回答案。"""
    result = qa_chain.invoke({"query": question})
    return {
        "answer": result["result"],
        "sources": list(set(
            doc.metadata.get("source", "未知")
            for doc in result.get("source_documents", [])
        )),
    }
