"""通义万相图片生成 — 为每个场景生成插图"""

import os
import time
import requests
import dashscope
from dashscope import ImageSynthesis

from src.shared.config import DASHSCOPE_API_KEY, IMAGE_MODEL, IMAGE_SIZE

dashscope.api_key = DASHSCOPE_API_KEY


def generate_scene_images(scenes: list[dict], output_dir: str) -> list[str]:
    """为每个场景生成插图，返回图片路径列表。

    Args:
        scenes: 场景列表，每项含 image_prompt 字段
        output_dir: 输出目录

    Returns:
        ["path/to/scene_0.png", ...]
    """
    os.makedirs(output_dir, exist_ok=True)
    image_paths = []
    total = len(scenes)

    for i, scene in enumerate(scenes):
        prompt = scene["image_prompt"]
        save_path = os.path.join(output_dir, f"scene_{i}.png")

        print(f"正在生成第 {i+1}/{total} 张图片...")
        print(f"  Prompt: {prompt[:80]}...")

        success = _generate_single(prompt, save_path)
        if success:
            image_paths.append(save_path)
            print(f"  [OK] 已保存: scene_{i}.png")
        else:
            # 失败时使用纯色占位图
            print(f"  [FAIL] 生成失败，使用占位图")
            _create_placeholder(save_path, text=scene.get("narration", "")[:20])
            image_paths.append(save_path)

        # 避免请求过快
        if i < total - 1:
            time.sleep(1)

    return image_paths


def _generate_single(prompt: str, save_path: str, max_retries: int = 3) -> bool:
    """单张图片生成，含重试。

    通义万相通过 DashScope API 调用，返回图片 URL 后下载到本地。
    """
    for attempt in range(max_retries):
        try:
            response = ImageSynthesis.call(
                model=IMAGE_MODEL,
                prompt=prompt,
                negative_prompt="blurry, low quality, distorted, ugly, dark, scary",
                n=1,
                size=IMAGE_SIZE,
            )

            if response.status_code == 200 and response.output:
                img_url = response.output.results[0].url
                _download_image(img_url, save_path)
                return True

            print(f"  API 返回错误 (尝试 {attempt+1}): "
                  f"status={response.status_code}, msg={getattr(response, 'message', 'unknown')}")

        except Exception as e:
            print(f"  异常 (尝试 {attempt+1}): {e}")

        if attempt < max_retries - 1:
            wait = 2 ** attempt
            print(f"  等待 {wait}s 后重试...")
            time.sleep(wait)

    return False


def _download_image(url: str, save_path: str) -> None:
    """从 URL 下载图片到本地。"""
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(r.content)


def _create_placeholder(save_path: str, text: str = "") -> None:
    """创建纯色占位图（无 PIL 依赖）。"""
    # 最小 PNG：1x1 紫色像素，让 FFmpeg 不会崩溃
    # 89 50 4E 47 = PNG magic
    import struct
    import zlib

    def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    # 256x256 紫色像素
    width, height = 256, 256
    raw_data = b""
    for y in range(height):
        raw_data += b"\x00"  # filter byte
        for _ in range(width):
            raw_data += b"\xCC\xAA\xEE\xFF"  # RGBA 淡紫色

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    compressed = zlib.compress(raw_data)

    with open(save_path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(_png_chunk(b"IHDR", ihdr))
        f.write(_png_chunk(b"IDAT", compressed))
        f.write(_png_chunk(b"IEND", b""))
