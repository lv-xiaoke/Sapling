"""知识讲解视频脚本生成 — 将育儿知识转化为幼儿能理解的讲解视频"""

import json
import re

from langchain_community.llms import Tongyi

from src.shared.config import DASHSCOPE_API_KEY, LLM_MODEL, RETRIEVAL_TOP_K
from src.video.script import STYLE_DIRECTIVE, CHARACTER_APPEARANCE, _enforce_style_prompts

KNOWLEDGE_SCRIPT_PROMPT = """你是一个幼儿教育内容创作者，专门为 3-5 岁小朋友制作知识讲解视频。

请把下面这个话题，用小朋友能理解的方式讲解出来：

- 话题标题：{topic_title}
- 话题分类：{topic_category}
- 话题简介：{topic_summary}
- 小朋友名字：{child_name}
- 小朋友年龄：{age}岁

{reference_section}

## 创作要求

这不是一个故事，而是一个**知识讲解视频**。你要像一个亲切的老师，用简单的话向小朋友解释一个道理。

1. 分为 5-8 个场景，每个场景讲清楚一个点
2. 画面描述用英文写（用于 AI 生成图片），必须始终以 "{style}" 开头，主角固定描述为 "{character}"。画面要配合讲解内容，用具体的场景图来帮助孩子理解
3. 旁白用中文写，每个场景 20-50 字。语气亲切、简单、朗朗上口，像在和小朋友对话
4. 讲解要具体，多举孩子生活中的例子，不要说教
5. 结尾要有鼓励和总结

## 输出格式
严格按以下 JSON 格式输出，不要包含任何其他文字：

```json
{{
  "title": "视频标题（中文，10字以内）",
  "scenes": [
    {{
      "image_prompt": "英文画面描述",
      "narration": "中文讲解文字"
    }}
  ]
}}
```"""


def generate_knowledge_script(
    topic: dict,
    child_name: str,
    age: int,
    vectorstore=None,
) -> dict:
    """根据知识库主题生成知识讲解视频脚本。

    Args:
        topic: {{"title": "...", "category": "...", "summary": "..."}}
        child_name: 孩子名字
        age: 年龄 (3-5)
        vectorstore: FAISS vectorstore (可选)

    Returns:
        {{"title": "...", "scenes": [{{"image_prompt": "...", "narration": "..."}}]}}
    """
    reference_section = ""
    if vectorstore is not None:
        try:
            query = f"{topic['title']} {topic['category']} 3-{age}岁幼儿教育 具体方法"
            docs = vectorstore.similarity_search(query, k=RETRIEVAL_TOP_K)
            if docs:
                refs = "\n".join(
                    f"- {d.page_content[:250]}" for d in docs
                )
                reference_section = f"## 参考资料（来自育儿书籍）\n{refs}\n"
        except Exception as e:
            print(f"知识库检索失败（将继续生成脚本）: {e}")

    llm = Tongyi(
        model=LLM_MODEL,
        dashscope_api_key=DASHSCOPE_API_KEY,
        temperature=0.7,
    )

    prompt = KNOWLEDGE_SCRIPT_PROMPT.format(
        topic_title=topic["title"],
        topic_category=topic.get("category", ""),
        topic_summary=topic.get("summary", topic["title"]),
        child_name=child_name,
        age=age,
        reference_section=reference_section,
        style=STYLE_DIRECTIVE,
        character=CHARACTER_APPEARANCE,
    )

    print(f"正在生成知识讲解脚本: {topic['title']}")
    raw = llm.invoke(prompt)

    try:
        script = _parse_llm_output(raw)
    except (json.JSONDecodeError, AttributeError) as e:
        print(f"JSON 解析失败 ({e})，使用退化方案")
        script = {
            "title": topic["title"],
            "scenes": _fallback_knowledge_scenes(topic),
        }

    if not isinstance(script.get("scenes"), list) or len(script["scenes"]) < 3:
        print("场景数量不足，使用退化方案")
        script = {
            "title": topic["title"],
            "scenes": _fallback_knowledge_scenes(topic),
        }

    script = _enforce_style_prompts(script)
    print(f"知识脚本生成完成: {script.get('title')} ({len(script['scenes'])} 个场景)")
    return script


def _parse_llm_output(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1)
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        text = match.group(0)
    return json.loads(text)


def _fallback_knowledge_scenes(topic: dict) -> list[dict]:
    title = topic.get("title", "一个小知识")
    return [
        {
            "image_prompt": (
                f"{STYLE_DIRECTIVE}, {CHARACTER_APPEARANCE}, "
                "a happy child waving hello, bright sunny day, green meadow"
            ),
            "narration": f"嗨，小朋友！今天我们来聊一聊「{title}」。",
        },
        {
            "image_prompt": (
                f"{STYLE_DIRECTIVE}, {CHARACTER_APPEARANCE}, "
                "child looking curious, thinking pose, question mark above head, colorful background"
            ),
            "narration": f"你有没有想过，{title}是什么意思呢？",
        },
        {
            "image_prompt": (
                f"{STYLE_DIRECTIVE}, {CHARACTER_APPEARANCE}, "
                "child and parent talking happily, warm home setting, cozy atmosphere"
            ),
            "narration": f"让我们一起来看看，{title}的小秘密吧！",
        },
        {
            "image_prompt": (
                f"{STYLE_DIRECTIVE}, {CHARACTER_APPEARANCE}, "
                "child doing a positive action, bright colors, happy expression"
            ),
            "narration": "只要我们每天坚持，就能做得越来越好！",
        },
        {
            "image_prompt": (
                f"{STYLE_DIRECTIVE}, {CHARACTER_APPEARANCE}, "
                "child clapping hands, rainbow and stars, celebration mood"
            ),
            "narration": "小朋友，你真棒！今天的知识你学会了吗？",
        },
    ]


def format_script_for_display(script: dict) -> str:
    lines = [f"## {script.get('title', '未命名')}\n"]
    for i, scene in enumerate(script["scenes"], 1):
        lines.append(f"### 场景 {i}")
        lines.append(f"**旁白：**{scene['narration']}")
        lines.append("")
    return "\n".join(lines)
