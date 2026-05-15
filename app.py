"""教育 AI 助手 — Gradio 入口"""
import sys
import os

os.environ["NO_PROXY"] = "localhost,127.0.0.1,0.0.0.0"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gradio as gr
from src.rag.loader import load_documents
from src.rag.embedder import get_or_create_index
from src.rag.qa import create_qa_chain, ask

qa_chain = None


def init_qa_chain():
    global qa_chain
    if qa_chain is not None:
        return
    vectorstore = get_or_create_index()
    if vectorstore is None:
        print("未找到索引，正在从文档构建...")
        docs = load_documents()
        vectorstore = get_or_create_index(docs, force_rebuild=True)
    qa_chain = create_qa_chain(vectorstore)
    print("✓ QA 系统就绪")


def qa_handler(question, history):
    if not question.strip():
        return "请输入问题"
    init_qa_chain()
    result = ask(question, qa_chain)
    sources_text = "\n\n---\n**参考来源：**\n" + "\n".join(f"- {s}" for s in result["sources"])
    return result["answer"] + sources_text


def build_ui():
    with gr.Blocks(title="教育 AI 助手") as demo:
        gr.Markdown("# 📚 幼儿教育 AI 助手")
        gr.Markdown("基于育儿书籍知识库，为 3-5 岁幼儿家长提供专业建议")

        with gr.Tab("💬 教育问答"):
            gr.ChatInterface(
                fn=qa_handler,
                chatbot=gr.Chatbot(height=500),
                title="育儿知识问答",
                description="输入你关心的育儿问题，我来基于知识库给你建议",
                examples=[
                    "3岁孩子晚上不肯睡觉怎么办？",
                    "如何培养4岁孩子的阅读兴趣？",
                    "孩子发脾气时家长应该怎么应对？",
                    "3-5岁孩子每天需要多长时间的户外活动？",
                    "如何帮助孩子建立良好的饮食习惯？",
                ],
            )

        with gr.Tab("🎬 视频生成"):
            gr.Markdown("### 视频生成功能即将上线")
            gr.Markdown("输入孩子信息，自动生成个性化故事视频。敬请期待！")

    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, show_error=True)
