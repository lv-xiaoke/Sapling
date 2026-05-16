"""教育 AI 助手 — Gradio 入口"""
import sys
import os
import time
import traceback
import socket
import subprocess

os.environ["NO_PROXY"] = "localhost,127.0.0.1,0.0.0.0"
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 补充 FFmpeg 可能的安装路径到 PATH（winget 安装不自动添加）
_ffmpeg_candidates = [
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"),
]
for _base in _ffmpeg_candidates:
    if os.path.isdir(_base):
        _versions = sorted(os.listdir(_base), reverse=True)
        for _v in _versions:
            _bin = os.path.join(_base, _v, "bin")
            if os.path.isdir(_bin):
                os.environ["PATH"] = _bin + os.pathsep + os.environ.get("PATH", "")
                break
        break

import warnings
warnings.filterwarnings("ignore")

import gradio as gr


def _free_port(port: int) -> None:
    """如果端口被占用，尝试释放它。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
        except OSError:
            pass
        else:
            return

    # 端口被占用，Windows 上杀掉占用进程
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    pid = line.strip().split()[-1]
                    subprocess.run(
                        ["taskkill", "/PID", pid, "/F"],
                        capture_output=True,
                    )
                    time.sleep(0.5)
                    print(f"[INFO] 已释放端口 {port}（PID={pid}）")
                    return
        except Exception:
            pass

    try:
        result = subprocess.run(
            ["fuser", "-k", f"{port}/tcp"], capture_output=True, text=True
        )
    except Exception:
        pass


from src.rag.loader import load_documents
from src.rag.embedder import get_or_create_index, load_index
from src.rag.qa import create_qa_chain, ask
from src.shared.config import VIDEO_OUTPUT_DIR, OUTPUT_DIR
from src.video.topic_extractor import extract_topics
from src.video.knowledge_script import generate_knowledge_script, format_script_for_display

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
    print("[OK] QA 系统就绪")


def qa_handler(question, history):
    if not question.strip():
        return "请输入问题"
    init_qa_chain()
    result = ask(question, qa_chain)
    sources_text = "\n\n---\n**参考来源：**\n" + "\n".join(f"- {s}" for s in result["sources"])
    return result["answer"] + sources_text


# ---------- 视频生成 ----------

def _get_vectorstore():
    """获取 vectorstore（不重建，失败返回 None）。"""
    try:
        return load_index()
    except Exception:
        return None


def _load_video_topics():
    """加载视频主题列表（优先从缓存，否则从知识库提取）。"""
    cache_path = os.path.join(OUTPUT_DIR, "video_topics.json")
    vs = _get_vectorstore()
    if vs is None:
        from src.video.topic_extractor import _default_topics
        return _default_topics()
    return extract_topics(vs, cache_path=cache_path)


def handle_refresh_topics():
    """强制从知识库重新提取主题。"""
    cache_path = os.path.join(OUTPUT_DIR, "video_topics.json")
    if os.path.exists(cache_path):
        os.remove(cache_path)
    topics = _load_video_topics()
    choices = [f"{t['category']}｜{t['title']} — {t['summary']}" for t in topics]
    return gr.update(choices=choices, value=choices[0] if choices else None)


def _list_existing_videos():
    """扫描输出目录，返回已有视频列表 [(label, path), ...]（最新在前）。"""
    videos = []
    if not os.path.isdir(VIDEO_OUTPUT_DIR):
        return videos
    for name in sorted(os.listdir(VIDEO_OUTPUT_DIR), reverse=True):
        dir_path = os.path.join(VIDEO_OUTPUT_DIR, name)
        story_path = os.path.join(dir_path, "story.mp4")
        if os.path.isfile(story_path):
            # 从目录名解析：名字_YYYYMMDD_HHMMSS
            label = name.replace("_", " ").replace("  ", " ")
            videos.append((label, story_path))
    return videos


def handle_generate_script(child_name, age, topic_selection, topics_data):
    """Step 1: 根据选中的知识主题生成讲解脚本。"""
    if not child_name.strip():
        return "### 请输入孩子名字", gr.update(visible=False), None, gr.update(visible=True)

    if not topic_selection or not topics_data:
        return "### 请先选择一个视频主题", gr.update(visible=False), None, gr.update(visible=True)

    # 从下拉框选择中匹配原始 topic dict
    topic = None
    for t in topics_data:
        label = f"{t['category']}｜{t['title']} — {t['summary']}"
        if label == topic_selection:
            topic = t
            break
    if topic is None:
        return "### 未找到选中的主题，请刷新重试", gr.update(visible=False), None, gr.update(visible=True)

    try:
        vs = _get_vectorstore()
        script = generate_knowledge_script(
            topic=topic,
            child_name=child_name.strip(),
            age=int(age),
            vectorstore=vs,
        )
        preview = format_script_for_display(script)
        scene_count = len(script["scenes"])
        return (
            f"### [OK] 脚本生成完成（{scene_count} 个场景）\n\n{preview}",
            gr.update(visible=True, value="确认并生成视频"),
            script,
            gr.update(visible=True),
        )
    except Exception as e:
        traceback.print_exc()
        return (
            f"### [FAIL] 脚本生成失败\n\n错误信息：{e}",
            gr.update(visible=False),
            None,
            gr.update(visible=True),
        )


def handle_generate_video(script_data, child_name, progress=gr.Progress()):
    """Step 2: 图片生成 → 配音 → 合成视频。"""
    if script_data is None:
        yield "### 请先生成脚本", gr.update(visible=False), gr.update(visible=True)
        return

    from src.video.image_gen import generate_scene_images
    from src.video.tts import generate_narration_audio
    from src.video.compose import compose_video

    # 为本次生成创建独立目录
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe_name = child_name.strip() or "story"
    work_dir = os.path.join(VIDEO_OUTPUT_DIR, f"{safe_name}_{ts}")
    os.makedirs(work_dir, exist_ok=True)

    scenes = script_data["scenes"]
    total = len(scenes)

    try:
        progress(0.0, desc="步骤 1/3: 正在生成图片...")
        yield f"### 正在生成图片（共 {total} 张）...", gr.update(visible=False), gr.update(visible=True)
        image_paths = generate_scene_images(scenes, work_dir)
        yield f"### [OK] 图片已生成 ({len(image_paths)}/{total})，正在配音...", gr.update(visible=False), gr.update(visible=True)

        progress(0.33, desc="步骤 2/3: 正在配音...")
        scenes = generate_narration_audio(scenes, work_dir)
        yield f"### [OK] 配音完成，正在合成视频...", gr.update(visible=False), gr.update(visible=True)

        progress(0.66, desc="步骤 3/3: 正在合成视频...")
        video_path = compose_video(scenes, work_dir)

        progress(1.0, desc="完成!")
        yield (
            f"### 🎉 视频生成完成！\n\n**「{script_data.get('title', '未命名')}」**\n\n点击下方播放或下载",
            gr.update(value=video_path, visible=True),
            gr.update(visible=True),
        )

    except Exception as e:
        traceback.print_exc()
        yield (
            f"### [FAIL] 视频生成失败\n\n错误信息：{e}\n\n请检查 API Key 配置和网络连接。",
            gr.update(visible=False),
            gr.update(visible=True),
        )


def build_video_tab():
    """构建视频生成 Tab — 基于知识库主题自动生成讲解视频。"""
    gr.Markdown("## 🎬 知识讲解视频生成")
    gr.Markdown("从育儿知识库中自动提取话题，AI 生成小朋友能理解的讲解视频")

    # 启动时加载主题
    topics = _load_video_topics()
    topic_choices = [f"{t['category']}｜{t['title']} — {t['summary']}" for t in topics]

    with gr.Row():
        child_name = gr.Textbox(label="孩子名字", placeholder="如：小明", scale=2)
        age = gr.Dropdown(label="年龄", choices=["3", "4", "5"], value="4", scale=1)

    with gr.Row():
        topic_dropdown = gr.Dropdown(
            label="视频主题（从知识库自动提取）",
            choices=topic_choices,
            value=topic_choices[0] if topic_choices else None,
            scale=3,
        )
        refresh_btn = gr.Button("🔄 刷新主题", scale=1)

    with gr.Row():
        gen_script_btn = gr.Button("📝 生成讲解脚本", variant="primary")
        confirm_btn = gr.Button("🎥 确认并生成视频", variant="primary", visible=False)

    script_output = gr.Markdown("选择主题后点击「生成讲解脚本」")
    video_output = gr.Video(visible=False, label="讲解视频")

    script_state = gr.State()
    topics_state = gr.State(topics)

    gen_script_btn.click(
        fn=handle_generate_script,
        inputs=[child_name, age, topic_dropdown, topics_state],
        outputs=[script_output, confirm_btn, script_state, gen_script_btn],
    )

    confirm_btn.click(
        fn=handle_generate_video,
        inputs=[script_state, child_name],
        outputs=[script_output, video_output, gen_script_btn],
    )

    refresh_btn.click(
        fn=handle_refresh_topics,
        inputs=[],
        outputs=[topic_dropdown],
    )

    # ---- 已生成视频 ----
    existing_videos = _list_existing_videos()
    if existing_videos:
        gr.Markdown("---")
        gr.Markdown("## 📺 已生成的视频")
        video_choices = [v[0] for v in existing_videos]
        video_paths = [v[1] for v in existing_videos]

        with gr.Row():
            video_selector = gr.Dropdown(
                label="选择视频",
                choices=video_choices,
                value=video_choices[0],
                scale=3,
            )
            play_btn = gr.Button("▶ 播放", variant="primary", scale=1)

        gallery_video = gr.Video(
            value=video_paths[0],
            visible=True,
            label="正在播放",
            autoplay=True,
            width=360,
            height=640,
        )

        def switch_video(selected_label):
            idx = video_choices.index(selected_label) if selected_label in video_choices else 0
            return gr.update(value=video_paths[idx], visible=True)

        play_btn.click(
            fn=switch_video,
            inputs=[video_selector],
            outputs=[gallery_video],
        )


# ---------- 主界面 ----------

def build_ui():
    with gr.Blocks(title="教育 AI 助手") as demo:
        gr.Markdown("# 📚 幼儿教育 AI 助手")
        gr.Markdown("基于育儿书籍知识库，为 3-5 岁幼儿家长提供专业建议")

        with gr.Tab("💬 教育问答"):
            gr.ChatInterface(
                fn=qa_handler,
                type="messages",
                chatbot=gr.Chatbot(height=500, type="messages", allow_tags=False),
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
            build_video_tab()

    return demo


if __name__ == "__main__":
    _free_port(7862)
    demo = build_ui()
    demo.launch(server_name="127.0.0.1", server_port=7862, share=False, show_error=True)
