import keyboard
import latex2mathml.converter
from PIL import ImageGrab, Image, ImageDraw, ImageFont
import io
import base64
import time
import json
import os
import re
import xml.etree.ElementTree as ET
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox
import pystray
import urllib.request
import urllib.error
from pystray import MenuItem as item
import threading
import ctypes

CONFIG_FILE = "config.json"

# --- Win32 剪贴板操作 (替代 pyperclip，节省打包体积) ---
CF_UNICODETEXT = 13

# 声明 Win32 API 的正确参数/返回类型，避免 64 位系统上指针被截断
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

_kernel32.GlobalAlloc.restype = ctypes.c_void_p
_kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
_kernel32.GlobalLock.restype = ctypes.c_void_p
_kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalSize.restype = ctypes.c_size_t
_kernel32.GlobalSize.argtypes = [ctypes.c_void_p]

_user32.OpenClipboard.argtypes = [ctypes.c_void_p]
_user32.GetClipboardData.restype = ctypes.c_void_p
_user32.GetClipboardData.argtypes = [ctypes.c_uint]
_user32.SetClipboardData.restype = ctypes.c_void_p
_user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]

def clipboard_copy(text):
    """将文本写入 Windows 剪贴板"""
    if not isinstance(text, str):
        text = str(text)
    _user32.OpenClipboard(None)
    try:
        _user32.EmptyClipboard()
        if text:
            data = text.encode('utf-16-le') + b'\x00\x00'
            h = _kernel32.GlobalAlloc(0x0042, len(data))
            p = _kernel32.GlobalLock(h)
            ctypes.memmove(p, data, len(data))
            _kernel32.GlobalUnlock(h)
            _user32.SetClipboardData(CF_UNICODETEXT, h)
    finally:
        _user32.CloseClipboard()

def clipboard_paste():
    """从 Windows 剪贴板读取文本"""
    _user32.OpenClipboard(None)
    try:
        h = _user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ''
        p = _kernel32.GlobalLock(h)
        try:
            size = _kernel32.GlobalSize(h)
            raw = ctypes.string_at(p, size)
            return raw.decode('utf-16-le').rstrip('\x00')
        finally:
            _kernel32.GlobalUnlock(h)
    finally:
        _user32.CloseClipboard()

# --- 0. 系统优化 ---
def optimize_process():
    try:
        _kernel32.SetPriorityClass(_kernel32.GetCurrentProcess(), 0x00004000)
    except Exception:
        pass
    
    # 针对 Windows，启用高 DPI 感知修复字体模糊
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1) # Windows 8.1+
    except Exception:
        try:
            _user32.SetProcessDPIAware() # Windows Vista+
        except Exception:
            pass

