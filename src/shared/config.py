import os
from dotenv import load_dotenv

load_dotenv()

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

LLM_MODEL = "qwen-plus"
EMBEDDING_MODEL = "text-embedding-v2"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 200
RETRIEVAL_TOP_K = 5

BOOKS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "books")
FAISS_INDEX_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "faiss_index")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "output")

SYSTEM_PROMPT = """你是一个专业的3-5岁幼儿教育顾问。请基于提供的育儿书籍资料回答问题。

规则：
1. 优先使用提供的资料内容回答，引用资料中的具体建议
2. 如果资料中找不到相关信息，诚实说明"当前知识库中未找到相关内容"，然后可以结合你的通用育儿知识提供参考建议
3. 回答要具体、可操作，适合3-5岁幼儿的家长理解和执行
4. 中文回答，语气温和专业"""

# --- 视频生成子系统配置 ---
IMAGE_MODEL = "wanx-v1"
IMAGE_SIZE = "1024*1024"
TTS_VOICE = "zh-CN-XiaoxiaoNeural"
VIDEO_FPS = 30
VIDEO_RESOLUTION = (1024, 1024)
VIDEO_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "videos")
