# Sapling — 幼儿教育 AI 助手

基于 RAG（检索增强生成）的幼儿教育 AI 工具，将育儿书籍转化为可交互的知识问答和自动生成的讲解视频。

## 功能

- **教育问答** — 上传育儿书籍（PDF/EPUB），构建本地知识库，用自然语言提问获取基于书籍内容的专业建议
- **视频生成** — 从知识库自动提取教育主题，AI 生成讲解脚本 → 文生图 → 语音合成 → 视频合成，全自动产出幼儿知识讲解视频
- **访问控制** — 内置密码保护，支持通过 Cloudflare Tunnel 部署到自定义域名，安全公开访问

## 技术架构

```
育儿书 PDF/EPUB → 文档切分 → Embedding → FAISS 向量索引
                                              ↓
                              ┌───────────────┴───────────────┐
                              ↓                               ↓
                        教育问答 (RAG)                   视频生成 (Pipeline)
                    检索 → LLM → 回答          主题提取 → 脚本 → 生图 → TTS → FFmpeg
```

| 环节 | 技术 |
|------|------|
| LLM | 通义千问 (qwen-plus) |
| Embedding | 通义千问 text-embedding-v2 |
| 向量检索 | LangChain + FAISS |
| 文生图 | 通义万相 (wanx-v1) |
| 语音合成 | Edge TTS |
| 视频合成 | FFmpeg (Ken Burns 动画) |
| Web UI | Gradio |

## 快速开始

### 环境要求

- Python 3.10+
- FFmpeg（需在 PATH 中）

### 安装

```bash
git clone https://github.com/<your-username>/sapling.git
cd sapling
pip install -r requirements.txt
```

### 配置

在项目根目录创建 `.env` 文件：

```env
DASHSCOPE_API_KEY=your_dashscope_api_key
SAPLING_AUTH_USER=admin
SAPLING_AUTH_PASS=your_custom_password
```

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `DASHSCOPE_API_KEY` | — | 阿里云百炼 API Key（必填） |
| `SAPLING_AUTH_USER` | `admin` | Web 登录账号 |
| `SAPLING_AUTH_PASS` | `sapling2026` | Web 登录密码 |

> 需要[阿里云百炼](https://bailian.console.aliyun.com/)的 API Key，开通通义千问和通义万相服务。

### 准备知识库

将育儿相关的 PDF 或 EPUB 文件放入 `data/books/` 目录，首次启动时会自动构建 FAISS 索引。

### 启动

```bash
python app.py
```

浏览器访问 `http://127.0.0.1:7862`，输入配置的账号密码登录。

### 部署到公网（Cloudflare Tunnel）

将应用部署到自定义域名，通过 Cloudflare 全球 CDN 安全访问：

**1. 域名托管到 Cloudflare DNS**

**2. 安装 cloudflared**

```powershell
winget install Cloudflare.cloudflared
```

**3. 创建隧道并绑定域名**

```powershell
cloudflared tunnel login
cloudflared tunnel create sapling
cloudflared tunnel route dns sapling kids.your-domain.com
```

**4. 配置隧道** (`%USERPROFILE%\.cloudflared\config.yml`)

```yaml
tunnel: sapling
credentials-file: C:\Users\<用户名>\.cloudflared\<tunnel-uuid>.json
ingress:
  - hostname: kids.your-domain.com
    service: http://localhost:7862
  - service: http_status:404
```

**5. 启动**

分别启动：

```powershell
$env:SAPLING_AUTH_USER="admin"
$env:SAPLING_AUTH_PASS="your_password"
python app.py

# 另一个终端
cloudflared tunnel run sapling
```

访问 `https://kids.your-domain.com` 即可，首次打开会弹出登录框。

## 项目结构

```
app.py                       # Gradio 入口（问答 Tab + 视频 Tab）
tunnel.cmd                   # Cloudflare Tunnel 启动脚本
src/
  rag/                       # 教育问答子系统
    loader.py                # PDF/EPUB 加载与 chunk 切分
    embedder.py              # Embedding + FAISS 索引构建
    qa.py                    # RetrievalQA chain
  video/                     # 视频生成子系统
    topic_extractor.py       # 从知识库提取视频主题
    knowledge_script.py      # LLM 生成知识讲解脚本
    image_gen.py             # 通义万相生图
    tts.py                   # Edge TTS 配音
    compose.py               # FFmpeg 合成视频
  shared/
    config.py                # 全局配置
data/
  books/                     # 育儿书源文件
  faiss_index/               # FAISS 索引
  output/videos/             # 生成的视频
```

## 配置常量

| 常量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_MODEL` | `qwen-plus` | 脚本生成 + 问答模型 |
| `IMAGE_MODEL` | `wanx-v1` | 文生图模型 |
| `IMAGE_SIZE` | `720*1280` | 输出图片/视频分辨率（竖屏） |
| `VIDEO_FPS` | 30 | Ken Burns 动画帧率 |
| `CHUNK_SIZE` | 500 | 文档切分粒度 |
| `RETRIEVAL_TOP_K` | 5 | 检索返回数量 |

## 视频生成流程

1. **主题提取** — LLM 扫描知识库，提取适合制作幼儿视频的知识点（如"为什么要刷牙"、"生气时怎么办"）
2. **脚本生成** — 根据选中主题，结合知识库参考资料，生成 5-8 个场景的讲解脚本，每个场景包含画面描述和旁白
3. **图片生成** — 通义万相逐场景生成竖屏图片，失败自动用占位图兜底
4. **语音合成** — Edge TTS 将旁白转为中文语音
5. **视频合成** — FFmpeg 合成 Ken Burns 动画（平移/缩放效果），拼接为完整视频

## License

MIT