# --- 1. GUI 配置界面类 ---
class MathFlowApp:
    def __init__(self, reopen=False):
        if reopen:
            # 从托盘重新打开时在后台线程运行，ttkbootstrap.Window 不支持非主线程
            import tkinter
            self.root = tkinter.Tk()
        else:
            self.root = ttk.Window(themename="cosmo")
        self.root.withdraw()
        self.root.title("MathFlow 配置")
        self.root.resizable(False, False)
        self.root.minsize(460, 0)
        
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        
        # 窗口图标
        try:
            from PIL import ImageTk
            tray_img = create_tray_image()
            self.tk_icon = ImageTk.PhotoImage(tray_img)
            self.root.iconphoto(False, self.tk_icon)
        except Exception:
            pass
        
        self.config = {
            "api_key": "",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model_name": "qwen-vl-max"
        }
        self.load_config()
        self.should_run = False
        self._key_visible = False
        
        self.create_widgets()
        
        self.root.bind('<Return>', lambda e: self.start_main())
        
        self.root.update_idletasks()
        self.root.eval('tk::PlaceWindow . center')
        self.root.deiconify()
    
    def _on_close(self):
        if messagebox.askokcancel("MathFlow", "确定要退出吗？\n点击“取消”可返回继续配置。"):
            self.root.quit()
            self.root.destroy()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.config.update(json.load(f))
            except Exception:
                pass

    def save_config(self):
        self.config["api_key"] = self.entry_key.get().strip()
        self.config["base_url"] = self.combo_url.get().strip()
        self.config["model_name"] = self.combo_model.get().strip()
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=30)
        main_frame.pack(fill=BOTH, expand=YES)

        # 标题
        ttk.Label(main_frame, text="MathFlow", font=("Segoe UI", 24, "bold")).pack(pady=(0, 2))
        ttk.Label(main_frame, text="全局数学公式识别与转换引擎", font=("Segoe UI", 10),
                  bootstyle="secondary").pack(pady=(0, 25))

        # API Key + 显隐切换
        ttk.Label(main_frame, text="🔑 API Key (必填)", font=("Segoe UI", 10, "bold")).pack(anchor=W, pady=(0, 5))
        key_frame = ttk.Frame(main_frame)
        key_frame.pack(fill=X, pady=(0, 15))
        self.entry_key = ttk.Entry(key_frame, show="*")
        self.entry_key.insert(0, self.config["api_key"])
        self.entry_key.pack(side=LEFT, fill=X, expand=YES)
        self.eye_btn = ttk.Button(key_frame, text="👁", command=self._toggle_key_visibility,
                                   bootstyle="secondary-link", width=3)
        self.eye_btn.pack(side=RIGHT, padx=(5, 0))

        # Base URL
        ttk.Label(main_frame, text="🔗 API 接口地址 (Base URL)", font=("Segoe UI", 10, "bold")).pack(anchor=W, pady=(0, 5))
        urls = [
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "https://open.bigmodel.cn/api/paas/v4/",
            "https://api.moonshot.cn/v1",
            "https://api.minimax.chat/v1",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
            "https://api.lingyiwanwu.com/v1",
            "https://api.siliconflow.cn/v1",
            "https://api.openai.com/v1"
        ]
        self.combo_url = ttk.Combobox(main_frame, values=urls)
        self.combo_url.set(self.config["base_url"])
        self.combo_url.pack(fill=X, pady=(0, 15))

        # Model Name
        ttk.Label(main_frame, text="🤖 模型名称 (支持手写输入新模型)", font=("Segoe UI", 10, "bold")).pack(anchor=W, pady=(0, 5))
        models = [
            "qwen3-vl-flash", "qwen3-vl-plus",
            "glm-4v", "glm-4v-plus",
            "moonshot-v1-8k-vision-preview",
            "abab6.5s-chat",
            "gemini-2.0-flash-lite", "gemini-2.0-flash",
            "yi-vision",
            "Qwen/Qwen2-VL-72B-Instruct",
            "gpt-4o", "gpt-4o-mini"
        ]
        self.combo_model = ttk.Combobox(main_frame, values=models)
        self.combo_model.set(self.config["model_name"])
        self.combo_model.pack(fill=X, pady=(0, 25))

        # 保存按钮
        ttk.Button(main_frame, text="保存并隐藏至任务栏", command=self.start_main,
                   bootstyle="primary", cursor="hand2",
                   padding=(0, 12)).pack(fill=X, pady=(0, 15))

        # 快捷键提示
        ttk.Label(main_frame,
                  text="快捷键指引:\nAlt+I: 截图识别公式    |    Alt+L: 复制LaTeX转MathML\n(在托盘栏右键图标可退出程序)",
                  font=("Segoe UI", 9), bootstyle="secondary",
                  justify=CENTER).pack(side=BOTTOM, pady=(10, 0))
    
    def _toggle_key_visibility(self):
        self._key_visible = not self._key_visible
        self.entry_key.configure(show="" if self._key_visible else "*")
        self.eye_btn.configure(text="🔒" if self._key_visible else "👁")

    def start_main(self):
        if not self.entry_key.get().strip():
            messagebox.showwarning("提示", "API Key 不能为空！")
            return
        if not self.combo_url.get().strip() or not self.combo_model.get().strip():
            messagebox.showwarning("提示", "接口地址和模型名称不能为空！")
            return
        self.save_config()
        self.should_run = True
        self.root.quit()
        self.root.destroy()

# --- 2. 公共工具函数 ---
def _truncate_error(e, max_len=60):
    msg = str(e)
    return msg[:max_len] + "..." if len(msg) > max_len else msg

def image_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)  # JPEG 比 PNG 体积小 ~60%，OCR 足够
    result = base64.b64encode(buffered.getvalue()).decode('utf-8')
    buffered.close()
    return result

def clean_latex(latex_str):
    """清理 AI 或用户输入中可能携带的多余标记"""
    latex_str = latex_str.strip()
    # 剥离代码块围栏
    for fence in ('```latex', '```math', '```'):
        if latex_str.startswith(fence):
            latex_str = latex_str[len(fence):]
            break
    if latex_str.endswith('```'):
        latex_str = latex_str[:-3]
    latex_str = latex_str.strip()
    # 剥离美元符定界符：逐层剥离，先 $$...$$ 再 $...$
    if latex_str.startswith('$$') and latex_str.endswith('$$'):
        latex_str = latex_str[2:-2].strip()
    elif latex_str.startswith('$') and latex_str.endswith('$'):
        latex_str = latex_str[1:-1].strip()
    # 剥离 \[ \] 和 \( \) 定界符
    if latex_str.startswith(r'\[') and latex_str.endswith(r'\]'):
        latex_str = latex_str[2:-2].strip()
    elif latex_str.startswith(r'\(') and latex_str.endswith(r'\)'):
        latex_str = latex_str[2:-2].strip()
    return latex_str

