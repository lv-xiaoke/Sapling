"""从知识库中自动提取适合制作幼儿视频的教育主题"""

import json
import os
import re

from langchain_community.llms import Tongyi

from src.shared.config import DASHSCOPE_API_KEY, LLM_MODEL, RETRIEVAL_TOP_K

SEED_QUERIES = [
    "幼儿习惯培养 刷牙 洗手 作息",
    "幼儿情绪管理 生气 害怕 分离焦虑",
    "幼儿社交技能 分享 排队 道歉",
    "幼儿安全教育 交通安全 陌生人",
    "幼儿生活自理 穿衣 吃饭 收玩具",
    "幼儿品格培养 诚实 勇敢 坚持",
]

TOPIC_EXTRACTION_PROMPT = """你是一个幼儿教育内容策划。下面是一些育儿书籍的片段，请从中提取出适合制作成 3-5 岁幼儿讲解视频的具体知识点。

要求：
1. 每个知识点是一个具体的、孩子能理解的小道理（如"为什么要刷牙"、"生气时怎么办"，而不是家长教育建议）
2. 每个知识点包含：标题（10字以内，孩子视角）、分类（如"习惯培养"）、一句话简介
3. 只提取书中确实讨论过的内容，不要编造
4. 输出 5-10 个知识点

## 书籍片段
{book_excerpts}

## 输出格式
严格按以下 JSON 格式输出，不要包含任何其他文字：

```json
{{
  "topics": [
    {{
      "title": "为什么要刷牙",
      "category": "习惯培养",
      "summary": "让小朋友理解刷牙的重要性，学会保护牙齿"
    }}
  ]
}}
```"""


def extract_topics(vectorstore, cache_path: str | None = None) -> list[dict]:
    """从知识库中提取视频主题列表。

    Args:
        vectorstore: FAISS vectorstore
        cache_path: 缓存 JSON 文件路径，存在则直接读取

    Returns:
        [{"title": "...", "category": "...", "summary": "..."}, ...]
    """
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    all_chunks = []
    seen = set()
    for query in SEED_QUERIES:
        try:
            docs = vectorstore.similarity_search(query, k=RETRIEVAL_TOP_K)
            for d in docs:
                text = d.page_content.strip()
                if text not in seen and len(text) > 50:
                    seen.add(text)
                    all_chunks.append(text)
        except Exception as e:
            print(f"检索 '{query[:20]}...' 失败: {e}")

    if not all_chunks:
        return _default_topics()

    excerpts = "\n\n---\n\n".join(
        f"[{i+1}] {chunk[:300]}" for i, chunk in enumerate(all_chunks[:20])
    )

    llm = Tongyi(
        model=LLM_MODEL,
        dashscope_api_key=DASHSCOPE_API_KEY,
        temperature=0.6,
    )

    prompt = TOPIC_EXTRACTION_PROMPT.format(book_excerpts=excerpts)

    print("正在从知识库提取视频主题...")
    raw = llm.invoke(prompt)

    try:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
        if match:
            raw = match.group(1)
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            raw = match.group(0)
        result = json.loads(raw)
        topics = result.get("topics", [])
        if topics:
            print(f"提取到 {len(topics)} 个视频主题")
            if cache_path:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(topics, f, ensure_ascii=False, indent=2)
            return topics
    except (json.JSONDecodeError, AttributeError) as e:
        print(f"主题提取 JSON 解析失败: {e}")

    return _default_topics()


def _default_topics() -> list[dict]:
    return [
        {"title": "为什么要刷牙", "category": "习惯培养", "summary": "让小朋友理解刷牙的重要性"},
        {"title": "生气时怎么办", "category": "情绪管理", "summary": "教孩子认识和表达愤怒情绪"},
        {"title": "学会说对不起", "category": "社交技能", "summary": "理解道歉的意义"},
        {"title": "过马路要小心", "category": "安全教育", "summary": "基本的交通安全意识"},
        {"title": "自己的事情自己做", "category": "生活自理", "summary": "培养独立性"},
        {"title": "勇敢说出心里话", "category": "品格培养", "summary": "鼓励孩子表达自己"},
        {"title": "分享的快乐", "category": "社交技能", "summary": "理解分享的意义"},
        {"title": "早睡早起身体好", "category": "习惯培养", "summary": "建立良好作息"},
    ]
