# TranslateGemma — Offline Translation Web GUI

基于 [Gemma](https://ai.google.dev/gemma) 的离线翻译工具，使用 llama.cpp 本地推理 + Flask Web 界面，无需联网。

## 功能特性

- **完全离线**：翻译全程在本地完成，数据不外传
- **47 种语言**：覆盖中、英、日、韩、法、德、西、俄、阿等主流语言
- **OpenAI 兼容 API**：提供 `/v1/chat/completions` 端点，可接入 Zotero 翻译插件等第三方工具
- **流式输出**：翻译结果实时逐字显示
- **轻量前端**：纯 HTML/CSS/JS，无框架依赖
- **系统托盘**：最小化到通知区域，右键菜单快速操作，不占任务栏空间

## 项目结构

```
translategemma4GUI/
├── launcher.py          # 启动器：一键启动 llama-server + Web UI + 系统托盘
├── src/
│   ├── app.py           # Flask 应用（Web UI + API）
│   ├── static/
│   │   ├── app.js       # 前端逻辑
│   │   └── style.css    # 样式
│   └── templates/
│       └── index.html   # 翻译界面
├── config.json          # 配置文件（模型路径、端口、语言列表等）
├── start.bat            # Windows 一键启动脚本
├── bin/                 # ⚠️ 需自行下载（见下方说明）
├── models/              # ⚠️ 需自行下载（见下方说明）
└── python/              # ⚠️ 需自行下载（见下方说明）
```

## 前置依赖下载

以下三个目录未包含在仓库中，需要自行准备：

### 1. `bin/` — llama.cpp 推理引擎

放置 `llama-server.exe`，用于运行 GGUF 格式的模型。

- **下载地址**：[llama.cpp Releases](https://github.com/ggerganov/llama.cpp/releases)
- 选择最新的 Windows 预编译包（如 `llama-bxxxx-bin-win-cuda-cuXX-x64.zip`）
- 将压缩包中的 `llama-server.exe` 及其依赖 DLL 解压到 `bin/` 目录

> 如果使用 CPU 推理，下载不带 CUDA 的版本即可。NVIDIA 显卡用户建议下载 CUDA 版本以获得更好性能。

### 2. `python/` — 嵌入式 Python 运行时

放置 `python.exe` 及其标准库，Flask Web UI 依赖此运行。

- **下载地址**：[Python Embedded Package](https://www.python.org/downloads/windows/)
- 选择 `Windows embeddable package (64-bit)`，推荐 Python 3.9+
- 解压到 `python/` 目录
- 需额外安装 `flask` 和 `requests` 到嵌入式环境中（或将它们放入 `python/Lib/site-packages/`）

### 3. `models/` — GGUF 翻译模型

放置 `.gguf` 格式的模型文件。默认配置指向 `models/translategemma-4b-it.Q4_K_M.gguf`。

- 推荐模型：`translategemma-4b-it`（专为翻译任务优化的 Gemma 4B 变体）。下载地址： [translategemma-4b-it-GGUF](https://huggingface.co/mradermacher/translategemma-4b-it-GGUF)
- 推荐量化：`Q4_K_M`（在速度与质量之间取得平衡）
- 可从 Hugging Face 等平台搜索下载对应的 GGUF 文件

> 如需使用其他路径或模型，修改 `config.json` 中的 `model.path` 即可。

## 快速开始

1. 按上述说明准备好 `bin/`、`python/`、`models/` 三个目录
2. 根据需要修改 `config.json`（模型路径、端口号等）
3. 双击 `start.bat` 或运行：
   ```bash
   python\python.exe launcher.py
   ```
4. 浏览器会自动打开翻译界面（默认 `http://127.0.0.1:5000`）
5. 将控制台窗口最小化即可隐藏到系统托盘；右键托盘图标可显示主窗口或退出

---

## 系统托盘

启动后，控制台窗口最小化时会自动隐藏到右下角通知区域。右键点击托盘图标（蓝色"译"字），弹出菜单：

| 菜单项 | 功能 |
|--------|------|
| **显示主窗口** | 恢复控制台窗口 + 打开浏览器 |
| **退出** | 停止所有服务（Flask + llama-server）并退出程序 |

> 依赖 `pystray` 和 `Pillow`。如未安装，程序会退回原始控制台行为（`Ctrl+C` 退出）。

---

## 配置说明

`config.json` 主要配置项：

| 配置项 | 说明 |
|--------|------|
| `model.path` | GGUF 模型文件路径（相对于项目根目录） |
| `model.context_size` | 上下文窗口大小，默认 2048 |
| `model.threads` | CPU 推理线程数 |
| `llama_server.host` | llama-server 监听地址，默认 127.0.0.1 |
| `llama_server.port` | llama-server 端口，默认 8080 |
| `web_ui.host` | Web 界面监听地址，默认 127.0.0.1 |
| `web_ui.port` | Web 界面端口，默认 5000 |
| `translation.default_source_lang` | 默认源语言 |
| `translation.default_target_lang` | 默认目标语言 |

---

## 使用方式

本工具提供三种使用途径，覆盖从日常手动翻译到自动化集成的所有场景。

### 方式一：Web 图形界面

启动程序后浏览器会自动打开翻译页面，这是最直观的使用方式。

**操作步骤：**

1. 在左侧下拉框选择**源语言**（要翻译的语言）
2. 在右侧下拉框选择**目标语言**（翻译成什么语言）
3. 在左侧文本框输入或粘贴待翻译文本
4. 点击 **Translate** 按钮（或按 `Ctrl+Enter`）
5. 翻译结果实时流式显示在右侧文本框中

**快捷操作：**

| 操作 | 说明 |
|------|------|
| `Ctrl+Enter` | 开始翻译 |
| 点击 ⇄ 按钮 | 交换源语言和目标语言 |
| 点击右侧译文 | 一键复制到剪贴板 |

**适用场景：** 日常手动翻译、阅读外文资料、撰写多语言邮件。

---

### 方式二：内置翻译 API（`/api/translate`）

适合脚本化调用或集成到自定义工具链。使用 Server-Sent Events (SSE) 协议流式返回翻译结果。

**端点：** `POST /api/translate`

**请求格式：**

```json
{
    "text": "要翻译的文本",
    "source_lang": "zh-Hans",
    "target_lang": "en"
}
```

**响应格式（SSE 流式）：**

```
data: {"token": "Hello"}

data: {"token": ", world"}

data: {"token": "!"}

data: {"done": true}
```

**curl 示例——中文翻译成英文：**

```bash
curl -N -X POST http://127.0.0.1:5000/api/translate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "人工智能正在改变世界。",
    "source_lang": "zh-Hans",
    "target_lang": "en"
  }'
```

> `-N` 参数禁用 curl 的缓冲，确保 SSE 数据实时输出。

**curl 示例——英文翻译成日文：**

```bash
curl -N -X POST http://127.0.0.1:5000/api/translate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Machine learning has revolutionized natural language processing.",
    "source_lang": "en",
    "target_lang": "ja"
  }'
```

**curl 示例——将结果保存到文件：**

```bash
curl -N -s -X POST http://127.0.0.1:5000/api/translate \
  -H "Content-Type: application/json" \
  -d '{"text": "你好世界", "source_lang": "zh-Hans", "target_lang": "fr"}' \
  | while IFS= read -r line; do
      token=$(echo "$line" | sed -n 's/data: {"token": "\(.*\)"}/\1/p')
      if [ -n "$token" ]; then
        printf "%s" "$token"
      fi
    done > translation_output.txt
```

> 接收到的 `data: {"done": true}` 表示翻译完成。

**Python 调用示例：**

```python
import requests
import json

url = "http://127.0.0.1:5000/api/translate"
payload = {
    "text": "今天天气真好。",
    "source_lang": "zh-Hans",
    "target_lang": "en"
}

with requests.post(url, json=payload, stream=True) as resp:
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        data_str = line[6:]  # 去掉 "data: " 前缀
        if data_str == '{"done": true}':
            break
        chunk = json.loads(data_str)
        print(chunk.get("token", ""), end="", flush=True)
```

**JavaScript (浏览器) 调用示例：**

```javascript
async function translate(text, sourceLang, targetLang) {
    const resp = await fetch("http://127.0.0.1:5000/api/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            text: text,
            source_lang: sourceLang,
            target_lang: targetLang,
        }),
    });

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let result = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const line of decoder.decode(value).split("\n")) {
            if (!line.startsWith("data: ")) continue;
            const data = JSON.parse(line.slice(6));
            if (data.done) return result;
            if (data.token) {
                result += data.token;
                console.log(data.token); // 逐 token 处理
            }
        }
    }
    return result;
}

// 使用
await translate("Hello world", "en", "zh-Hans");
```

---

### 方式三：OpenAI 兼容 API（`/v1/chat/completions`）

提供与 OpenAI Chat Completions API 兼容的端点，可直接接入 Zotero、沉浸式翻译、OpenCat 等大量第三方工具。支持流式和非流式两种模式。

**端点：** `POST /v1/chat/completions`

**两种工作模式：**

| 模式 | 触发条件 | 说明 |
|------|----------|------|
| **原生翻译模式** | 请求中带 `source_lang` + `target_lang` | 自动提取用户消息中的待翻译文本，去除 Zotero 等工具的提示词模板，以模型原生格式构建 prompt。推荐用于翻译场景。 |
| **原始对话模式** | 不带语言参数 | 将 messages 数组原样转换为 Gemma chat template 发给模型。适合发送完全自定义的 prompt。 |

---

#### 3a. 原生翻译模式（推荐）

传入 `source_lang` 和 `target_lang`，系统会自动从 messages 中提取纯文本进行翻译。

**非流式请求示例：**

```bash
curl -X POST http://127.0.0.1:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "translategemma-4b",
    "messages": [
      {"role": "user", "content": "人工智能正在改变世界。"}
    ],
    "source_lang": "zh-Hans",
    "target_lang": "en",
    "stream": false
  }'
```

**响应：**

```json
{
    "id": "chatcmpl-...",
    "object": "chat.completion",
    "created": 1720350000,
    "model": "translategemma-4b",
    "choices": [{
        "index": 0,
        "message": {
            "role": "assistant",
            "content": "Artificial intelligence is changing the world."
        },
        "finish_reason": "stop"
    }],
    "usage": {
        "prompt_tokens": 45,
        "completion_tokens": 8,
        "total_tokens": 53
    }
}
```

**流式请求示例：**

```bash
curl -N -X POST http://127.0.0.1:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "translategemma-4b",
    "messages": [
      {"role": "user", "content": "Bonjour le monde"}
    ],
    "source_lang": "fr",
    "target_lang": "zh-Hans",
    "stream": true
  }'
```

**流式响应（SSE）：**

```
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","created":...,"model":"translategemma-4b","choices":[{"index":0,"delta":{"role":"assistant","content":"你好"},"finish_reason":null}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","created":...,"model":"translategemma-4b","choices":[{"index":0,"delta":{"content":"世界"},"finish_reason":null}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","created":...,"model":"translategemma-4b","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

> 非流式模式适用于批量处理脚本；流式模式适用于需要实时反馈的交互式 UI。

---

#### 3b. 原始对话模式

不传 `source_lang` / `target_lang` 时，messages 数组会被原样转换为 Gemma 格式发给模型。适合需要完全控制 prompt 的高级场景。

**示例——发送自定义 prompt：**

```bash
curl -X POST http://127.0.0.1:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "translategemma-4b",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant that summarizes text."},
      {"role": "user", "content": "Summarize: The quick brown fox jumps over the lazy dog. This sentence contains every letter of the English alphabet."}
    ],
    "stream": false
  }'
```

---

#### 3c. Python 调用示例（OpenAI SDK 兼容）

```python
import requests
import json

url = "http://127.0.0.1:5000/v1/chat/completions"

# 非流式翻译
resp = requests.post(url, json={
    "model": "translategemma-4b",
    "messages": [{"role": "user", "content": "机器学习很有趣。"}],
    "source_lang": "zh-Hans",
    "target_lang": "en",
    "stream": False,
})
result = resp.json()
translated = result["choices"][0]["message"]["content"]
print(translated)
```

---

### 方式四：第三方工具集成

#### Zotero 翻译插件

Zotero 是一款文献管理工具，内置翻译功能。接入后可实现论文摘要、标题的一键离线翻译。

**配置步骤：**

1. 打开 Zotero → `编辑` → `设置` → `翻译`（或 `Edit` → `Settings` → `Translate`）
2. 翻译服务选择 **自定义 API** 或 **OpenAI 兼容**
3. 填入以下信息：

| 设置项 | 值 |
|--------|-----|
| API 地址 / Base URL | `http://127.0.0.1:5000` |
| API Key | 留空（本工具不验证密钥） |
| 模型名称 | `translategemma-4b` |
| 提示语 / Prompt | 留空即可，系统自动处理 |

4. 在 Zotero 中选中文本，即可查看翻译

> Zotero 的翻译请求中包含 `source_lang` 和 `target_lang`，会自动触发原生翻译模式，提示词中的 🔤 标记会被正确剥离。

---

#### 沉浸式翻译 (Immersive Translate)

沉浸式翻译是一款浏览器插件，支持双语对照浏览网页。

**配置步骤：**

1. 打开沉浸式翻译插件 → `设置` → `翻译服务`
2. 添加 **OpenAI 兼容** 服务
3. 填入以下信息：

| 设置项 | 值 |
|--------|-----|
| 自定义 API 地址 | `http://127.0.0.1:5000/v1/chat/completions` |
| API Key | 留空 |
| 模型 | `translategemma-4b` |

4. 保存后在网页中即可使用双语对照翻译

---

#### 其他支持 OpenAI 兼容 API 的工具

任何支持自定义 OpenAI API 端点的工具都可以接入，通用的配置参数：

| 参数 | 值 |
|------|-----|
| Base URL / Endpoint | `http://127.0.0.1:5000` |
| API Key | 任意非空字符串（如 `sk-local`）或不填 |
| Model | `translategemma-4b` |

已验证或理论上兼容的工具：

| 工具 | 类型 | 备注 |
|------|------|------|
| [Zotero](https://www.zotero.org/) | 文献管理 | 已验证，见上方详细配置 |
| [沉浸式翻译](https://immersivetranslate.com/) | 浏览器插件 | 需填入完整路径 `/v1/chat/completions` |
| [OpenCat](https://opencat.app/) | macOS/iOS ChatGPT 客户端 | 添加自定义 API |
| [Chatbox](https://chatboxai.app/) | 跨平台 AI 桌面客户端 | 支持自定义 OpenAI 兼容端点 |
| [Continue](https://continue.dev/) | IDE 编程助手 | 可作为本地补全/对话后端 |
| [Open WebUI](https://openwebui.com/) | 自托管 AI 聊天面板 | 添加 OpenAI 兼容连接 |
| [RSS 翻译](https://github.com/rss-translator) | RSS 订阅翻译 | 设置自定义翻译 API |

> **注意：** 本工具的核心场景是翻译，使用对话功能时受限于 translategemma 模型的训练目标，非翻译类对话的质量可能不如通用聊天模型。

---

## API 端点速查

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 翻译 Web 图形界面 |
| `/api/languages` | GET | 获取支持的语言列表 |
| `/api/translate` | POST | 简单翻译接口（SSE 流式） |
| `/v1/models` | GET | OpenAI 兼容模型列表 |
| `/v1/chat/completions` | POST | OpenAI 兼容 Chat Completions（流式/非流式） |

---

## 许可

MIT License — 详见 [LICENSE](LICENSE)