# 预编译正则：避免每次调用 to_office_mathml 时重复编译
_RE_ALIGN_BEGIN = re.compile(r'\\begin\{align\*?\}|\\begin\{aligned\}')
_RE_ALIGN_END = re.compile(r'\\end\{align\*?\}|\\end\{aligned\}')
_RE_BARE_AMP = re.compile(r'&(?!(?:#[xX]?[0-9a-fA-F]+|[a-zA-Z]+);)')

def to_office_mathml(latex_expr):
    """LaTeX → Office MathML 字符串"""
    # 预处理：Office 的内置公式不支持 aligned，会导致 latex2mathml 输出包含非法 & 的单行公式。
    # 把它转化为标准的 array 环境来激活原生的 mtable 表格对齐功能。
    latex_expr = _RE_ALIGN_BEGIN.sub(r'\\begin{array}{rl}', latex_expr)
    latex_expr = _RE_ALIGN_END.sub(r'\\end{array}', latex_expr)
    
    try:
        mathml_str = latex2mathml.converter.convert(latex_expr)
    except Exception as e:
        raise RuntimeError(f"LaTeX转换失败: {e}")
        
    # 安全转义 XML 字符串中的意外 &，避免破坏诸如 &#x003C6; 的规范实体
    mathml_str = _RE_BARE_AMP.sub('&amp;', mathml_str)
    
    # 吸收 Web 版的精确解析优势：使用 XML DOM 解析器处理而不依赖脆弱的文本生成
    try:
        # 保留无前缀的 namespace 避免标签乱码
        ET.register_namespace('', 'http://www.w3.org/1998/Math/MathML')
        root = ET.fromstring(mathml_str)
        
        # DOM 属性规范：补充 xmlns 并在展示模式显示 (同网页版的 display='block')
        if 'xmlns' not in root.attrib and not root.tag.startswith('{'):
            root.set('xmlns', 'http://www.w3.org/1998/Math/MathML')
        root.set('display', 'block')
        
        # 将 DOM 树安全序列化回严格的 XML 字符串
        mathml_str = ET.tostring(root, encoding='unicode', method='xml')
    except Exception as e:
        print(f"XML 稳健解析跳过，使用回退方案: {e}")
        
    return '<?xml version="1.0"?>\n' + mathml_str

# --- 3. 全局状态 ---
tray_icon = None
is_processing = False  # 防止图像识别重复触发

