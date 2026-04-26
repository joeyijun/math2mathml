# MathFlow

![Python](https://img.shields.io/badge/Python-3.x-blue.svg)
![Windows](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

MathFlow 是一个适用于 Windows 平台的公式识别与转换工具。它可以将屏幕截图中的数学公式，或纯文本的 LaTeX 代码，直接转换为 Microsoft Word/PPT 原生支持的 MathML 格式。

基于多模态大模型 API (如 Qwen-VL, GLM-4v, Gemini, GPT-4o 等) 进行图像识别。

## ✨ 核心特性

- 📸 **截图识别 (Alt+I)**：识别剪贴板中的图片公式，提取并在后台转换为 Office MathML 格式覆盖回剪贴板。
- ⌨️ **LaTeX 转换 (Alt+L)**：将剪贴板或选中的 LaTeX 文本直接转换为 Office MathML 格式。
- 🤖 **多模型支持**：兼容所有支持 OpenAI 接口格式的大模型视觉服务（阿里云、智谱、Kimi、MiniMax、Google、OpenAI 等）。
- 🪶 **轻量化**：使用原生 Win32 API 替代非必要的厚重依赖库（如 pyperclip），减少打包体积和内存占用。
- ⚙️ **配置便捷**：带界面配置应用参数，配置完成后可通过系统托盘在后台静默运行。

## 🎯 使用流程

1. 使用截图工具 (如快捷键 `Win+Shift+S`) 截取屏幕上的公式。
2. 按下 `Alt+I` 等待系统通知提示成功。
3. 在 Word 中使用 `Ctrl+V` 粘贴为原生公式。

*(提示：如果是已有的 LaTeX 公式文本，可先复制到剪贴板，然后按下 `Alt+L` 进行直接转换。)*

## 🚀 安装与运行

### 方式 1：执行预编译程序
1. 从 Releases 页面下载对应的 `MathFlow.exe`。
2. 运行程序，在界面中填写服务商的 API Key 与模型名称。
3. 点击保存并隐藏。

### 方式 2：使用源码运行或自主构建
1. 克隆相关代码：
   ```bash
   git clone https://github.com/joeyijun/math2mathml.git
   cd math2mathml
   ```

2. 安装主要依赖：
   ```bash
   pip install pillow keyboard pystray latex2mathml ttkbootstrap
   ```

3. 直接运行：
   ```bash
   python math2mathml.py
   ```

4. 打包文件：
   运行项目提供的 `build.bat` 脚本（已包含了剔除多余 Python 模块的逻辑）：
   ```cmd
   build.bat
   ```
   打包结果会生成在 `dist/MathFlow.exe` 目录内。

## 📋 配置项参考
源码运行会在同目录下存储应用配置 `config.json`。参考供例 `config.example.json`：

| 参数项        | 说明                                                    |
|-------------|-------------------------------------------------------|
| `api_key`   | 模型服务商提供的 API 鉴权密钥。发布代码前请注意不要泄露该文件。  |
| `base_url`  | Base URL 接口地址                                       |
| `model_name`| 使用的视觉大模型名（如 `qwen-vl-max` 或 `gpt-4o`）         |

## ⚠️ 注意事项
1. **网络延迟**：图片 OCR 识别过程依赖云端大模型的接口响应速率，通常网络耗时约 3~8 秒，识别期间未做强制弹窗干扰。
2. **快捷键冲突**：程序全局占用了 `Alt+I` 与 `Alt+L` 快捷键，请注意避开第三方软件的相同快捷键。
3. **Office 版本支持**：推荐 Microsoft Office 2016 及以上的较新版本测试原生粘贴体验。

## 📄 开源许可
本项目遵循 MIT 开源许可。
