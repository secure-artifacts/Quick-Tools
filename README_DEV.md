# Quick Tools (全能工具箱) - 开发者接手手册

本项目是一个基于 **PyQt6** 开发的桌面自动化工具集合，主要包含音频处理、TTS (文本转语音) 生成、以及项目制的文件管理功能。

## 1. 项目整体结构

```text
Quick Tools/
├── main.py                 # 程序入口，负责主窗口初始化、全局设置及功能标签页装载
├── config.json             # 全局配置文件（包含 API 密钥、输出路径、任务记录等）
├── history.db              # SQLite 数据库，用于存储音频生成的历史记录
├── requirements.txt        # 项目依赖列表
├── modules/                # 核心功能模块文件夹
│   ├── config_manager.py   # 配置管理逻辑，处理 config.json 的读写
│   ├── history_manager.py  # 历史记录管理逻辑，操作 SQLite 数据库
│   ├── audio_manager/      # 音频功能模块
│   │   ├── ui.py           # 音频工具主页（包含子标签页容器）
│   │   ├── services/       # 音频逻辑服务（API 接口、音频处理算法）
│   │   │   ├── processor.py   # 音频分割与匹配的核心算法
│   │   │   ├── google_ai.py   # Google AI (Gemini) TTS 服务封装
│   │   │   └── elevenlabs.py  # ElevenLabs TTS 服务封装
│   │   └── widgets/        # 具体功能的 UI 组件
│   │       ├── generate_widget.py   # 音频生成（TTS）界面
│   │       ├── split_widget.py     # 音频分割界面
│   │       ├── match_widget.py     # 音频视频匹配界面
│   │       └── history_widget.py   # 生成历史管理界面
│    ├── file_manager/       # 文件管理模块
│       ├── logic.py        # 包含 CSV 解析逻辑、Google Drive ID 提取及文件下载功能
│       └── ui.py           # 智能导入与项目管理界面
```

---

## 2. 核心模块功能详解

### 2.1 全局入口与配置 (`main.py` & `config_manager.py`)
- **`main.py`**: 程序启动点。它定义了 `DesktopApp` 类，管理顶部导航和全局输出路径。它通过 `QTabWidget` 将不同的功能模块以标签页形式组合。
- **配置管理**: `ConfigManager` 是全局单例化的（在 `main.py` 中初始化并传给子模块）。它负责维护 API Key、语言设置以及生成的任务列表状态（实现关闭程序后再打开任务不丢失）。

### 2.2 音频管理模块 (`modules/audio_manager/`)
这是目前功能最丰富的部分，采用“UI 组件化” + “服务逻辑化”的结构。

- **音频生成 (`generate_widget.py`)**:
    - **双引擎支持**: 同时支持 ElevenLabs 和 Google AI。
    - **任务队列**: 支持批量添加文本任务，实时更新各任务的生成进度（等待中、生成中、已完成）。
    - **Key 轮询**: 针对 Google AI 的配额限制，实现了自动轮询多个 API Key 的功能（定义在 `google_ai.py`）。

- **Google AI 服务 (`google_ai.py`)**:
    - **模型适配**: 针对 `gemini-2.5-flash-preview-tts` 模型进行了提示词优化，通过强制音频模态输出避免 400 错误。
    - **智能重试与 Key 轮换**: 集成 `tenacity` 进行指数退避重试；检测到 429 额度耗尽时，自动从池中剔除失效 Key 并无缝切换至下一个。
    - **WAV 头构建**: 对于返回原始 PCM 流的音频片段，逻辑层会自动计算采样率（24kHz）并封装标准的 WAV 文件头（RIFF），确保输出文件可直接播放。

- **ElevenLabs 服务 (`elevenlabs.py`)**:
    - **API Key 池管理**: 支持多 Key 轮询和自动补救。当某个 Key 余额不足时，自动从备用 Key 池中调取可用 Key 继续任务。
    - **自动声线管理**: 针对 ElevenLabs 免费/基础版账户的自定义声线槽位限制（如 3/3），实现了自动检测并释放旧声线逻辑。
    - **熔断机制**: 增加了针对账户风控（unusual activity）的自动熔断，防止账号在异常状态下继续调用。
    - **隐私保护**: 生成过程中采用随机 UUID 命名临时文件，确保任务名称不直接暴露在 API 调用和初始磁盘写入中。

- **音频处理 (`processor.py`)**:
    - **静音分割**: 自动检测音频中的静音部分并切割成独立小段。
    - **音视频匹配**: 通过计算音频与视频音轨的相似度（通常提取前几秒进行匹配），实现批量视频重命名，解决素材对应的痛点。
- **历史记录**: 使用 `history.db` 记录每次生成的详情，方便回溯和重新导出。

### 2.3 文件管理模块 (`modules/file_manager/`)
提供了一种“项目化”的文件组织方式。

- **智能导入 (`logic.py`)**: 
    - **宽容解析**: 使用 `csv` 模块处理从 Excel 或 Google Sheets 复制的制表符分隔文本，支持单元格内换行。
    - **链接识别**: 自动识别并提取链接，优先支持 Google Drive 链接的 ID 转换与直接下载。
- **文本预处理**: 包含去除多余空行、短行智能合并（提高 TTS 生成的自然度、减少停顿）等逻辑。
- **项目组织**: 每次导入可创建独立子文件夹，将生成的音频、视频、原始文本统一归档在 `global_output_path` 下。

---

## 3. 技术栈与环境要求

- **核心语言**: Python 3.10+
- **GUI 框架**: PyQt6
- **音频处理**: `pydub` (需安装 `ffmpeg`), `moviepy` (视频音轨提取)
- **网络访问**: `requests`, `google-generativeai`, `elevenlabs`
---

## 5. 常用的调试脚本
在根目录下有一些 `test_*.py` 或 `debug_*.py` 文件，可用于在脱离 GUI 的情况下测试核心算法，如 `test_audio_gen.py` 或 `debug_match.py`。