# --- 4. 功能一：截图识别公式 (Alt+I) ---
def on_image_hotkey_pressed(api_key, base_url, model_name):
    global is_processing, tray_icon
    if is_processing:
        return
    is_processing = True

    img = ImageGrab.grabclipboard()
    if img is None:
        if tray_icon:
            tray_icon.notify("\u526a\u8d34\u677f\u91cc\u6ca1\u6709\u56fe\u7247\uff01\u8bf7\u5148\u622a\u56fe\u3002", "MathFlow \u63d0\u793a")
        is_processing = False
        return
    try:
        # grabclipboard 在有些截图工具下返回的是文件路径列表而非 Image
        if isinstance(img, list):
            img = Image.open(img[0])
        if img.mode != 'RGB':
            img = img.convert('RGB')

        base64_image = image_to_base64(img)
        del img  # 尽早释放截图对象
        
        # 使用内置的 urllib 替代重型的 openai 库（可大幅降低 PyInstaller 构建体积，极大节省内容占用）
        if not base_url.endswith('/'):
            base_url += '/'
        api_endpoint = base_url if "chat/completions" in base_url else base_url + "chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": model_name,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "You are an expert mathematician and OCR engine. Your task is to transcribe the mathematical formulas in the provided image into valid, standard LaTeX. Output ONLY the raw LaTeX representation of the visible math. Math equations should be properly formatted. IMPORTANT: If there are multiple lines of equations, wrap them in a \\begin{array}{rl} ... \\end{array} block (DO NOT use aligned) and use \\\\ for line breaks. Do not include markdown code blocks like ```latex or ```. Ensure superscripts, subscripts, fractions, matrices, and greek letters are precisely transcribed."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]}],
            "temperature": 0.1
        }
        req = urllib.request.Request(api_endpoint, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result_json = json.loads(response.read().decode('utf-8'))
                latex_result = result_json['choices'][0]['message']['content']
        except urllib.error.URLError as http_e:
            err_msg = str(http_e)
            if hasattr(http_e, 'read'):
                err_msg += " " + http_e.read().decode('utf-8', errors='ignore')
            raise RuntimeError(f"HTTP/网络错误: {err_msg}")
        del base64_image  # 释放 base64 字符串
        clean_expr = clean_latex(latex_result)
        clipboard_copy(to_office_mathml(clean_expr))

        if tray_icon:
            tray_icon.notify("✅ 识别成功！已复制 MathML，去粘贴吧。", "MathFlow 成功")

    except Exception as e:
        if tray_icon:
            tray_icon.notify(f"\u274c \u8bc6\u522b\u5931\u8d25: {_truncate_error(e)}", "MathFlow \u9519\u8bef")
    finally:
        is_processing = False

# --- 5. 功能二：选中 LaTeX 文本转 MathML (Alt+L) ---
def on_latex_hotkey_pressed():
    keyboard.release('alt')
    keyboard.release('l')

    old_cb = clipboard_paste()
    clipboard_copy('')
    keyboard.send('ctrl+c')
    time.sleep(0.1)  # 等系统完成复制写入

    latex_input = ''
    for _ in range(15):  # 最多再等 0.75 秒
        current = clipboard_paste()
        if current:
            latex_input = current
            break
        time.sleep(0.05)

    if not latex_input or not latex_input.strip() or len(latex_input) > 2000:
        if old_cb: 
            clipboard_copy(old_cb) # 恢复原剪贴板内容
        return  # 静默失败

    clean_expr = clean_latex(latex_input)
    try:
        clipboard_copy(to_office_mathml(clean_expr))
        if tray_icon:
            tray_icon.notify("✅ 转换成功！已复制 MathML，去粘贴吧。", "LaTeX → MathML")
    except Exception as e:
        if tray_icon:
            tray_icon.notify(f"\u274c \u8f6c\u6362\u5931\u8d25: {_truncate_error(e)}", "LaTeX \u2192 MathML \u9519\u8bef")

# --- 6. 系统托盘 ---
_tray_image_cache = None

def create_tray_image():
    global _tray_image_cache
    if _tray_image_cache is not None:
        return _tray_image_cache
    image = Image.new('RGB', (64, 64), color=(24, 54, 43)) # 高级的剑桥绿
    dc = ImageDraw.Draw(image)
    try:
        # 尝试绘制字符图标
        font = ImageFont.truetype("msyhbd.ttc", 40) # 尝试载入粗体微软雅黑
        dc.text((12, 4), "Σ", fill="white", font=font)
    except Exception:
        try:
            font = ImageFont.truetype("arialbd.ttf", 44) # 退行到 Arial Bold
            dc.text((15, 6), "Σ", fill="white", font=font)
        except Exception:
            # 基础绘制退行方案
            dc.rectangle((16, 16, 48, 48), fill=(255, 255, 255))
            dc.rectangle((24, 24, 40, 40), fill=(0, 120, 215))
    _tray_image_cache = image
    return image

def quit_action(icon, item):
    icon.stop()
    keyboard.unhook_all()
    os._exit(0)

# --- 主程序入口 ---
def load_and_apply_config():
    global tray_icon
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        conf = json.load(f)
        
    keyboard.unhook_all()
    keyboard.add_hotkey('alt+i', lambda: threading.Thread(
        target=on_image_hotkey_pressed,
        args=(conf["api_key"], conf["base_url"], conf["model_name"]),
        daemon=True
    ).start())
    
    keyboard.add_hotkey('alt+l', lambda: threading.Thread(
        target=on_latex_hotkey_pressed,
        daemon=True
    ).start())

def open_settings_action(icon, item):
    def run_ui():
        app2 = MathFlowApp(reopen=True)
        app2.root.mainloop()
        if app2.should_run:
            load_and_apply_config()
            if tray_icon:
                tray_icon.notify("设置已更新并生效！", "MathFlow 提示")
    threading.Thread(target=run_ui, daemon=True).start()

if __name__ == "__main__":
    optimize_process()

    app = MathFlowApp()
    app.root.mainloop()

    if app.should_run:
        load_and_apply_config()

        menu = pystray.Menu(
            item('⚙️ 设置模型参数', open_settings_action),
            pystray.Menu.SEPARATOR,
            item('Alt+I  截图识别公式', lambda *_: None, enabled=False),
            item('Alt+L  LaTeX转MathML', lambda *_: None, enabled=False),
            pystray.Menu.SEPARATOR,
            item('退出 MathFlow', quit_action)
        )
        tray_icon = pystray.Icon("MathFlow", create_tray_image(), "MathFlow (Alt+I / Alt+L)", menu)
        tray_icon.run()