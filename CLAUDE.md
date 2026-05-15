# CLAUDE.md — Sapling 儿童教育 AI 助手

## 项目概述

幼儿教育 AI 工具，两个子系统共享同一套知识库（育儿书 PDF → Embedding → FAISS）：

1. **教育问答**：RAG 管线，检索 → LLM → 回答
2. **视频生成**：脚本 → 生图 → TTS → FFmpeg 合成

技术栈：Gradio + LangChain + 通义千问/万相 + Edge TTS + FFmpeg

## 关键设计约束

### 图片与台词的一致性

当前问题：image_prompt 和 narration 由 LLM 一次性输出后各自独立处理，没有交叉验证。多场景间角色外观不一致（靠 prompt 工程硬凑）。

修改相关代码时遵循：

```
每个场景 = { image_prompt（给图片 API）, narration（给 TTS） }
```

- **image_prompt 必须以 `STYLE_DIRECTIVE + CHARACTER_APPEARANCE` 开头**，[src/video/script.py](src/video/script.py) 的 `_enforce_style_prompts()` 保证了这一点，新增入口时也要调用它
- **image_prompt 和 narration 必须描述同一件事**：narration 说"小兔子吃胡萝卜"，image_prompt 就不能画"小猫玩球"。LLM 输出后考虑加一个校验步骤，用简单规则检查关键词是否同时在 narration 和 image_prompt 中出现
- **CHARACTER_APPEARANCE 是全局常量**，所有场景复用，不要在每个 scene 里为同一角色写不同的外观描述。如果要引入角色名替换，在 CHARACTER_APPEARANCE 中用 `{name}` 占位符然后 format
- **image_gen.py 生成失败时用占位图兜底**，不要中断整个管线。当前 `_create_placeholder()` 生成 256x256 紫色 PNG，确保 FFmpeg 不会报错
- **生图后不要假设成功**：`generate_scene_images()` 返回的路径列表可能与 scenes 数量一致（失败时也有占位图），下游代码可以安全依赖这个不变量

### 脚本检索的准确性

当前问题：知识库是育儿书（写给家长看的），但检索出来给 LLM 当"参考资料"写儿童故事。家长教育建议 ≠ 儿童故事素材，匹配度天然低。

- **检索 query 的构造在 `generate_script()` 中**：[src/video/script.py:113](src/video/script.py#L113) — `f"{theme} {educational_goal} 3-{age}岁幼儿教育"`。调整检索策略时优先改这个 query 模板
- **检索结果仅作为参考，不是模板**：SCRIPT_PROMPT 里 `{reference_section}` 是可选的，vectorstore 为 None 时也能生成。不要硬依赖检索结果
- **当检索内容与 theme/goal 明显不相关时**（比如检索出"家长如何处理分离焦虑"，但 theme 是"小兔子学刷牙"），LLM 应该忽略参考资料用自己的知识创作。当前实现没有这个判断逻辑，可以考虑加一个相关性阈值过滤
- **调优方向**：
  - 把检索 query 从家长视角改写为故事创作视角（"关于 X 主题的幼儿故事素材"而不是"X 岁孩子 X 问题怎么办"）
  - 对检索回来的 chunk 做二次过滤，只保留与故事创作相关的（用 LLM 判断或关键词匹配）
  - 增加检索 k 值（当前 `RETRIEVAL_TOP_K=5`），多召回一些再筛选
- **降级方案优先级**：LLM JSON 解析失败 → 认知类退化脚本（`_fallback_cognitive_scenes`）；场景数 < 3 → 同样降级。认知类内容不需要角色一致性，天然规避了图片一致性问题

## 项目结构

```
app.py                      # Gradio 入口（问答 Tab + 视频 Tab）
src/
  rag/                      # 子系统一：教育问答
    loader.py               # PDF/EPUB 加载与 chunk 切分
    embedder.py             # Embedding + FAISS 索引构建/加载
    qa.py                   # RetrievalQA chain + ask()
  video/                    # 子系统二：视频生成
    script.py               # LLM 分镜脚本生成（核心：prompt 模板）
    image_gen.py             # 通义万相 API 调用，逐场景生图
    tts.py                  # Edge TTS 配音，获取音频时长
    compose.py              # FFmpeg Ken Burns 合成 + 片段拼接
  shared/
    config.py               # 所有全局配置（API key、模型、路径常量）
data/
  books/                    # 育儿书 PDF/EPUB 源文件
  faiss_index/              # FAISS 索引持久化
  output/
    videos/                 # 生成的视频输出目录
```

## 配置常量（修改时注意影响范围）

| 常量 | 值 | 影响 |
|------|-----|------|
| `LLM_MODEL` | `qwen-plus` | 脚本生成 + 问答 |
| `IMAGE_MODEL` | `wanx-v1` | 文生图 |
| `IMAGE_SIZE` | `1024*1024` | 输出图片分辨率，也是视频分辨率 |
| `VIDEO_FPS` | 30 | Ken Burns 动画帧率 |
| `CHUNK_SIZE` | 500 | 文档切分粒度，影响检索精度 |
| `CHUNK_OVERLAP` | 200 | chunk 重叠量 |
| `RETRIEVAL_TOP_K` | 5 | 检索返回文档数 |

## 开发约定

- FFmpeg 必须在 PATH 中，`compose.py` 启动时会检查
- 通义万相 API 返回的是图片 URL，需要 `_download_image()` 下载到本地，不是直接返回图片数据
- Edge TTS 是 async API，用 `asyncio.run()` 同步调用，注意 Gradio 环境可能有自己的 event loop（已处理）
- 视频生成为每个请求创建独立目录 `data/output/videos/{name}_{timestamp}/`
