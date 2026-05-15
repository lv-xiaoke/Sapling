"""故事脚本生成 — LLM 结构化分镜输出"""

import json
import re

from langchain_community.llms import Tongyi

from src.shared.config import DASHSCOPE_API_KEY, LLM_MODEL, RETRIEVAL_TOP_K
from src.rag.embedder import load_index


STYLE_DIRECTIVE = (
    "cute illustration for 3-5 year olds, soft pastel colors, simple shapes, "
    "children's picture book style, warm and friendly"
)

CHARACTER_APPEARANCE = (
    "a cute young child with round face, big sparkling eyes, "
    "wearing colorful clothes, cartoon style, consistent appearance"
)

SCRIPT_PROMPT = """你是一个专业的儿童故事创作者，专门为3-5岁幼儿编写故事绘本脚本。

请根据以下信息创作一个故事：

- 孩子名字：{child_name}
- 年龄：{age}岁
- 故事主题：{theme}
- 教育目标：{educational_goal}

{reference_section}

## 创作要求
1. 故事分为 5-8 个场景，每个场景包含画面描述和旁白文字
2. 画面描述用英文写（用于 AI 生成图片），必须始终以 "{style}" 开头，主角固定描述为 "{character}"
3. 旁白用中文写，每个场景 20-50 字，语言简单朗朗上口
4. 故事有趣、温暖，融入教育目标（寓教于乐）
5. 适合 {age} 岁幼儿理解

## 输出格式
严格按以下 JSON 格式输出，不要包含任何其他文字：

```json
{{
  "title": "故事标题（中文）",
  "scenes": [
    {{
      "image_prompt": "英文画面描述",
      "narration": "中文旁白文字"
    }}
  ]
}}
```"""


def _format_script_for_display(script: dict) -> str:
    """将脚本转为可读的 Markdown 字符串。"""
    lines = [f"## {script.get('title', '未命名故事')}\n"]
    for i, scene in enumerate(script["scenes"], 1):
        lines.append(f"### 场景 {i}")
        lines.append(f"**旁白：**{scene['narration']}")
        lines.append("")
    return "\n".join(lines)


def _parse_llm_output(text: str) -> dict:
    """从 LLM 输出中提取 JSON。处理可能的 markdown 代码块包裹。"""
    # 尝试匹配 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1)

    # 尝试匹配第一个 { 到最后一个 }
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        text = match.group(0)

    return json.loads(text)


def _enforce_style_prompts(script: dict) -> dict:
    """确保每个场景的 image_prompt 都包含统一的风格描述。"""
    for scene in script["scenes"]:
        prompt = scene["image_prompt"]
        if STYLE_DIRECTIVE not in prompt:
            scene["image_prompt"] = f"{STYLE_DIRECTIVE}, {CHARACTER_APPEARANCE}, {prompt}"
    return script


def generate_script(
    child_name: str,
    age: int,
    theme: str,
    educational_goal: str,
    vectorstore=None,
) -> dict:
    """生成结构化分镜脚本。

    Args:
        child_name: 孩子名字
        age: 年龄 (3-5)
        theme: 故事主题
        educational_goal: 教育目标
        vectorstore: FAISS vectorstore (可选)，提供则检索参考资料

    Returns:
        {"title": "...", "scenes": [{"image_prompt": "...", "narration": "..."}]}
    """
    # 从知识库检索参考资料
    reference_section = ""
    if vectorstore is not None:
        try:
            query = f"{theme} {educational_goal} 3-{age}岁幼儿教育"
            docs = vectorstore.similarity_search(query, k=RETRIEVAL_TOP_K)
            if docs:
                refs = "\n".join(
                    f"- {d.page_content[:200]}..." for d in docs
                )
                reference_section = f"## 参考资料（来自育儿书籍）\n{refs}\n"
        except Exception as e:
            print(f"知识库检索失败（将继续生成脚本）: {e}")

    llm = Tongyi(
        model=LLM_MODEL,
        dashscope_api_key=DASHSCOPE_API_KEY,
        temperature=0.8,
    )

    prompt = SCRIPT_PROMPT.format(
        child_name=child_name,
        age=age,
        theme=theme,
        educational_goal=educational_goal or "培养良好的行为习惯",
        reference_section=reference_section,
        style=STYLE_DIRECTIVE,
        character=CHARACTER_APPEARANCE,
    )

    print("正在生成故事脚本...")
    raw = llm.invoke(prompt)

    try:
        script = _parse_llm_output(raw)
    except (json.JSONDecodeError, AttributeError) as e:
        # 退化方案：认知类内容
        print(f"JSON 解析失败 ({e})，使用认知类退化方案")
        script = {
            "title": f"{child_name}的学习小课堂",
            "scenes": _fallback_cognitive_scenes(theme, educational_goal),
        }

    if not isinstance(script.get("scenes"), list) or len(script["scenes"]) < 3:
        print("场景数量不足，使用认知类退化方案")
        script = {
            "title": f"{child_name}的学习小课堂",
            "scenes": _fallback_cognitive_scenes(theme, educational_goal),
        }

    script = _enforce_style_prompts(script)
    print(f"脚本生成完成: {script.get('title')} ({len(script['scenes'])} 个场景)")
    return script


def _fallback_cognitive_scenes(theme: str, educational_goal: str) -> list[dict]:
    """认知类退化脚本 — 动物/颜色/数字主题。"""
    topic = theme or "有趣的动物"
    goal = educational_goal or "认识世界"

    scenes = [
        {
            "image_prompt": (
                f"{STYLE_DIRECTIVE}, {CHARACTER_APPEARANCE}, "
                "a happy child waving hello, bright sunny day, green meadow with flowers"
            ),
            "narration": f"嗨，小朋友！今天我们来认识{topic}吧！",
        },
        {
            "image_prompt": (
                f"{STYLE_DIRECTIVE}, cute red apple, blue sky, green tree, "
                "simple shapes, educational illustration"
            ),
            "narration": f"看，这是一个红红的大苹果，圆圆的真可爱。",
        },
        {
            "image_prompt": (
                f"{STYLE_DIRECTIVE}, two adorable yellow ducklings swimming in a pond, "
                "sparkling water, friendly animals"
            ),
            "narration": f"一二，两只小黄鸭在水里游来游去。",
        },
        {
            "image_prompt": (
                f"{STYLE_DIRECTIVE}, three colorful balloons, red blue yellow, "
                "floating in the sky with white clouds"
            ),
            "narration": f"一二三，三个彩色气球飞上了蓝天。",
        },
        {
            "image_prompt": (
                f"{STYLE_DIRECTIVE}, {CHARACTER_APPEARANCE}, "
                "the child clapping hands happily, rainbow in background"
            ),
            "narration": f"小朋友，你真棒！{goal}让我们一起快乐成长！",
        },
    ]
    return scenes
