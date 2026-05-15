"""FFmpeg 视频合成 — Ken Burns 效果 + 配音合成 MP4"""

import os
import subprocess
import shutil

from src.shared.config import VIDEO_FPS, VIDEO_RESOLUTION


def compose_video(scenes: list[dict], output_dir: str) -> str:
    """将场景图片 + 音频合成为带 Ken Burns 效果的 MP4。

    Args:
        scenes: 场景列表，每项需含 image_prompt(仅用索引), audio_path, duration
        output_dir: 输出目录（含 scene_N.png 和 scene_N.mp3）

    Returns:
        最终视频文件路径
    """
    _check_ffmpeg()
    width, height = VIDEO_RESOLUTION

    segment_paths = []

    for i, scene in enumerate(scenes):
        image_path = os.path.join(output_dir, f"scene_{i}.png")
        audio_path = scene.get("audio_path", os.path.join(output_dir, f"scene_{i}.mp3"))
        duration = scene.get("duration", 5.0)

        segment_path = os.path.join(output_dir, f"segment_{i}.mp4")
        print(f"正在合成场景 {i+1}/{len(scenes)} ({duration:.1f}s)...")

        _create_segment(image_path, audio_path, duration, segment_path, width, height)
        segment_paths.append(segment_path)

    # 拼接所有片段
    final_path = os.path.join(output_dir, "story.mp4")

    if len(segment_paths) == 1:
        shutil.copy2(segment_paths[0], final_path)
    else:
        concat_list = os.path.join(output_dir, "concat_list.txt")
        with open(concat_list, "w") as f:
            for p in segment_paths:
                f.write(f"file '{os.path.basename(p)}'\n")

        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_list,
                "-c", "copy",
                final_path,
            ],
            capture_output=True,
            text=True,
            cwd=output_dir,
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg 拼接失败:\n{result.stderr}")

    print(f"视频合成完成: {final_path}")
    return final_path


def _create_segment(
    image_path: str,
    audio_path: str,
    duration: float,
    output_path: str,
    width: int,
    height: int,
) -> None:
    """为单张图片创建带 Ken Burns 效果 + 音频的视频片段。

    Ken Burns: 缓慢缩放 (1.0→1.12)，产生动态视觉效果。
    """
    fps = VIDEO_FPS
    total_frames = int(duration * fps)
    # 缩放速度：总缩放量 / 总帧数
    zoom_speed = 0.12 / max(total_frames, 1)

    zoompan = (
        f"zoompan="
        f"z='if(eq(on,1),1.0,min(zoom+{zoom_speed},1.2))':"
        f"d=1:"
        f"fps={fps}:"
        f"s={width}x{height}:"
        f"x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)',"
        f"format=yuv420p"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-i", audio_path,
        "-vf", zoompan,
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 片段合成失败:\n{result.stderr}")


def _check_ffmpeg() -> None:
    """验证 FFmpeg 可用。"""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "未找到 FFmpeg，请安装后添加到 PATH。\n"
            "下载地址: https://ffmpeg.org/download.html"
        )
