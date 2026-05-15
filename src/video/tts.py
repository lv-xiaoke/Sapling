"""Edge TTS 配音 — 将旁白转为语音"""

import os
import json
import subprocess
import asyncio

from src.shared.config import TTS_VOICE


def generate_narration_audio(
    scenes: list[dict],
    output_dir: str,
    voice: str | None = None,
) -> list[dict]:
    """为每个场景生成旁白音频，返回带时长信息的场景列表。

    Args:
        scenes: 场景列表，每项含 narration 字段
        output_dir: 输出目录
        voice: TTS 音色，默认 zh-CN-XiaoxiaoNeural

    Returns:
        更新后的 scenes 列表，每项新增 audio_path 和 duration 字段
    """
    if voice is None:
        voice = TTS_VOICE

    os.makedirs(output_dir, exist_ok=True)

    for i, scene in enumerate(scenes):
        text = scene["narration"]
        audio_path = os.path.join(output_dir, f"scene_{i}.mp3")

        print(f"正在配音第 {i+1}/{len(scenes)} 场景...")
        _tts_sync(text, audio_path, voice)

        duration = _get_audio_duration(audio_path)
        scene["audio_path"] = audio_path
        scene["duration"] = duration
        print(f"  [OK] 已保存: scene_{i}.mp3 ({duration:.1f}s)")

    return scenes


def _tts_sync(text: str, output_path: str, voice: str) -> None:
    """同步调用 edge-tts 生成语音。"""
    import edge_tts

    async def _run():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)

    try:
        asyncio.run(_run())
    except RuntimeError:
        # 如果已有 event loop（如在某些 Gradio 环境下）
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_run())
        loop.close()


def _get_audio_duration(filepath: str) -> float:
    """通过 ffprobe 获取音频时长（秒）。"""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", filepath,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])
    except Exception as e:
        print(f"  获取音频时长失败: {e}，使用估算值 5s")
        return 5.0


def generate_combined_audio(scenes: list[dict], output_dir: str) -> str:
    """将所有场景旁白合并为一个音频文件（带短暂停顿）。"""
    import edge_tts

    # 拼接所有旁白
    combined_text = "。".join(s["narration"] for s in scenes)
    output_path = os.path.join(output_dir, "narration_combined.mp3")

    async def _run():
        communicate = edge_tts.Communicate(combined_text, TTS_VOICE)
        await communicate.save(output_path)

    try:
        asyncio.run(_run())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_run())
        loop.close()

    return output_path
