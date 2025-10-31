import json
import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QGridLayout, QWidget, QPushButton
from PyQt5 import uic
import subprocess
import time
import os
import urllib.request
import urllib.error
import ctypes
from PyQt5.QtCore import QMimeData
from PyQt5.QtGui import QDrag
import shutil
import re
import socket
from threading import Thread
import glob
import socket


# 在这里添加新函数
def get_base_path():
    """获取程序基础路径，兼容开发环境和打包后的exe"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的exe，获取exe所在目录的上级目录
        exe_dir = os.path.dirname(sys.executable)
        return os.path.dirname(exe_dir)  # 返回上级目录
    else:
        # 如果是开发环境，返回Python文件所在目录的上级目录
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_app_path():
    """获取程序运行的主目录，无论是开发环境还是打包后的exe"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的exe，获取exe所在的目录
        return os.path.dirname(sys.executable)
    else:
        # 如果是开发环境，返回Python文件所在的目录
        return os.path.dirname(os.path.abspath(__file__))


def load_tool_descriptions():
    """加载所有工具的名称和描述"""
    tool_descriptions = {}
    fc_tools = set()  # Function Call工具集合
    mcp_tools = set()  # MCP工具集合

    try:
        # 获取server-tools目录路径
        app_path = get_app_path()
        server_tools_path = os.path.join(app_path, "server-tools")

        if not os.path.exists(server_tools_path):
            print(f"server-tools目录不存在: {server_tools_path}")
            return tool_descriptions, fc_tools, mcp_tools

        # 加载Function Call工具描述（server-tools目录）
        js_files = glob.glob(os.path.join(server_tools_path, "*.js"))
        js_files = [f for f in js_files if not f.endswith("index.js")]

        for file_path in js_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 使用更灵活的正则表达式提取工具定义
                # 支持跨行和不同的引号格式
                pattern = r'name:\s*["\']([^"\']+)["\']\s*,\s*description:\s*["\']([^"\']*(?:[^"\'\\]|\\.)*)["\']'
                matches = re.findall(pattern, content, re.DOTALL)

                file_tools = []
                for name, description in matches:
                    # 清理描述文本，移除多余的空白
                    clean_description = re.sub(r'\s+', ' ', description.strip())
                    tool_descriptions[name] = clean_description
                    fc_tools.add(name)  # 记录为Function Call工具
                    file_tools.append(name)

                if file_tools:
                    filename = os.path.basename(file_path)
                    print(f"文件 {filename} 包含工具: {', '.join(file_tools)}")

            except Exception as e:
                print(f"读取工具文件失败 {file_path}: {e}")

        # 加载MCP工具描述（mcp/tools目录）
        mcp_tools_path = os.path.join(app_path, "mcp", "tools")
        if os.path.exists(mcp_tools_path):
            mcp_js_files = glob.glob(os.path.join(mcp_tools_path, "*.js"))

            for file_path in mcp_js_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # MCP工具使用不同的格式：name: "tool_name", description: "描述"
                    pattern = r'name:\s*["\']([^"\']+)["\']\s*,\s*description:\s*["\']([^"\']*(?:[^"\'\\]|\\.)*)["\']'
                    matches = re.findall(pattern, content, re.DOTALL)

                    file_tools = []
                    for name, description in matches:
                        clean_description = re.sub(r'\s+', ' ', description.strip())
                        tool_descriptions[name] = clean_description
                        mcp_tools.add(name)  # 记录为MCP工具
                        file_tools.append(name)

                    if file_tools:
                        filename = os.path.basename(file_path)
                        print(f"MCP文件 {filename} 包含工具: {', '.join(file_tools)}")

                except Exception as e:
                    print(f"读取MCP工具文件失败 {file_path}: {e}")

    except Exception as e:
        print(f"加载工具描述失败: {e}")

    return tool_descriptions, fc_tools, mcp_tools


class LogReader(QThread):
    """读取日志文件的线程"""
    log_signal = pyqtSignal(str)

    def __init__(self, log_file_path):
        super().__init__()
        self.log_file_path = log_file_path
        self.running = True

    def run(self):
        """实时读取日志文件"""
        while not os.path.exists(self.log_file_path) and self.running:
            time.sleep(0.1)

        if not self.running:
            return

        encodings = ['utf-8', 'gbk']
        file_handle = None

        for encoding in encodings:
            try:
                file_handle = open(self.log_file_path, 'r', encoding=encoding, errors='ignore')
                file_handle.seek(0, 2)
                break
            except Exception:
                if file_handle:
                    file_handle.close()
                continue

        if not file_handle:
            return

        try:
            while self.running:
                line = file_handle.readline()
                if line:
                    self.log_signal.emit(line.strip())
                else:
                    time.sleep(0.1)
        except Exception:
            pass
        finally:
            if file_handle:
                file_handle.close()

    def stop(self):
        self.running = False


class ToastNotification(QLabel):
    """自定义Toast提示"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 rgba(255, 255, 255, 240), 
                    stop:1 rgba(248, 248, 248, 240));
                color: rgb(60, 60, 60);
                border: 1px solid rgba(200, 200, 200, 150);
                border-radius: 15px;
                padding: 18px 36px;
                font-size: 16px;
                font-family: "Microsoft YaHei";
                font-weight: normal;
            }
        """)
        self.hide()

        # 创建动画效果
        self.effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.effect)

        self.slide_animation = QPropertyAnimation(self, b"pos")
        self.slide_animation.setDuration(300)
        self.slide_animation.setEasingCurve(QEasingCurve.OutCubic)

        self.opacity_animation = QPropertyAnimation(self.effect, b"opacity")
        self.opacity_animation.setDuration(300)

    def show_message(self, message, duration=2000):
        """显示消息，duration为显示时长（毫秒）"""
        self.setText(message)
        self.adjustSize()

        # 计算位置
        parent = self.parent()
        if parent:
            x = (parent.width() - self.width()) // 2
            start_y = -self.height()  # 从顶部外面开始
            end_y = 20  # 最终位置距离顶部20像素

            # 设置起始位置
            self.move(x, start_y)
            self.show()
            self.raise_()

            # 滑入动画
            self.slide_animation.setStartValue(QPoint(x, start_y))
            self.slide_animation.setEndValue(QPoint(x, end_y))

            # 透明度渐入
            self.opacity_animation.setStartValue(0.0)
            self.opacity_animation.setEndValue(1.0)

            # 开始动画
            self.slide_animation.start()
            self.opacity_animation.start()

            # 延迟后滑出
            QTimer.singleShot(duration, self.hide_with_animation)

    def hide_with_animation(self):
        """带动画的隐藏"""
        parent = self.parent()
        if parent:
            current_pos = self.pos()
            end_y = -self.height()

            # 滑出动画
            self.slide_animation.setStartValue(current_pos)
            self.slide_animation.setEndValue(QPoint(current_pos.x(), end_y))

            # 透明度渐出
            self.opacity_animation.setStartValue(1.0)
            self.opacity_animation.setEndValue(0.0)

            # 动画完成后隐藏
            self.slide_animation.finished.connect(self.hide)

            # 开始动画
            self.slide_animation.start()
            self.opacity_animation.start()


class CustomTitleBar(QWidget):
    """自定义标题栏"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(55)
        self.setStyleSheet("""
           CustomTitleBar {
               background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(235, 233, 225, 255), stop:1 rgba(230, 228, 220, 255));
               border: none;
               border-radius: 25px 25px 0px 0px;
           }
       """)
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 5, 0)
        layout.setSpacing(0)

        # 标题
        self.title_label = QLabel()
        self.title_label.setStyleSheet("""
           QLabel {
               color: rgb(114, 95, 77);
               font-size: 12px;
               font-family: "Microsoft YaHei";
               font-weight: bold;
               background-color: transparent;
           }
       """)

        layout.addWidget(self.title_label)
        layout.addStretch()

        # 窗口控制按钮
        button_style = """
           QPushButton {
               background-color: transparent;
               border: none;
               width: 45px;
               height: 40px;
               font-size: 14px;
               font-weight: bold;
               color: rgb(114, 95, 77);
           }
           QPushButton:hover {
               background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(200, 195, 185, 255), stop:1 rgba(180, 175, 165, 255));
               color: rgb(40, 35, 25);
               border-radius: 5px;
           }
       """

        close_style = """
           QPushButton {
               background-color: transparent;
               border: none;
               width: 45px;
               height: 40px;
               font-size: 14px;
               font-weight: bold;
               color: rgb(114, 95, 77);
           }
           QPushButton:hover {
               background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(255, 182, 193, 255), stop:1 rgba(255, 160, 122, 255));
               color: rgb(139, 69, 19);
               border-radius: 5px;
           }
       """

        # 最小化按钮
        self.min_btn = QPushButton("−")
        self.min_btn.setStyleSheet(button_style)
        self.min_btn.clicked.connect(self.parent.showMinimized)

        # 最大化/还原按钮
        self.max_btn = QPushButton("□")
        self.max_btn.setStyleSheet(button_style)
        self.max_btn.clicked.connect(self.toggle_maximize)

        # 关闭按钮
        self.close_btn = QPushButton("×")
        self.close_btn.setStyleSheet(close_style)
        self.close_btn.clicked.connect(self.parent.close)

        layout.addWidget(self.min_btn)
        layout.addWidget(self.max_btn)
        layout.addWidget(self.close_btn)

    def toggle_maximize(self):
        """切换最大化状态"""
        if self.parent.isMaximized():
            self.parent.showNormal()
            self.max_btn.setText("□")
        else:
            self.parent.showMaximized()
            self.max_btn.setText("◱")

    def mousePressEvent(self, event):
        """鼠标按下事件 - 用于拖拽窗口"""
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.parent.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 拖拽窗口"""
        if event.buttons() == Qt.LeftButton and hasattr(self, 'drag_pos'):
            self.parent.move(event.globalPos() - self.drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        """双击标题栏最大化/还原"""
        if event.button() == Qt.LeftButton:
            self.toggle_maximize()

def is_server_running(host='localhost', port=3002):
    """检查指定端口的服务是否正在运行"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.1)  # 设置一个0.1秒的超短超时
        try:
            s.connect((host, port))
            return True
        except (socket.timeout, ConnectionRefusedError):
            return False

class set_pyqt(QWidget):
    # 添加信号用于线程安全的日志更新
    log_signal = pyqtSignal(str)
    mcp_log_signal = pyqtSignal(str)
    scan_complete_signal = pyqtSignal()

    def _on_scan_complete(self):
        """在主线程中安全地刷新UI"""
        print("扫描完成，正在刷新UI...")
        self.refresh_model_list()
        self.load_motion_config()
        self.refresh_drag_drop_interface()
        print("UI刷新完成。")

    def __init__(self):
        super().__init__()
        self.live2d_process = None
        self.tools_enabled = False  # 工具调用功能状态，默认关闭
        self.mcp_enabled = False    # MCP功能状态，默认关闭
        self.terminal_process = None  # 新增：后台终端进程
        self.asr_process = None  # 新增：ASR进程
        self.bert_process = None  # 新增：BERT进程
        self.rag_process = None  # 新增：RAG进程
        self.voice_clone_process = None  # 新增：声音克隆进程
        self.minecraft_terminal_process = None  # 新增：Minecraft终端进程
        self.selected_model_path = None  # 选择的模型文件路径
        self.selected_audio_path = None  # 选择的音频文件路径
        self.config_path = 'config.json'
        self.config = self.load_config()

        # 日志读取相关
        self.log_readers = {}
        self.log_file_paths = {
            'asr': r"..\logs\asr.log",
            'tts': r"..\logs\tts.log",
            'bert': r"..\logs\bert.log",
            'rag': r"..\logs\rag.log"
        }

        # 加载工具描述
        self.tool_descriptions, self.fc_tools, self.mcp_tools = load_tool_descriptions()

        # 调整大小相关变量
        self.resizing = False
        self.resize_edge = None
        self.resize_start_pos = None
        self.resize_start_geometry = None
        self.edge_margin = 10

        # 新增分页变量
        self.current_page = 0
        self.items_per_page = 15
        self.pagination_widget = None
        self.unclassified_actions_cache = []


        self.init_ui()
        self.init_live2d_models()


        self.check_all_service_status()
        self.run_startup_scan()  # 添加这行
        self.drag_start_position = None
        self.dragged_action = None
        # 备份原始配置
        self.original_config = None
        self.backup_original_config()

        # --- 核心修复：连接后台扫描完成信号到UI刷新槽 ---
        self.scan_complete_signal.connect(self._on_scan_complete)

        # --- 性能优化：为MouseMove事件添加节流 ---
        self.can_process_mousemove = True
        self.mousemove_timer = QTimer(self)
        self.mousemove_timer.setInterval(16)  # ~60 FPS
        self.mousemove_timer.timeout.connect(lambda: setattr(self, 'can_process_mousemove', True))
        self.mousemove_timer.start()

    def init_ui(self):
        # 设置无边框
        self.setWindowFlags(Qt.FramelessWindowHint)

        # 启用透明背景
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 启用鼠标跟踪
        self.setMouseTracking(True)

        # 为整个应用安装事件过滤器
        app = QApplication.instance()
        app.installEventFilter(self)

        # 添加圆角样式 - 改为浅色渐变
        self.setStyleSheet("""
            QWidget {
                border-radius: 25px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(250, 249, 245, 255), stop:0.5 rgba(245, 243, 235, 255), stop:1 rgba(240, 238, 230, 255));
            }
        """)

        # 加载原始UI文件
        self.ui = uic.loadUi('test222.ui')

        # self.ui.label_model_status.setText("未上传模型文件 (.pth)")
        # self.ui.label_audio_status.setText("未上传参考音频 (.wav)")
        # self.ui.label_bat_status.setText("状态：请上传文件并生成配置")

        # 添加下面这行代码来让声音克隆页面支持拖放
        self.ui.tab_tts_switch.setAcceptDrops(True)
        self.ui.tab_tts_switch.dragEnterEvent = self.voice_clone_dragEnterEvent
        self.ui.tab_tts_switch.dropEvent = self.voice_clone_dropEvent

        # 隐藏状态栏
        self.ui.statusbar.hide()

        # 创建一个容器来装标题栏和原UI
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # 添加自定义标题栏
        self.title_bar = CustomTitleBar(self)
        container_layout.addWidget(self.title_bar)

        # 添加原始UI
        container_layout.addWidget(self.ui)

        # 设置主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)

        # 设置窗口大小
        # 获取桌面尺寸
        desktop = QApplication.desktop()
        screen_rect = desktop.screenGeometry()

        # 计算合理的窗口大小
        width = int(screen_rect.width() * 0.45)
        height = int(screen_rect.height() * 0.55)

        # 设置窗口大小
        self.resize(width, height)


        # 设置最小尺寸为1x1，允许任意缩小
        # self.setMinimumSize(1, 1)

        # 保持原来的功能
        self.set_btu()
        self.set_config()

        # 为API KEY输入框添加小眼睛图标
        self.setup_api_key_visibility_toggles()

        # 修改复选框布局为水平布局
        self.modify_checkbox_layout()

        # 创建Toast提示
        self.toast = ToastNotification(self)

        # 初始化时刷新工具列表
        self.refresh_tools_list()
        self.refresh_mcp_tools_list()

        # 根据UI复选框状态初始化开关（必须在日志信号连接之前设置）
        self.mcp_enabled = self.ui.checkBox_mcp_enable.isChecked()  # MCP功能开关
        self.tools_enabled = self.ui.checkBox_mcp.isChecked()       # 工具调用功能开关

        # 加载最近的日志记录
        self.load_recent_logs()

        # 连接日志信号
        self.log_signal.connect(self.update_log)
        self.mcp_log_signal.connect(self.update_tool_log)

        # 设置动画控制按钮
        self.setup_motion_buttons()

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        try:
            # 重新加载配置，确保使用最新的设置
            try:
                self.config = self.load_config()
            except Exception as e:
                print(f"重新加载配置失败: {e}")

            # 检查是否启用了自动关闭服务功能
            auto_close_config = self.config.get('auto_close_services', {})
            if auto_close_config.get('enabled', True):
                print("自动关闭所有服务...")

                # 关闭各种服务进程
                self.stop_asr()
                self.stop_bert()
                self.stop_rag()
                self.stop_voice_tts()
                self.stop_terminal()
                self.stop_minecraft_terminal()

                # 关闭桌宠进程
                self.close_live_2d()

                print("所有服务已关闭")
            else:
                print("未启用自动关闭服务，只关闭UI界面")

        except Exception as e:
            print(f"关闭服务时出错: {e}")

        # 停止日志读取线程
        for reader in self.log_readers.values():
            if reader and reader.isRunning():
                reader.stop()
                reader.wait(1000)  # 等待最多1秒

        # 接受关闭事件
        event.accept()

    def update_service_log(self, service_name, text):
        """更新指定服务的日志显示"""
        log_widgets = {
            'asr': getattr(self.ui, 'textEdit_asr_log', None),
            'tts': getattr(self.ui, 'textEdit_tts_log', None),
            'bert': getattr(self.ui, 'textEdit_bert_log', None),
            'rag': getattr(self.ui, 'textEdit_rag_log', None)
        }

        widget = log_widgets.get(service_name)
        if widget:
            widget.append(text)
            scrollbar = widget.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def load_recent_logs(self, max_lines=10):
        """加载最近的日志记录到UI界面，并启动日志读取线程"""
        log_widgets = {
            'asr': getattr(self.ui, 'textEdit_asr_log', None),
            'tts': getattr(self.ui, 'textEdit_tts_log', None),
            'bert': getattr(self.ui, 'textEdit_bert_log', None),
            'rag': getattr(self.ui, 'textEdit_rag_log', None)
        }

        for service_name, widget in log_widgets.items():
            if widget:
                log_file = self.log_file_paths.get(service_name)
                if log_file and os.path.exists(log_file):
                    try:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            # 获取最后max_lines行
                            recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines

                            # 清空当前内容并加载历史日志
                            widget.clear()
                            for line in recent_lines:
                                line = line.strip()
                                if line:  # 只添加非空行
                                    widget.append(line)

                            # 滚动到底部
                            scrollbar = widget.verticalScrollBar()
                            scrollbar.setValue(scrollbar.maximum())

                        # 启动日志读取线程来实时监控日志文件更新
                        if service_name in self.log_readers:
                            # 如果已有读取线程，先停止它
                            self.log_readers[service_name].stop()
                            self.log_readers[service_name].wait()

                        self.log_readers[service_name] = LogReader(log_file)
                        self.log_readers[service_name].log_signal.connect(
                            lambda text, sn=service_name: self.update_service_log(sn, text)
                        )
                        self.log_readers[service_name].start()
                        print(f"已启动{service_name}日志监控线程")

                    except Exception as e:
                        print(f"加载{service_name}日志失败: {str(e)}")

    def voice_clone_dragEnterEvent(self, event: QDragEnterEvent):
        """
        处理拖拽对象进入控件区域的事件。
        """
        # 检查拖拽的数据中是否包含URL（也就是文件）
        if event.mimeData().hasUrls():
            # 获取第一个URL来检查文件类型
            url = event.mimeData().urls()[0]
            if url.isLocalFile():
                file_path = url.toLocalFile()
                # 如果是 .pth 或 .wav 文件，就接受这个拖放动作
                if file_path.lower().endswith(('.pth', '.wav')):
                    event.acceptProposedAction()

    def voice_clone_dropEvent(self, event: QDropEvent):
        """
        处理文件在控件上被释放（放下）的事件。
        """
        for url in event.mimeData().urls():
            if url.isLocalFile():
                file_path = url.toLocalFile()
                filename = os.path.basename(file_path)

                # 确保目标文件夹存在
                app_path = get_app_path()
                voice_model_dir = os.path.join(app_path, "Voice_Model_Factory")
                if not os.path.exists(voice_model_dir):
                    os.makedirs(voice_model_dir)

                dest_path = os.path.join(voice_model_dir, filename)

                try:
                    # 复制文件
                    shutil.copy2(file_path, dest_path)

                    # 根据文件类型，更新对应的UI元素
                    if file_path.lower().endswith('.pth'):
                        self.selected_model_path = dest_path
                        self.ui.label_model_status.setText(f"已上传：{filename}")
                        self.toast.show_message(f"模型已拖拽上传至 Voice_Model_Factory", 2000)

                    elif file_path.lower().endswith('.wav'):
                        self.selected_audio_path = dest_path
                        self.ui.label_audio_status.setText(f"已上传：{filename}")
                        self.toast.show_message(f"音频已拖拽上传至 Voice_Model_Factory", 2000)

                except Exception as e:
                    self.toast.show_message(f"文件处理失败: {str(e)}", 3000)

    # 添加文件选择方法：
    def select_model_file(self):
        """选择模型文件"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择模型文件",
                "",
                "PyTorch模型文件 (*.pth);;所有文件 (*)"
            )

            if file_path:
                # 确保Voice_Model_Factory文件夹存在
                app_path = get_app_path()
                voice_model_dir = os.path.join(app_path, "Voice_Model_Factory")
                if not os.path.exists(voice_model_dir):
                    os.makedirs(voice_model_dir)

                # 复制文件到Voice_Model_Factory文件夹
                shutil.copy2(file_path, dest_path)

                self.selected_model_path = dest_path
                self.ui.label_model_status.setText(f"已上传：{filename}")
                self.toast.show_message(f"模型文件已保存到Voice_Model_Factory", 2000)

        except Exception as e:
            self.toast.show_message(f"选择模型文件失败：{str(e)}", 3000)

    def select_audio_file(self):
        """选择音频文件"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择音频文件",
                "",
                "音频文件 (*.wav);;所有文件 (*)"
            )

            if file_path:
                # 确保Voice_Model_Factory文件夹存在
                app_path = get_app_path()
                voice_model_dir = os.path.join(app_path, "Voice_Model_Factory")
                if not os.path.exists(voice_model_dir):
                    os.makedirs(voice_model_dir)

                # 复制文件到Voice_Model_Factory文件夹
                shutil.copy2(file_path, dest_path)

                self.selected_audio_path = dest_path
                self.ui.label_audio_status.setText(f"已上传：{filename}")
                self.toast.show_message(f"音频文件已保存到Voice_Model_Factory", 2000)

        except Exception as e:
            self.toast.show_message(f"选择音频文件失败：{str(e)}", 3000)

    def generate_voice_clone_bat(self):
        """使用上传文件生成声音克隆的bat文件"""
        try:
            # 获取用户输入
            text = self.ui.textEdit_voice_text.toPlainText().strip()
            if not text:
                self.toast.show_message("请输入要合成的文本内容", 2000)
                return

            character_name = self.ui.lineEdit_character_name.text().strip()
            if not character_name:
                self.toast.show_message("请输入角色名称", 2000)
                return

            # 检查是否已选择文件
            if not self.selected_model_path or not os.path.exists(self.selected_model_path):
                self.toast.show_message("请先选择模型文件", 2000)
                return

            if not self.selected_audio_path or not os.path.exists(self.selected_audio_path):
                self.toast.show_message("请先选择音频文件", 2000)
                return

            # 获取语言选择
            language = self.ui.comboBox_language.currentText().split(' - ')[0]  # 提取语言代码

            # 生成命令 - 使用选择的文件和语言
            cmd = (f"python tts_api.py -p 5000 -d cuda "
                   f"-s {self.selected_model_path} -dr {self.selected_audio_path} -dt \"{text}\" -dl {language}")

            # 创建bat文件在Voice_Model_Factory文件夹里
            app_path = get_app_path()
            voice_model_dir = os.path.join(app_path, "Voice_Model_Factory")
            bat_path = os.path.join(voice_model_dir, f"{character_name}_TTS.bat")

            # 写入bat文件内容
            with open(bat_path, "w", encoding="gbk") as bat_file:
                bat_file.write("@echo off\n")
                bat_file.write("call conda activate my-neuro\n")
                bat_file.write("cd ..\\..\\tts-studio\n")  # 多退一层目录
                bat_file.write(f"{cmd}\n")
                bat_file.write("pause\n")

            self.toast.show_message(f"生成成功：{character_name}_TTS.bat", 2000)
            self.ui.label_bat_status.setText(f"已生成：Voice_Model_Factory/{character_name}_TTS.bat")

            print(f"使用模型：{os.path.basename(self.selected_model_path)}")
            print(f"使用音频：{os.path.basename(self.selected_audio_path)}")
            print(f"使用语言：{language}")

        except Exception as e:
            self.toast.show_message(f"生成失败：{str(e)}", 3000)
            self.ui.label_bat_status.setText("生成失败")

    def setup_motion_buttons(self):
        """设置动画控制按钮 - 统一使用底层触发"""
        # 注意: "唱歌"和"停止"必须是 emotion_actions.json 中定义过的情绪名称
        # 如果您没有定义，可以改成 "开心" "生气" 等已有的情绪
        self.ui.start_singing_btn.clicked.connect(lambda: self.trigger_emotion_motion("唱歌"))
        self.ui.stop_singing_btn.clicked.connect(lambda: self.trigger_emotion_motion("停止"))

        # 加载动作配置
        self.load_motion_config()

        # 创建动态动作按钮
        self.create_dynamic_motion_buttons()

    def load_motion_config(self):
        try:
            app_path = get_app_path()
            config_path = os.path.join(app_path, 'emotion_actions.json')
            print(f"尝试加载配置文件: {config_path}")
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"JSON文件中的角色列表: {list(data.keys())}")
            # 获取当前角色名称
            current_character = self.get_current_character_name()
            print(f"当前角色: '{current_character}'")
            # 加载对应角色的配置
            if current_character in data:
                self.motion_config = data[current_character].get('emotion_actions', {})
                print(f"成功加载角色 '{current_character}' 的动作配置，共 {len(self.motion_config)} 个动作")
            else:
                print(f"错误：未找到角色 '{current_character}' 的配置")
                print(f"可用角色: {list(data.keys())}")
                self.motion_config = {}
        except Exception as e:
            print(f"加载动作配置失败: {e}")
            self.motion_config = {}

    def get_current_character_name(self):
        # 直接从main.js读取当前设置的模型优先级
        try:
            app_path = get_app_path()
            main_js_path = os.path.join(app_path, "main.js")

            with open(main_js_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取当前priorityFolders中第一个角色（这就是实际使用的角色）
            import re
            match = re.search(r"const priorityFolders = \['([^']+)'", content)
            if match:
                current_character = match.group(1)
                print(f"从main.js获取实际使用的角色: {current_character}")
                return current_character

        except Exception as e:
            print(f"读取main.js失败: {e}")
            raise Exception("无法确定当前使用的角色")

    def save_motion_config(self):
        """保存时需要更新对应角色的配置"""
        try:
            app_path = get_app_path()
            config_path = os.path.join(app_path, 'emotion_actions.json')

            # 读取完整配置
            with open(config_path, 'r', encoding='utf-8') as f:
                all_data = json.load(f)

            # 更新当前角色的配置
            current_character = self.get_current_character_name()
            if current_character not in all_data:
                all_data[current_character] = {"emotion_actions": {}}

            all_data[current_character]["emotion_actions"] = self.motion_config

            # 保存回文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"保存动作配置失败: {e}")

    def backup_original_config(self):
        """检查并加载分角色备份配置"""
        try:
            app_path = get_app_path()
            character_backup_path = os.path.join(app_path, 'character_backups.json')
            old_backup_path = os.path.join(app_path, 'emotion_actions_backup.json')

            # 兼容性处理：如果存在旧的备份文件但没有新的备份文件，进行迁移
            if os.path.exists(old_backup_path) and not os.path.exists(character_backup_path):
                self.migrate_old_backup_format(old_backup_path, character_backup_path)

            # 加载分角色备份配置
            if os.path.exists(character_backup_path):
                with open(character_backup_path, 'r', encoding='utf-8') as f:
                    self.character_backups = json.load(f)
                    print("已加载分角色备份配置")
            else:
                self.character_backups = {}
                print("未找到分角色备份文件，将在需要时创建")

        except Exception as e:
            print(f"加载备份配置失败: {e}")
            self.character_backups = {}

    def migrate_old_backup_format(self, old_backup_path, new_backup_path):
        """将旧格式的备份文件迁移到新格式"""
        try:
            import time
            with open(old_backup_path, 'r', encoding='utf-8') as f:
                old_data = json.load(f)

            new_format = {}
            current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

            for character_name, character_data in old_data.items():
                new_format[character_name] = {
                    "original_config": character_data,
                    "backup_time": current_time,
                    "migrated_from": "emotion_actions_backup.json"
                }

            with open(new_backup_path, 'w', encoding='utf-8') as f:
                json.dump(new_format, f, ensure_ascii=False, indent=2)

            print("已将旧格式备份文件迁移到新格式")

            # 重命名旧备份文件
            os.rename(old_backup_path, old_backup_path + '.old')

        except Exception as e:
            print(f"迁移旧备份文件失败: {e}")

    def create_dynamic_motion_buttons(self):
        """创建拖拽分类界面"""
        page_layout = self.ui.page_6.layout()
        if not page_layout:
            # 如果没有布局，创建一个新的垂直布局
            page_layout = QVBoxLayout(self.ui.page_6)
            self.ui.page_6.setLayout(page_layout)

        # 创建拖拽分类容器
        drag_drop_widget = QWidget()
        drag_drop_layout = QVBoxLayout(drag_drop_widget)

        # 添加控制按钮区域
        control_layout = QHBoxLayout()

        # 一键复位按钮
        reset_button = QPushButton("🔄 一键复位")
        reset_button.setObjectName("stopButton")  # 使用停止按钮的样式
        reset_button.clicked.connect(self.reset_current_character)
        control_layout.addWidget(reset_button)

        # 添加弹性空间，让标签推到右边
        control_layout.addStretch()

        # 将情绪分类标签添加到同一行
        emotion_label = QLabel("情绪分类区域（拖拽动作到这里进行分类）")
        emotion_label.setObjectName("subTitle")
        control_layout.addWidget(emotion_label)

        drag_drop_layout.addLayout(control_layout)

        # 情绪分类区域
        emotion_frame = QFrame()
        emotion_frame.setStyleSheet("QFrame { border: 2px solid #ccc; border-radius: 10px; padding: 10px; }")
        emotion_layout = QGridLayout(emotion_frame)

        # 创建情绪分类容器
        empty_emotions = ["开心", "生气", "难过", "惊讶", "害羞", "俏皮"]
        for i, emotion in enumerate(empty_emotions):
            drop_zone = self.create_drop_zone(emotion)
            emotion_layout.addWidget(drop_zone, i // 3, i % 3)

        drag_drop_layout.addWidget(emotion_frame)

        # 未分类动作区域
        action_label = QLabel("未分类动作（点击预览，拖拽到上方分类）")
        action_label.setObjectName("subTitle")
        drag_drop_layout.addWidget(action_label)

        action_frame = QFrame()
        action_frame.setStyleSheet("QFrame { border: 2px solid #ddd; border-radius: 10px; padding: 10px; }")
        # action_frame.setMinimumHeight(300)  # 添加这行，设置固定高度
        action_layout = QGridLayout(action_frame)

        # 创建分页后的动作按钮 - 只创建动作按钮，不创建分页控件
        self.unclassified_actions_cache = [key for key in self.motion_config.keys()
                                           if key not in empty_emotions and self.motion_config[key]]
        self.create_action_buttons_only(action_layout)

        drag_drop_layout.addWidget(action_frame)
        drag_drop_layout.setStretch(0,0)
        drag_drop_layout.setStretch(1, 1)
        drag_drop_layout.setStretch(2, 0)
        drag_drop_layout.setStretch(3, 2)


        # 在框外独立创建分页控件
        if len(self.unclassified_actions_cache) > self.items_per_page:
            self.create_standalone_pagination(drag_drop_layout)

        # 插入到页面布局的第1个位置
        page_layout.insertWidget(1, drag_drop_widget)


        # 为拖拽区域设置拉伸因子为1（可拉伸）
        page_layout.setStretch(0,0)
        page_layout.setStretch(1, 1)




    def create_action_buttons_only(self, action_layout):
        """只创建动作按钮，不创建分页控件"""
        # 清空旧的动作按钮
        for i in reversed(range(action_layout.count())):
            item = action_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()

        total_actions = len(self.unclassified_actions_cache)

        # 计算当前页的动作
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, total_actions)
        current_page_actions = self.unclassified_actions_cache[start_idx:end_idx]

        # 创建动作按钮
        for i, action in enumerate(current_page_actions):
            btn = self.create_draggable_button(action, self.motion_config[action])
            action_layout.addWidget(btn, i // 4, i % 4)

    def create_standalone_pagination(self, parent_layout):
        """创建独立的分页控件"""
        total_items = len(self.unclassified_actions_cache)
        total_pages = (total_items + self.items_per_page - 1) // self.items_per_page

        # 创建分页容器
        pagination_layout = QHBoxLayout()
        pagination_layout.addStretch()

        # 上一页按钮
        prev_btn = QPushButton("上一页")
        prev_btn.setObjectName("navButton")
        prev_btn.setMinimumSize(80, 40)
        prev_btn.setEnabled(self.current_page > 0)
        prev_btn.clicked.connect(self.go_to_prev_page)
        pagination_layout.addWidget(prev_btn)

        # 页码按钮
        for page in range(total_pages):
            page_btn = QPushButton(str(page + 1))
            page_btn.setObjectName("navButton")
            page_btn.setMinimumSize(40, 40)
            page_btn.setCheckable(True)
            page_btn.setChecked(page == self.current_page)
            page_btn.clicked.connect(lambda checked, p=page: self.go_to_page(p))
            pagination_layout.addWidget(page_btn)

        # 下一页按钮
        next_btn = QPushButton("下一页")
        next_btn.setObjectName("navButton")
        next_btn.setMinimumSize(80, 40)
        next_btn.setEnabled(self.current_page < total_pages - 1)
        next_btn.clicked.connect(self.go_to_next_page)
        pagination_layout.addWidget(next_btn)

        pagination_layout.addStretch()

        # 将分页布局添加到主布局
        parent_layout.addLayout(pagination_layout)

    def go_to_prev_page(self):
        """切换到上一页"""
        if self.current_page > 0:
            self.current_page -= 1
            self.refresh_drag_drop_interface()

    def go_to_next_page(self):
        """切换到下一页"""
        total_pages = (len(self.unclassified_actions_cache) + self.items_per_page - 1) // self.items_per_page
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.refresh_drag_drop_interface()

    def go_to_page(self, page):
        """切换到指定页"""
        self.current_page = page
        self.refresh_drag_drop_interface()

    def create_drop_zone(self, emotion_name):
        """创建情绪分类投放区域"""
        drop_zone = QLabel()
        # drop_zone.setMinimumSize(200, 120)  # 增加高度以显示更多内容
        drop_zone.setAlignment(Qt.AlignCenter)
        drop_zone.setWordWrap(True)  # 允许文字换行
        drop_zone.setAcceptDrops(True)
        drop_zone.emotion_name = emotion_name

        # 更新显示内容
        self.update_drop_zone_display(drop_zone, emotion_name)

        # 重写拖拽事件
        def dragEnterEvent(event):
            if event.mimeData().hasText():
                event.acceptProposedAction()

        def dropEvent(event):
            action_name = event.mimeData().text()
            self.move_action_to_emotion(action_name, emotion_name)
            event.acceptProposedAction()

        drop_zone.dragEnterEvent = dragEnterEvent
        drop_zone.dropEvent = dropEvent

        return drop_zone

    def update_drop_zone_display(self, drop_zone, emotion_name):
        """更新投放区域的显示内容"""
        if emotion_name in self.motion_config and self.motion_config[emotion_name]:
            # 如果有动作文件，显示动作数量和部分文件名
            motion_files = self.motion_config[emotion_name]
            count = len(motion_files)

            # 获取动作文件名（去掉路径和扩展名）
            action_names = []
            for file_path in motion_files:
                if isinstance(file_path, str):
                    # 提取文件名，去掉路径和.motion3.json扩展名
                    filename = file_path.split('/')[-1].replace('.motion3.json', '')
                    action_names.append(filename)

            # 显示内容：情绪名 + 动作数量 + 部分动作名
            if action_names:
                if len(action_names) <= 2:
                    display_text = f"{emotion_name}\n({count}个动作)\n{', '.join(action_names)}"
                else:
                    display_text = f"{emotion_name}\n({count}个动作)\n{', '.join(action_names[:2])}..."
            else:
                display_text = f"{emotion_name}\n({count}个动作)"

            # 改变样式表示已有内容
            drop_zone.setStyleSheet("""
                QLabel {
                    border: 2px solid #4CAF50;
                    border-radius: 8px;
                    background-color: #E8F5E8;
                    font-size: 13px;
                    color: #2E7D32;
                    padding: 5px;
                    font-weight: bold;
                }
                QLabel:hover {
                    border-color: #388E3C;
                    background-color: #C8E6C9;
                }
            """)
        else:
            # 空的情绪分类
            display_text = f"{emotion_name}\n(拖拽动作到此)"
            drop_zone.setStyleSheet("""
                QLabel {
                    border: 2px dashed #aaa;
                    border-radius: 8px;
                    background-color: #f5f5f5;
                    font-size: 14px;
                    color: #666;
                    padding: 5px;
                }
                QLabel:hover {
                    border-color: #007acc;
                    background-color: #e8f4fd;
                }
            """)
        drop_zone.setText(display_text)

    def create_draggable_button(self, action_name, motion_files):
        """创建可拖拽的动作按钮"""
        btn = QPushButton(f"{action_name}\n({len(motion_files)}个)")
        btn.setObjectName("motionButton")
        btn.setMinimumSize(150, 80)
        btn.action_name = action_name
        btn.motion_files = motion_files

        # 点击预览动作
        btn.clicked.connect(lambda: self.trigger_emotion_motion(action_name))

        # 重写鼠标事件实现拖拽
        def mousePressEvent(event):
            if event.button() == Qt.LeftButton:
                self.drag_start_position = event.pos()
            # 调用原始的mousePressEvent以保持点击功能
            QPushButton.mousePressEvent(btn, event)

        def mouseMoveEvent(event):
            if (event.buttons() == Qt.LeftButton and
                    self.drag_start_position and
                    (event.pos() - self.drag_start_position).manhattanLength() > 20):
                drag = QDrag(btn)
                mimeData = QMimeData()
                mimeData.setText(action_name)
                drag.setMimeData(mimeData)
                drag.exec_(Qt.MoveAction)
            else:
                # 调用原始的mouseMoveEvent
                QPushButton.mouseMoveEvent(btn, event)

        def mouseReleaseEvent(event):
            # 重置拖拽起始位置
            if event.button() == Qt.LeftButton:
                self.drag_start_position = None
            # 调用原始的mouseReleaseEvent以保持点击功能
            QPushButton.mouseReleaseEvent(btn, event)

        btn.mousePressEvent = mousePressEvent
        btn.mouseMoveEvent = mouseMoveEvent
        btn.mouseReleaseEvent = mouseReleaseEvent

        return btn

    def move_action_to_emotion(self, action_name, emotion_name):
        """将动作移动到指定情绪分类"""
        if action_name in self.motion_config:
            # 获取要移动的动作文件
            motion_files = self.motion_config[action_name]
            # 从原位置删除
            del self.motion_config[action_name]
            # 追加到目标情绪分类（不是覆盖）
            if emotion_name in self.motion_config:
                # 如果目标情绪已有动作，追加到现有列表
                if isinstance(self.motion_config[emotion_name], list):
                    self.motion_config[emotion_name].extend(motion_files)
                else:
                    self.motion_config[emotion_name] = motion_files
            else:
                # 如果目标情绪还没有动作，直接赋值
                self.motion_config[emotion_name] = motion_files

            self.save_motion_config()
            # 刷新界面
            self.refresh_drag_drop_interface()
            self.toast.show_message(f"已将 {action_name} 追加到 {emotion_name}", 2000)

    def reset_current_character(self):
        """复位当前选中的角色到原版配置"""
        try:
            # 获取当前角色名称
            current_character = self.get_current_character_name()
            if not current_character:
                self.toast.show_message("无法获取当前角色信息", 3000)
                return

            # 检查角色是否有备份
            if current_character not in self.character_backups:
                self.toast.show_message(f"角色 {current_character} 没有备份配置", 3000)
                return

            # 加载当前完整配置
            app_path = get_app_path()
            config_path = os.path.join(app_path, 'emotion_actions.json')

            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    all_config = json.load(f)
            else:
                self.toast.show_message("配置文件不存在", 3000)
                return

            # 只复位当前角色的配置
            original_config = self.character_backups[current_character]["original_config"]
            all_config[current_character] = original_config

            # 保存更新后的配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(all_config, f, ensure_ascii=False, indent=2)

            # 重新加载配置
            self.load_motion_config()

            # 刷新界面
            self.refresh_drag_drop_interface()

            self.toast.show_message(f"已复位当前皮套到原版配置", 2000)

        except Exception as e:
            self.toast.show_message(f"复位失败：{str(e)}", 3000)


    def refresh_drag_drop_interface(self):
        """刷新拖拽界面"""
        # 保持当前页码不变，除非超出范围
        unclassified_keys = [key for key in self.motion_config.keys()
                             if key not in ["开心", "生气", "难过", "惊讶", "害羞", "俏皮"]
                             and self.motion_config[key]]
        max_page = max(0, (len(unclassified_keys) - 1) // self.items_per_page)
        if self.current_page > max_page:
            self.current_page = max_page

        # 重新加载配置并刷新界面
        self.load_motion_config()

        # 清空并重新创建界面
        page_layout = self.ui.page_6.layout()
        # 移除旧的动态控件，确保完全清理
        items_to_remove = []
        for i in range(page_layout.count()):
            if i > 0:  # 保留第一个控件
                items_to_remove.append(i)

        # 从后往前删除，避免索引变化问题
        for i in reversed(items_to_remove):
            item = page_layout.takeAt(i)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # 递归删除布局中的所有控件
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                    elif child.layout():
                        self.delete_layout(child.layout())
                item.layout().deleteLater()

        self.create_dynamic_motion_buttons()

    def delete_layout(self, layout):
        """递归删除布局中的所有控件和子布局"""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget() is not None:
                    item.widget().deleteLater()
                elif item.layout() is not None:
                    self.delete_layout(item.layout())
            layout.deleteLater()

    def update_all_drop_zones(self):
        """更新所有投放区域的显示"""
        # 这个方法会在刷新界面时自动调用，暂时留空
        pass

    def trigger_emotion_motion(self, emotion_name):
        """
        最终版：通过HTTP请求直接调用前端底层的情绪触发逻辑。
        """
        if not (self.live2d_process and self.live2d_process.poll() is None):
            self.toast.show_message("桌宠未启动，无法触发动作", 2000)
            return

        print(f"准备通过HTTP发送情绪指令: {emotion_name}")
        try:
            # 构建一个完全符合前端 emotion-motion-mapper.js 逻辑的请求
            data = json.dumps({
                "action": "trigger_emotion",  # 告诉前端使用情绪名称触发
                "emotion_name": emotion_name  # 传递情绪名称
            }).encode('utf-8')

            # 创建请求
            req = urllib.request.Request(
                'http://localhost:3002/control-motion',  # 这是内嵌在main.js的命令接收地址
                data=data,
                headers={'Content-Type': 'application/json'}
            )

            # 发送请求并处理响应
            with urllib.request.urlopen(req, timeout=2) as response:
                result = json.loads(response.read().decode('utf-8'))
                if result.get('success'):
                    self.toast.show_message(f"已触发情绪: {emotion_name}", 1500)
                    print(f"前端成功响应: {result.get('message')}")
                else:
                    self.toast.show_message(f"指令失败: {result.get('message', '未知错误')}", 2000)

        except urllib.error.URLError as e:
            error_message = f"动作触发失败: 无法连接到桌宠的命令接收器。请确认桌宠已完全启动。"
            print(f"HTTP请求失败: {e}")
            self.toast.show_message(error_message, 3000)
        except Exception as e:
            error_message = f"动作触发失败: 发生未知错误 - {str(e)}"
            print(f"触发动作时发生未知错误: {e}")
            self.toast.show_message(error_message, 3000)

    def read_live2d_logs(self):
        """读取桌宠进程的标准输出"""
        if not self.live2d_process:
            return

        # 持续读取直到进程结束
        for line in iter(self.live2d_process.stdout.readline, ''):
            if line:
                line_stripped = line.strip()
                # 分别检查MCP和Function Call内容
                is_mcp_content = self.contains_mcp_content(line_stripped)
                is_fc_content = self.contains_function_call_content(line_stripped)

                # 检查是否是需要过滤的MCP技术日志
                is_mcp_technical_log = any(kw in line_stripped for kw in [
                    'MCP', 'mcp', 'MCPManager', 'MCP管理器',
                    '初始化MCP系统', 'MCP管理器配置', 'MCPManager创建',
                    '检查MCP状态', 'MCP系统', '开始MCP', '等待MCP系统初始化'
                ])

                # 只显示对应启用功能的日志
                should_show_in_tool_log = False
                if is_mcp_content and self.mcp_enabled:
                    should_show_in_tool_log = True
                elif is_fc_content and self.tools_enabled:
                    should_show_in_tool_log = True

                if should_show_in_tool_log:
                    # 去除时间戳前缀，只保留实际内容
                    clean_line = self.clean_log_line(line_stripped)
                    if clean_line is not None:  # 只有非None的内容才显示
                        self.mcp_log_signal.emit(clean_line)
                elif not is_mcp_technical_log:
                    # 非MCP技术日志才发送到桌宠日志
                    self.log_signal.emit(line_stripped)
            if self.live2d_process.poll() is not None:
                break

    def tail_log_file(self):
        """实时读取runtime.log文件"""
        log_file = "runtime.log"

        # 如果文件存在，先清空
        if os.path.exists(log_file):
            open(log_file, 'w').close()

        # 等待文件创建
        while not os.path.exists(log_file):
            time.sleep(0.1)
            # 如果进程已经结束，停止等待
            if self.live2d_process and self.live2d_process.poll() is not None:
                return

        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                f.seek(0, 2)  # 移到文件末尾
                while True:
                    line = f.readline()
                    if line:
                        line_stripped = line.strip()
                        # 分别检查MCP和Function Call内容
                        is_mcp_content = self.contains_mcp_content(line_stripped)
                        is_fc_content = self.contains_function_call_content(line_stripped)

                        # 检查是否是需要过滤的MCP技术日志
                        is_mcp_technical_log = any(kw in line_stripped for kw in [
                            'MCP', 'mcp', 'MCPManager', 'MCP管理器',
                            '初始化MCP系统', 'MCP管理器配置', 'MCPManager创建',
                            '检查MCP状态', 'MCP系统', '开始MCP', '等待MCP系统初始化'
                        ])

                        # 只显示对应启用功能的日志
                        should_show_in_tool_log = False
                        if is_mcp_content and self.mcp_enabled:
                            should_show_in_tool_log = True
                        elif is_fc_content and self.tools_enabled:
                            should_show_in_tool_log = True

                        if should_show_in_tool_log:
                            # 去除时间戳前缀，只保留实际内容
                            clean_line = self.clean_log_line(line_stripped)
                            if clean_line is not None:  # 只有非None的内容才显示
                                self.mcp_log_signal.emit(clean_line)
                        elif not is_mcp_technical_log:
                            # 非MCP技术日志才发送到桌宠日志
                            self.log_signal.emit(line_stripped)
                    else:
                        time.sleep(0.1)

                    # 如果进程已经结束，停止读取
                    if self.live2d_process and self.live2d_process.poll() is not None:
                        break
        except Exception as e:
            self.log_signal.emit(f"读取日志文件出错: {str(e)}")

    def update_log(self, text):
        """更新日志到UI（在主线程中执行）"""
        self.ui.textEdit_2.append(text)

    def clean_log_line(self, log_line):
        """清理日志行，去除时间戳前缀并简化特定的MCP状态信息"""
        try:
            # 匹配并去除时间戳格式：[2025-09-26T15:46:16.371Z] [INFO]
            import re
            pattern = r'^\[[\d\-T:.Z]+\]\s*\[[\w]+\]\s*'
            cleaned = re.sub(pattern, '', log_line)
            cleaned = cleaned.strip()

            # 只简化特定的MCP状态信息
            if '✅ MCPManager创建成功，启用状态: true' in cleaned:
                return None  # 不显示这个
            elif '✅ MCPManager创建成功，启用状态: false' in cleaned:
                return 'MCP启动失败'
            elif '🔍 检查MCP状态: mcpManager=true, isEnabled=true' in cleaned:
                return 'MCP启动成功'
            elif '✅ MCP系统初始化完成，耗时:' in cleaned:
                # 提取耗时信息
                match = re.search(r'耗时:\s*(\d+)ms', cleaned)
                if match:
                    time_ms = match.group(1)
                    return f'mcp服务器开启耗时：{time_ms}ms'
                return 'mcp服务器开启完成'

            return cleaned
        except Exception as e:
            print(f"清理日志行失败: {e}")
            return log_line


    def enhance_tool_log_with_description(self, log_text):
        """增强工具日志，添加工具描述"""
        try:
            enhanced_text = log_text

            # 检查日志中是否包含工具名称，并添加描述
            for tool_name, description in self.tool_descriptions.items():
                if tool_name in log_text and "→" not in log_text:
                    # 对于MCP工具调用日志，替换JSON中的工具名
                    if '{"name":"' + tool_name + '"' in log_text or '"function":{"name":"' + tool_name + '"' in log_text:
                        enhanced_text = log_text.replace(tool_name, f"{tool_name} → {description}")
                    else:
                        # 对于其他格式，添加描述到日志末尾
                        enhanced_text = f"{log_text} → {description}"
                    break

            return enhanced_text
        except Exception as e:
            print(f"增强工具日志失败: {e}")
            return log_text

    def update_tool_log(self, text):
        """更新工具日志到UI（在主线程中执行）"""
        # 增强日志文本，添加工具描述
        enhanced_text = self.enhance_tool_log_with_description(text)
        self.ui.textEdit.append(enhanced_text)

    def is_tool_related_log(self, log_line):
        """判断日志是否与工具调用相关（排除初始化日志）"""
        # 排除桌宠初始化时的MCP系统日志
        init_keywords = [
            '初始化MCP系统', 'MCP管理器配置', 'MCPManager创建',
            '检查MCP状态', 'MCP系统未启用', 'MCP系统启用失败'
        ]

        # 如果包含初始化关键词，不视为工具调用日志
        if any(keyword in log_line for keyword in init_keywords):
            return False

        # 只有实际工具调用相关的日志才路由到工具日志
        actual_tool_keywords = [
            'Function Call', 'function call',
            '工具调用', '函数调用',
            'tool_calls', 'function_name',
            'tool executed', 'tool execution',
            'handleToolCalls', 'callTool',
            '正在执行工具', '工具执行',
            'server-tools'
        ]

        return any(keyword in log_line for keyword in actual_tool_keywords)

    def contains_mcp_content(self, log_line):
        """判断日志是否包含MCP相关内容（只保留重要状态）"""
        # MCP状态信息
        mcp_status_keywords = [
            'MCP系统初始化完成，耗时',  # 启动状态和时间
            'MCP状态:',               # 服务器和工具数量
            'MCPManager创建成功，启用状态'  # 启动状态
        ]

        # 检查是否是MCP状态信息
        if any(keyword in log_line for keyword in mcp_status_keywords):
            return True

        # 检查是否是MCP工具调用（不包含Function Call工具名）
        tool_call_keywords = ['检测到工具调用', '开始执行工具调用', '工具调用结果', '发送工具结果到LLM']
        if any(keyword in log_line for keyword in tool_call_keywords):
            # 排除Function Call工具名
            fc_tool_names = list(self.fc_tools) if hasattr(self, 'fc_tools') else []
            if any(tool_name in log_line for tool_name in fc_tool_names):
                return False  # 这是Function Call工具
            return True  # 这是MCP工具

        return False

    def contains_function_call_content(self, log_line):
        """判断日志是否包含Function Call相关内容"""
        # Function Call状态信息
        fc_status_keywords = [
            'Function Call', 'function call',
            'server-tools', '工具服务器', '正在执行工具', '工具执行'
        ]

        # 检查是否是Function Call状态信息
        if any(keyword in log_line for keyword in fc_status_keywords):
            return True

        # 检查是否是Function Call工具调用（包含Function Call工具名）
        tool_call_keywords = ['检测到工具调用', '开始执行工具调用', '工具调用结果', '发送工具结果到LLM']
        if any(keyword in log_line for keyword in tool_call_keywords):
            # 检查是否包含Function Call工具名
            fc_tool_names = list(self.fc_tools) if hasattr(self, 'fc_tools') else []
            if any(tool_name in log_line for tool_name in fc_tool_names):
                return True  # 这是Function Call工具
            return False  # 这是MCP工具

        return False

    def eventFilter(self, obj, event):
        """全局事件过滤器 - 捕获所有鼠标事件"""
        if event.type() == QEvent.MouseMove:
            # --- 核心修复：始终处理拖拽和缩放，不对其节流 ---
            if self.resizing and self.resize_edge:
                self.do_resize(QCursor.pos())
                # 注意：这里不返回True，让事件可以继续传递给标题栏
                # return True 
            
            # --- 性能优化：仅对光标样式的更新进行节流 ---
            if self.can_process_mousemove and self.isVisible() and not self.isMinimized():
                self.can_process_mousemove = False  # 立即锁定
                
                # 只有在不拖拽不缩放时才更新光标
                if not self.resizing and not (event.buttons() & Qt.LeftButton):
                    local_pos = self.mapFromGlobal(QCursor.pos())
                    edge = self.get_resize_edge(local_pos)
                    if edge and self.rect().contains(local_pos):
                        self.setCursor(self.get_resize_cursor(edge))
                    else:
                        self.setCursor(Qt.ArrowCursor)

        elif event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton and self.isVisible():
                local_pos = self.mapFromGlobal(QCursor.pos())
                if self.rect().contains(local_pos):
                    # 检查是否点击在自定义标题栏上
                    if self.title_bar.geometry().contains(local_pos):
                         # 如果在标题栏上，让标题栏自己处理拖拽
                        pass
                    else:
                        self.resize_edge = self.get_resize_edge(local_pos)
                        if self.resize_edge:
                            self.resizing = True
                            self.resize_start_pos = QCursor.pos()
                            self.resize_start_geometry = self.geometry()
                            return True

        elif event.type() == QEvent.MouseButtonRelease:
            if event.button() == Qt.LeftButton and self.resizing:
                self.resizing = False
                self.resize_edge = None
                self.setCursor(Qt.ArrowCursor)
                return True

        return super().eventFilter(obj, event)

    def modify_checkbox_layout(self):
        """修改复选框布局为水平布局"""
        # 找到启动页面
        page = self.ui.page
        page_layout = page.layout()

        # 移除原来的垂直布局中的复选框
        checkbox_mcp = self.ui.checkBox_mcp
        checkbox_mcp_enable = self.ui.checkBox_mcp_enable
        checkbox_vision = self.ui.checkBox_5

        # 从原布局中移除
        page_layout.removeWidget(checkbox_mcp)
        page_layout.removeWidget(checkbox_mcp_enable)
        page_layout.removeWidget(checkbox_vision)

        # 创建新的水平布局
        checkbox_layout = QHBoxLayout()
        checkbox_layout.setSpacing(30)
        checkbox_layout.addWidget(checkbox_mcp)
        checkbox_layout.addWidget(checkbox_mcp_enable)
        checkbox_layout.addWidget(checkbox_vision)
        checkbox_layout.addStretch()  # 添加弹性空间

        # 将水平布局插入到原来的位置（在按钮布局之后）
        page_layout.insertLayout(1, checkbox_layout)

    def get_resize_edge(self, pos):
        """判断鼠标是否在边缘 - 只检测四个角"""
        rect = self.rect()
        x, y = pos.x(), pos.y()

        # 检查是否在边缘
        left = x <= self.edge_margin
        right = x >= rect.width() - self.edge_margin
        top = y <= self.edge_margin
        bottom = y >= rect.height() - self.edge_margin

        # 只返回四个角的情况
        if top and left:
            return 'top-left'
        elif top and right:
            return 'top-right'
        elif bottom and left:
            return 'bottom-left'
        elif bottom and right:
            return 'bottom-right'
        return None

    def get_resize_cursor(self, edge):
        """根据边缘返回光标样式"""
        cursor_map = {
            'top': Qt.SizeVerCursor,
            'bottom': Qt.SizeVerCursor,
            'left': Qt.SizeHorCursor,
            'right': Qt.SizeHorCursor,
            'top-left': Qt.SizeFDiagCursor,
            'top-right': Qt.SizeBDiagCursor,
            'bottom-left': Qt.SizeBDiagCursor,
            'bottom-right': Qt.SizeFDiagCursor,
        }
        return cursor_map.get(edge, Qt.ArrowCursor)

    def mousePressEvent(self, event):
        # 这些方法保留，但主要逻辑在eventFilter中
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 这些方法保留，但主要逻辑在eventFilter中
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # 这些方法保留，但主要逻辑在eventFilter中
        super().mouseReleaseEvent(event)

    def do_resize(self, global_pos):
        """执行窗口调整大小"""
        if not self.resize_start_pos or not self.resize_start_geometry:
            return

        delta = global_pos - self.resize_start_pos
        geo = QRect(self.resize_start_geometry)

        # 处理水平调整
        if 'left' in self.resize_edge:
            geo.setLeft(geo.left() + delta.x())
            geo.setWidth(geo.width() - delta.x())
        elif 'right' in self.resize_edge:
            geo.setWidth(geo.width() + delta.x())

        # 处理垂直调整
        if 'top' in self.resize_edge:
            geo.setTop(geo.top() + delta.y())
            geo.setHeight(geo.height() - delta.y())
        elif 'bottom' in self.resize_edge:
            geo.setHeight(geo.height() + delta.y())

        self.setGeometry(geo)

    def set_btu(self):
        self.ui.pushButton.clicked.connect(lambda: self.ui.stackedWidget.setCurrentIndex(1))
        self.ui.pushButton_3.clicked.connect(lambda: self.ui.stackedWidget.setCurrentIndex(0))
        self.ui.pushButton_2.clicked.connect(lambda: self.ui.stackedWidget.setCurrentIndex(5))  # 直播改成5
        self.ui.pushButton_5.clicked.connect(lambda: self.ui.stackedWidget.setCurrentIndex(2))
        self.ui.pushButton_6.clicked.connect(lambda: self.ui.stackedWidget.setCurrentIndex(3))
        self.ui.pushButton_animation.clicked.connect(lambda: self.ui.stackedWidget.setCurrentIndex(4))  # 动画改成4
        self.ui.pushButton_terminal.clicked.connect(lambda: self.ui.stackedWidget.setCurrentIndex(7))
        self.ui.pushButton_game.clicked.connect(lambda: self.ui.stackedWidget.setCurrentIndex(9))
        self.ui.pushButton_voice_clone.clicked.connect(lambda: self.ui.stackedWidget.setCurrentIndex(6))  # 声音克隆页面
        self.ui.pushButton_ui_settings.clicked.connect(lambda: self.ui.stackedWidget.setCurrentIndex(11))  # UI设置页面
        self.ui.pushButton_tools.clicked.connect(lambda: self.ui.stackedWidget.setCurrentIndex(10))  # 工具屋页面
        self.ui.pushButton_cloud_config.clicked.connect(lambda: self.ui.stackedWidget.setCurrentIndex(12))  # 云端配置页面
        self.ui.saveConfigButton.clicked.connect(self.save_config)
        self.ui.pushButton_8.clicked.connect(self.start_live_2d)
        self.ui.pushButton_7.clicked.connect(self.close_live_2d)
        self.ui.pushButton_clearLog.clicked.connect(self.clear_logs)
        self.ui.pushButton_start_terminal.clicked.connect(self.start_terminal)
        self.ui.pushButton_stop_terminal.clicked.connect(self.stop_terminal)  # 新增
        # 新增按钮绑定
        self.ui.pushButton_start_asr.clicked.connect(self.start_asr)
        self.ui.pushButton_stop_asr.clicked.connect(self.stop_asr)
        self.ui.pushButton_start_bert.clicked.connect(self.start_bert)
        self.ui.pushButton_stop_bert.clicked.connect(self.stop_bert)
        self.ui.pushButton_start_rag.clicked.connect(self.start_rag)
        self.ui.pushButton_stop_rag.clicked.connect(self.stop_rag)

        # 添加声音克隆按钮绑定
        self.ui.pushButton_generate_bat.clicked.connect(self.generate_voice_clone_bat)
        self.ui.pushButton_select_model.clicked.connect(self.select_model_file)
        self.ui.pushButton_select_audio.clicked.connect(self.select_audio_file)
        self.ui.pushButton_tutorial.clicked.connect(self.show_tutorial)
        
        # 添加Minecraft游戏终端按钮绑定
        self.ui.pushButton_start_minecraft_terminal.clicked.connect(self.start_minecraft_terminal)

        self.ui.pushButton_tutorial.clicked.connect(self.show_tutorial)
        self.ui.pushButton_back_to_home.clicked.connect(lambda: self.ui.stackedWidget.setCurrentIndex(0))

        # 工具屋相关按钮绑定
        self.ui.listWidget_tools.itemClicked.connect(self.toggle_tool_status)
        self.ui.listWidget_mcp_tools.itemClicked.connect(self.toggle_mcp_tool_status)

        # 云端配置两个标签页的通用配置实时同步
        self.ui.lineEdit_cloud_provider.textChanged.connect(
            lambda text: self.ui.lineEdit_cloud_provider_2.setText(text)
        )
        self.ui.lineEdit_cloud_provider_2.textChanged.connect(
            lambda text: self.ui.lineEdit_cloud_provider.setText(text) if self.ui.lineEdit_cloud_provider.text() != text else None
        )
        self.ui.lineEdit_cloud_api_key.textChanged.connect(
            lambda text: self.ui.lineEdit_cloud_api_key_2.setText(text)
        )
        self.ui.lineEdit_cloud_api_key_2.textChanged.connect(
            lambda text: self.ui.lineEdit_cloud_api_key.setText(text) if self.ui.lineEdit_cloud_api_key.text() != text else None
        )

        # 加载Minecraft配置到UI
        self.load_minecraft_config()

    def scan_voice_models(self):
        """扫描当前目录下的pth模型文件"""
        try:
            import glob
            current_dir = os.path.dirname(os.path.abspath(__file__))
            pth_files = glob.glob(os.path.join(current_dir, "*.pth"))

            self.ui.comboBox_models.clear()
            if pth_files:
                for pth_file in pth_files:
                    model_name = os.path.basename(pth_file)
                    self.ui.comboBox_models.addItem(model_name, pth_file)
                self.toast.show_message(f"找到 {len(pth_files)} 个模型文件", 2000)
            else:
                self.toast.show_message("未找到pth模型文件，请将模型文件放在程序目录下", 3000)

        except Exception as e:
            self.toast.show_message(f"扫描模型文件失败：{str(e)}", 3000)

    def scan_reference_audio(self):
        """扫描当前目录下的wav音频文件"""
        try:
            import glob
            current_dir = os.path.dirname(os.path.abspath(__file__))
            wav_files = glob.glob(os.path.join(current_dir, "*.wav"))

            self.ui.comboBox_audio.clear()
            if wav_files:
                for wav_file in wav_files:
                    audio_name = os.path.basename(wav_file)
                    self.ui.comboBox_audio.addItem(audio_name, wav_file)
                self.toast.show_message(f"找到 {len(wav_files)} 个音频文件", 2000)
            else:
                self.toast.show_message("未找到wav音频文件，请将音频文件放在程序目录下", 3000)

        except Exception as e:
            self.toast.show_message(f"扫描音频文件失败：{str(e)}", 3000)

    def start_voice_tts(self):
        """启动声音克隆TTS服务"""
        try:
            # 检查是否已生成bat文件
            character_name = self.ui.lineEdit_character_name.text().strip()
            if not character_name:
                self.toast.show_message("请先生成bat文件", 2000)
                return

            current_dir = os.path.dirname(os.path.abspath(__file__))
            bat_path = os.path.join(current_dir, f"{character_name}_TTS.bat")

            if not os.path.exists(bat_path):
                self.toast.show_message("bat文件不存在，请先生成", 2000)
                return

            if self.voice_clone_process and self.voice_clone_process.poll() is None:
                self.toast.show_message("声音克隆服务已在运行中", 2000)
                return

            # 启动bat文件
            self.voice_clone_process = subprocess.Popen(
                bat_path,
                shell=True,
                cwd=current_dir,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )

            self.ui.label_voice_tts_status.setText("状态：声音克隆服务正在运行")
            self.toast.show_message("声音克隆服务启动成功", 2000)

        except Exception as e:
            error_msg = f"启动声音克隆服务失败：{str(e)}"
            self.toast.show_message(error_msg, 3000)
            self.ui.label_voice_tts_status.setText("状态：启动失败")

    def stop_voice_tts(self):
        """关闭声音克隆TTS服务"""
        try:
            # 通过进程名强制关闭TTS相关进程
            subprocess.run('wmic process where "name=\'python.exe\' and commandline like \'%tts_api%\'" delete',
                           shell=True, capture_output=True)

            # 清空进程引用
            self.voice_clone_process = None

            # 更新状态显示
            self.ui.label_voice_tts_status.setText("状态：声音克隆服务未启动")
            self.toast.show_message("声音克隆服务已关闭", 2000)

        except Exception as e:
            error_msg = f"关闭声音克隆服务失败：{str(e)}"
            self.toast.show_message(error_msg, 3000)

    def start_asr(self):
        """启动ASR服务"""
        try:
            if self.asr_process and self.asr_process.poll() is None:
                print("ASR服务已在运行中，无需重复启动")
                self.toast.show_message("ASR服务已在运行中", 2000)
                self.ui.label_asr_status.setText("状态：ASR服务正在运行")
                self.update_status_indicator('asr', True)
                return

            print("正在启动ASR终端.....")
            self.update_service_log('asr', "正在启动ASR服务.....")

            # 根据config中的云端ASR配置选择对应的bat文件
            is_cloud_asr = self.config.get('cloud', {}).get('asr', {}).get('enabled', False)
            base_path = get_base_path()

            if is_cloud_asr:  # 云端ASR
                bat_file = os.path.join(base_path, "VAD.bat")
                asr_type_name = "云端ASR（仅VAD）"
            else:  # 本地ASR
                bat_file = os.path.join(base_path, "ASR.bat")
                asr_type_name = "本地ASR"

            print(f"选择的ASR类型：{asr_type_name}")
            self.update_service_log('asr', f"选择的ASR类型：{asr_type_name}")

            if not os.path.exists(bat_file):
                error_msg = f"找不到文件：{bat_file}"
                print(f"错误：{error_msg}")
                self.update_service_log('asr', f"错误：{error_msg}")
                self.toast.show_message(error_msg, 3000)
                return

            # 确保日志目录存在
            log_file = self.log_file_paths['asr']
            log_dir = os.path.dirname(log_file)
            os.makedirs(log_dir, exist_ok=True)
            # 不再清空日志文件，保留历史记录

            # 启动日志读取线程
            if 'asr' in self.log_readers:
                self.log_readers['asr'].stop()
                self.log_readers['asr'].wait()

            self.log_readers['asr'] = LogReader(log_file)
            self.log_readers['asr'].log_signal.connect(lambda text: self.update_service_log('asr', text))
            self.log_readers['asr'].start()

            self.asr_process = subprocess.Popen(
                bat_file,
                shell=True,
                cwd=base_path,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )

            print(f"ASR进程已启动，PID: {self.asr_process.pid}")
            print("当前ASR终端已成功启动！！！")

            self.update_service_log('asr', f"ASR进程已启动，PID: {self.asr_process.pid}")
            self.update_service_log('asr', "当前ASR终端已成功启动！！！")

            self.ui.label_asr_status.setText(f"状态：{asr_type_name}服务正在运行")
            self.update_status_indicator('asr', True)
            self.toast.show_message(f"{asr_type_name}服务启动成功", 2000)

        except Exception as e:
            error_msg = f"启动ASR服务失败：{str(e)}"
            print(f"错误：{error_msg}")
            self.update_service_log('asr', f"错误：{error_msg}")
            self.ui.label_asr_status.setText("状态：启动失败")
            self.toast.show_message(error_msg, 3000)

    def stop_asr(self):
        """关闭ASR服务"""
        try:
            # 在ASR日志窗口显示关闭信息
            self.update_service_log('asr', "正在关闭ASR服务...")

            # 停止日志读取线程
            if 'asr' in self.log_readers:
                self.log_readers['asr'].stop()
                self.log_readers['asr'].wait()
                del self.log_readers['asr']

            # 同时关闭本地ASR和云端VAD进程
            subprocess.run('wmic process where "name=\'python.exe\' and (commandline like \'%ASR%\' or commandline like \'%VAD%\')" delete',
                           shell=True, capture_output=True)

            self.asr_process = None
            self.ui.label_asr_status.setText("状态：ASR服务未启动")
            self.update_status_indicator('asr', False)

            # 在日志窗口显示关闭完成信息
            self.update_service_log('asr', "当前ASR终端已关闭！！！")
            print("当前ASR终端已关闭！！！")  # 同时在控制台也打印

            self.toast.show_message("ASR服务已关闭", 2000)

        except Exception as e:
            error_msg = f"关闭ASR服务失败：{str(e)}"
            self.update_service_log('asr', f"错误：{error_msg}")
            print(f"错误：{error_msg}")
            self.toast.show_message(error_msg, 3000)

    def start_bert(self):
        """启动BERT服务"""
        try:
            if self.bert_process and self.bert_process.poll() is None:
                print("BERT服务已在运行中，无需重复启动")
                self.toast.show_message("BERT服务已在运行中", 2000)
                self.ui.label_bert_status.setText("状态：BERT服务正在运行")
                self.update_status_indicator('bert', True)
                return

            print("正在启动BERT终端.....")
            self.update_service_log('bert', "正在启动BERT服务.....")

            base_path = get_base_path()
            bat_file = os.path.join(base_path, "bert.bat")

            if not os.path.exists(bat_file):
                error_msg = f"找不到文件：{bat_file}"
                print(f"错误：{error_msg}")
                self.update_service_log('bert', f"错误：{error_msg}")
                self.toast.show_message(error_msg, 3000)
                return

            # 确保日志目录存在
            log_file = self.log_file_paths['bert']
            log_dir = os.path.dirname(log_file)
            os.makedirs(log_dir, exist_ok=True)
            # 不再清空日志文件，保留历史记录

            # 启动日志读取线程
            if 'bert' in self.log_readers:
                self.log_readers['bert'].stop()
                self.log_readers['bert'].wait()

            self.log_readers['bert'] = LogReader(log_file)
            self.log_readers['bert'].log_signal.connect(lambda text: self.update_service_log('bert', text))
            self.log_readers['bert'].start()

            self.bert_process = subprocess.Popen(
                bat_file,
                shell=True,
                cwd=base_path,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )

            print(f"BERT进程已启动，PID: {self.bert_process.pid}")
            print("当前BERT终端已成功启动！！！")

            self.update_service_log('bert', f"BERT进程已启动，PID: {self.bert_process.pid}")
            self.update_service_log('bert', "当前BERT终端已成功启动！！！")

            self.ui.label_bert_status.setText("状态：BERT服务正在运行")
            self.update_status_indicator('bert', True)
            self.toast.show_message("BERT服务启动成功", 2000)

        except Exception as e:
            error_msg = f"启动BERT服务失败：{str(e)}"
            print(f"错误：{error_msg}")
            self.update_service_log('bert', f"错误：{error_msg}")
            self.ui.label_bert_status.setText("状态：启动失败")
            self.toast.show_message(error_msg, 3000)

    def stop_bert(self):
        """关闭BERT服务"""
        try:
            print("正在关闭BERT终端...")
            self.update_service_log('bert', "正在关闭BERT服务...")

            # 停止日志读取线程
            if 'bert' in self.log_readers:
                self.log_readers['bert'].stop()
                self.log_readers['bert'].wait()
                del self.log_readers['bert']

            # 强制关闭BERT相关进程
            subprocess.run('wmic process where "name=\'python.exe\' and commandline like \'%bert%\'" delete',
                           shell=True, capture_output=True)

            self.bert_process = None
            self.ui.label_bert_status.setText("状态：BERT服务未启动")
            self.update_status_indicator('bert', False)

            print("当前BERT终端已关闭！！！")
            self.update_service_log('bert', "当前BERT终端已关闭！！！")
            self.toast.show_message("BERT服务已关闭", 2000)

        except Exception as e:
            error_msg = f"关闭BERT服务失败：{str(e)}"
            print(f"错误：{error_msg}")
            self.update_service_log('bert', f"错误：{error_msg}")
            self.toast.show_message(error_msg, 3000)

    def start_rag(self):
        """启动RAG服务"""
        try:
            if self.rag_process and self.rag_process.poll() is None:
                print("RAG服务已在运行中，无需重复启动")
                self.toast.show_message("RAG服务已在运行中", 2000)
                self.ui.label_rag_status.setText("状态：RAG服务正在运行")
                self.update_status_indicator('rag', True)
                return

            print("正在启动RAG终端.....")
            self.update_service_log('rag', "正在启动RAG服务.....")

            base_path = get_base_path()
            bat_file = os.path.join(base_path, "RAG.bat")

            if not os.path.exists(bat_file):
                error_msg = f"找不到文件：{bat_file}"
                print(f"错误：{error_msg}")
                self.update_service_log('rag', f"错误：{error_msg}")
                self.toast.show_message(error_msg, 3000)
                return

            # 确保日志目录存在
            log_file = self.log_file_paths['rag']
            log_dir = os.path.dirname(log_file)
            os.makedirs(log_dir, exist_ok=True)
            # 不再清空日志文件，保留历史记录

            # 启动日志读取线程
            if 'rag' in self.log_readers:
                self.log_readers['rag'].stop()
                self.log_readers['rag'].wait()

            self.log_readers['rag'] = LogReader(log_file)
            self.log_readers['rag'].log_signal.connect(lambda text: self.update_service_log('rag', text))
            self.log_readers['rag'].start()

            self.rag_process = subprocess.Popen(
                bat_file,
                shell=True,
                cwd=base_path,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )

            print(f"RAG进程已启动，PID: {self.rag_process.pid}")
            print("当前RAG终端已成功启动！！！")

            self.update_service_log('rag', f"RAG进程已启动，PID: {self.rag_process.pid}")
            self.update_service_log('rag', "当前RAG终端已成功启动！！！")

            self.ui.label_rag_status.setText("状态：RAG服务正在运行")
            self.update_status_indicator('rag', True)
            self.toast.show_message("RAG服务启动成功", 2000)

        except Exception as e:
            error_msg = f"启动RAG服务失败：{str(e)}"
            print(f"错误：{error_msg}")
            self.update_service_log('rag', f"错误：{error_msg}")
            self.ui.label_rag_status.setText("状态：启动失败")
            self.toast.show_message(error_msg, 3000)

    def stop_rag(self):
        """关闭RAG服务"""
        try:
            print("正在关闭RAG终端...")
            self.update_service_log('rag', "正在关闭RAG服务...")

            # 停止日志读取线程
            if 'rag' in self.log_readers:
                self.log_readers['rag'].stop()
                self.log_readers['rag'].wait()
                del self.log_readers['rag']

            # 强制关闭RAG相关进程
            subprocess.run('wmic process where "name=\'python.exe\' and commandline like \'%RAG%\'" delete',
                           shell=True, capture_output=True)

            self.rag_process = None
            self.ui.label_rag_status.setText("状态：RAG服务未启动")
            self.update_status_indicator('rag', False)

            print("当前RAG终端已关闭！！！")
            self.update_service_log('rag', "当前RAG终端已关闭！！！")
            self.toast.show_message("RAG服务已关闭", 2000)

        except Exception as e:
            error_msg = f"关闭RAG服务失败：{str(e)}"
            print(f"错误：{error_msg}")
            self.update_service_log('rag', f"错误：{error_msg}")
            self.toast.show_message(error_msg, 3000)

    # 新增关闭后台服务的方法
    def stop_terminal(self):
        """关闭TTS服务"""
        try:
            print("正在关闭TTS终端...")
            self.update_service_log('tts', "正在关闭TTS服务...")

            # 停止日志读取线程
            if 'tts' in self.log_readers:
                self.log_readers['tts'].stop()
                self.log_readers['tts'].wait()
                del self.log_readers['tts']

            # 通过进程名强制关闭TTS相关进程
            subprocess.run('wmic process where "name=\'python.exe\' and commandline like \'%TTS%\'" delete',
                           shell=True, capture_output=True)

            # 清空进程引用
            self.terminal_process = None

            # 更新状态显示
            self.ui.label_terminal_status.setText("状态：TTS服务未启动")
            self.update_status_indicator('tts', False)

            print("当前TTS终端已关闭！！！")
            self.update_service_log('tts', "当前TTS终端已关闭！！！")
            self.toast.show_message("TTS服务已关闭", 2000)

        except Exception as e:
            error_msg = f"关闭TTS服务失败：{str(e)}"
            print(f"错误：{error_msg}")
            self.update_service_log('tts', f"错误：{error_msg}")
            self.toast.show_message(error_msg, 3000)

            # 即使出错也更新状态
            self.terminal_process = None
            self.ui.label_terminal_status.setText("状态：TTS服务未启动")

    def start_terminal(self):
        """启动TTS服务"""
        try:
            if self.terminal_process and self.terminal_process.poll() is None:
                print("TTS服务已在运行中，无需重复启动")
                self.toast.show_message("TTS服务已在运行中", 2000)
                self.ui.label_terminal_status.setText("状态：TTS服务正在运行")
                self.update_status_indicator('tts', True)
                return

            print("正在启动TTS终端.....")
            self.update_service_log('tts', "正在启动TTS服务.....")

            base_path = get_base_path()
            bat_file = os.path.join(base_path, "TTS.bat")

            if not os.path.exists(bat_file):
                error_msg = f"找不到文件：{bat_file}"
                print(f"错误：{error_msg}")
                self.update_service_log('tts', f"错误：{error_msg}")
                self.toast.show_message(error_msg, 3000)
                return

            # 确保日志目录存在
            log_file = self.log_file_paths['tts']
            log_dir = os.path.dirname(log_file)
            os.makedirs(log_dir, exist_ok=True)
            # 不再清空日志文件，保留历史记录

            # 启动日志读取线程
            if 'tts' in self.log_readers:
                self.log_readers['tts'].stop()
                self.log_readers['tts'].wait()

            self.log_readers['tts'] = LogReader(log_file)
            self.log_readers['tts'].log_signal.connect(lambda text: self.update_service_log('tts', text))
            self.log_readers['tts'].start()

            print(f"启动TTS.bat文件: {bat_file}")

            self.terminal_process = subprocess.Popen(
                bat_file,
                shell=True,
                cwd=base_path,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                # stdout=subprocess.PIPE,
                # stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )

            print(f"TTS进程已启动，PID: {self.terminal_process.pid}")
            print("当前TTS终端已成功启动！！！")

            self.update_service_log('tts', f"TTS进程已启动，PID: {self.terminal_process.pid}")
            self.update_service_log('tts', "当前TTS终端已成功启动！！！")

            self.ui.label_terminal_status.setText("状态：TTS服务正在运行")
            self.update_status_indicator('tts', True)
            self.toast.show_message("TTS服务启动成功", 2000)

        except Exception as e:
            error_msg = f"启动TTS服务失败：{str(e)}"
            print(f"错误：{error_msg}")
            self.update_service_log('tts', f"错误：{error_msg}")
            self.ui.label_terminal_status.setText("状态：启动失败")
            self.toast.show_message(error_msg, 3000)

    def clear_logs(self):
        """清空日志功能"""
        # 清空桌宠日志
        self.ui.textEdit_2.clear()
        # 清空工具日志
        self.ui.textEdit.clear()
        # 显示提示
        self.toast.show_message("日志已清空", 1500)



    def set_config(self):
        self.ui.lineEdit.setText(self.config['llm']['api_key'])
        self.ui.lineEdit_2.setText(self.config['llm']['api_url'])
        self.ui.lineEdit_3.setText(self.config['llm']['model'])
        self.ui.textEdit_3.setPlainText(self.config['llm']['system_prompt'])
        self.ui.lineEdit_4.setText(self.config['ui']['intro_text'])
        self.ui.lineEdit_5.setText(str(self.config['context']['max_messages']))
        self.ui.lineEdit_idle_time.setText(str(self.config['auto_chat']['idle_time']))
        self.ui.textEdit_prompt.setPlainText(self.config['auto_chat']['prompt'])
        self.ui.lineEdit_6.setText(str(self.config['bilibili']['roomId']))
        self.ui.checkBox_mcp.setChecked(self.config.get('tools', {}).get('enabled', True))
        self.ui.checkBox_mcp_enable.setChecked(self.config.get('mcp', {}).get('enabled', True))
        self.ui.checkBox_5.setChecked(self.config['vision']['auto_screenshot'])
        self.ui.checkBox_4.setChecked(self.config['context']['enable_limit'])
        self.ui.checkBox.setChecked(self.config['auto_chat']['enabled'])
        self.ui.checkBox_2.setChecked(self.config['bilibili']['enabled'])
        # 新增ASR和TTS配置
        self.ui.checkBox_asr.setChecked(self.config['asr']['enabled'])
        self.ui.checkBox_tts.setChecked(self.config['tts']['enabled'])
        self.ui.checkBox_persistent_history.setChecked(self.config['context']['persistent_history'])
        self.ui.checkBox_voice_barge_in.setChecked(self.config['asr']['voice_barge_in'])
        self.ui.checkBox_game_minecraft.setChecked(self.config['game']['Minecraft']['enabled'])

# 新增：设置TTS语言下拉框 (已修复BUG)
        # 1. 从已加载的配置中读取保存的语言代码，如果不存在则默认为'zh'
        saved_language = self.config.get('tts', {}).get('language', 'zh')
        
        # 2. 遍历下拉框中的所有选项
        for i in range(self.ui.comboBox_tts_language.count()):
            # 获取每个选项的文本，例如 "ja - 日语"
            item_text = self.ui.comboBox_tts_language.itemText(i)
            # 提取语言代码，例如 "ja"
            item_language_code = item_text.split(' - ')[0]
            
            # 3. 如果选项的语言代码与保存的配置匹配
            if item_language_code == saved_language:
                # 4. 设置下拉框的当前选项为这一项，并停止查找
                self.ui.comboBox_tts_language.setCurrentIndex(i)
                break

        # 新增：设置翻译配置
        self.ui.checkBox_translation_enabled.setChecked(self.config['translation']['enabled'])
        self.ui.lineEdit_translation_api_key.setText(self.config['translation']['api_key'])
        self.ui.lineEdit_translation_api_url.setText(self.config['translation']['api_url'])
        self.ui.lineEdit_translation_model.setText(self.config['translation']['model'])
        self.ui.textEdit_translation_prompt.setPlainText(self.config['translation']['system_prompt'])

        # 新增：设置UI设置配置
        subtitle_labels = self.config.get('subtitle_labels', {})
        self.ui.checkBox_subtitle_enabled.setChecked(subtitle_labels.get('enabled', True))
        self.ui.lineEdit_user_name.setText(subtitle_labels.get('user', '用户'))
        self.ui.lineEdit_ai_name.setText(subtitle_labels.get('ai', 'Fake Neuro'))

        # 新增：设置自动关闭服务配置
        auto_close_services = self.config.get('auto_close_services', {})
        self.ui.checkBox_auto_close_services.setChecked(auto_close_services.get('enabled', True))

        # 新增：设置云端配置
        cloud_config = self.config.get('cloud', {})
        # 通用云端配置（两个标签页都设置）
        provider = cloud_config.get('provider', 'siliconflow')
        api_key = cloud_config.get('api_key', '')
        self.ui.lineEdit_cloud_provider.setText(provider)
        self.ui.lineEdit_cloud_api_key.setText(api_key)
        self.ui.lineEdit_cloud_provider_2.setText(provider)
        self.ui.lineEdit_cloud_api_key_2.setText(api_key)

        # 云端TTS配置
        cloud_tts = cloud_config.get('tts', {})
        self.ui.checkBox_cloud_tts_enabled.setChecked(cloud_tts.get('enabled', False))
        self.ui.lineEdit_cloud_tts_url.setText(cloud_tts.get('url', 'https://api.siliconflow.cn/v1/audio/speech'))
        self.ui.lineEdit_cloud_tts_model.setText(cloud_tts.get('model', 'FunAudioLLM/CosyVoice2-0.5B'))
        self.ui.lineEdit_cloud_tts_voice.setText(cloud_tts.get('voice', ''))
        # 设置音频格式下拉框
        tts_format = cloud_tts.get('response_format', 'mp3')
        format_index = self.ui.comboBox_cloud_tts_format.findText(tts_format)
        if format_index >= 0:
            self.ui.comboBox_cloud_tts_format.setCurrentIndex(format_index)
        self.ui.doubleSpinBox_cloud_tts_speed.setValue(cloud_tts.get('speed', 1.0))

        # 云端ASR配置
        cloud_asr = cloud_config.get('asr', {})
        self.ui.checkBox_cloud_asr_enabled.setChecked(cloud_asr.get('enabled', False))
        self.ui.lineEdit_cloud_asr_url.setText(cloud_asr.get('url', 'https://api.siliconflow.cn/v1/audio/transcriptions'))
        self.ui.lineEdit_cloud_asr_model.setText(cloud_asr.get('model', 'FunAudioLLM/SenseVoiceSmall'))

    def start_live_2d(self):
        # 检查是否已经有桌宠在运行
        if self.live2d_process and self.live2d_process.poll() is None:
            self.toast.show_message("桌宠已在运行中，请勿重复启动", 2000)
            return

        # 清空之前的日志
        self.ui.textEdit_2.clear()  # 清空桌宠日志
        self.ui.textEdit.clear()    # 清空工具日志

        # 启动桌宠进程 - 使用bat文件
        self.live2d_process = subprocess.Popen(
            "go.bat",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='ignore',
            bufsize=1,
            universal_newlines=True
        )

        # 检查复选框状态（必须在启动日志线程之前设置）
        self.mcp_enabled = self.ui.checkBox_mcp_enable.isChecked()  # MCP功能
        self.tools_enabled = self.ui.checkBox_mcp.isChecked()       # 工具调用功能

        # 重新加载工具描述，确保显示最新的工具列表
        self.tool_descriptions, self.fc_tools, self.mcp_tools = load_tool_descriptions()

        # 检查工具状态
        self.check_tools_status()

        # 启动线程读取进程输出
        from threading import Thread
        Thread(target=self.read_live2d_logs, daemon=True).start()

        # 启动线程读取runtime.log文件
        Thread(target=self.tail_log_file, daemon=True).start()

        self.toast.show_message("桌宠启动中...", 1500)

    def check_tools_status(self):
        """检查工具状态和模块"""
        try:
            # 只有任何一个工具功能启用时才显示详细信息
            if not self.tools_enabled and not self.mcp_enabled:
                return

            tools_path = ".\\server-tools"

            # 检查工具目录是否存在
            if not os.path.exists(tools_path):
                self.mcp_log_signal.emit("❌ server-tools目录不存在")
                return

            # 扫描工具模块
            js_files = [f for f in os.listdir(tools_path) if f.endswith('.js') and f != 'server.js']

            # 显示Function Call工具状态
            if self.tools_enabled:
                self.mcp_log_signal.emit("🔧 工具调用功能: 已启用")

            # 分别统计和显示Function Call和MCP工具
            if hasattr(self, 'tool_descriptions') and self.tool_descriptions:
                # 只有启用对应功能时才显示
                if self.tools_enabled and hasattr(self, 'fc_tools') and self.fc_tools:
                    self.mcp_log_signal.emit("🧪 Function Call工具:")
                    for tool_name in self.fc_tools:
                        if tool_name in self.tool_descriptions:
                            description = self.tool_descriptions[tool_name]
                            self.mcp_log_signal.emit(f"【{tool_name}】→ {description}")
                        else:
                            self.mcp_log_signal.emit(f"【{tool_name}】")

                if self.mcp_enabled and hasattr(self, 'mcp_tools') and self.mcp_tools:
                    self.mcp_log_signal.emit("🧪 MCP工具:")
                    for tool_name in self.mcp_tools:
                        if tool_name in self.tool_descriptions:
                            description = self.tool_descriptions[tool_name]
                            self.mcp_log_signal.emit(f"【{tool_name}】→ {description}")
                        else:
                            self.mcp_log_signal.emit(f"【{tool_name}】")

        except Exception as e:
            # 错误信息仍然显示，以便调试
            self.mcp_log_signal.emit(f"❌ 检查工具状态失败: {e}")


    def close_live_2d(self):
        """关闭桌宠进程"""
        try:
            # 直接杀死所有 node.exe 进程
            result = subprocess.run(
                'taskkill /f /im node.exe',
                shell=True, capture_output=True, text=True
            )

            if result.returncode == 0:
                self.mcp_log_signal.emit("✅ 所有 Node.js 进程已强制关闭")
            else:
                self.mcp_log_signal.emit("⚠️ 未找到 Node.js 进程或已关闭")

            # 清理进程引用
            if self.live2d_process:
                self.live2d_process = None

        except Exception as e:
            self.mcp_log_signal.emit(f"❌ 关闭进程失败: {e}")

    def load_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_minecraft_config(self):
        """加载Minecraft配置文件"""
        try:
            app_path = get_app_path()
            andy_config_path = os.path.join(app_path, 'GAME', 'Minecraft', 'andy.json')
            keys_config_path = os.path.join(app_path, 'GAME', 'Minecraft', 'keys.json')

            # 加载andy.json配置
            if os.path.exists(andy_config_path):
                with open(andy_config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # 将配置加载到UI控件中
                self.ui.lineEdit_minecraft_name.setText(config.get('name', ''))
                self.ui.lineEdit_minecraft_model_name.setText(config.get('model', {}).get('model', ''))
                self.ui.lineEdit_minecraft_model_url.setText(config.get('model', {}).get('url', ''))
                self.ui.textEdit_minecraft_conversing.setPlainText(config.get('conversing', ''))

            # 加载keys.json中的API KEY
            if os.path.exists(keys_config_path):
                with open(keys_config_path, 'r', encoding='utf-8') as f:
                    keys_config = json.load(f)
                    self.ui.lineEdit_minecraft_api_key.setText(keys_config.get('OPENAI_API_KEY', ''))

        except Exception as e:
            print(f"加载Minecraft配置失败: {e}")

    def save_minecraft_config(self):
        """保存Minecraft配置文件"""
        try:
            app_path = get_app_path()
            andy_config_path = os.path.join(app_path, 'GAME', 'Minecraft', 'andy.json')
            keys_config_path = os.path.join(app_path, 'GAME', 'Minecraft', 'keys.json')

            # 创建目录（如果不存在）
            os.makedirs(os.path.dirname(andy_config_path), exist_ok=True)

            # 先读取现有配置，保留嵌入模型配置
            existing_config = {}
            if os.path.exists(andy_config_path):
                with open(andy_config_path, 'r', encoding='utf-8') as f:
                    existing_config = json.load(f)

            # 构建配置数据，保留原有的embedding配置
            config = {
                "name": self.ui.lineEdit_minecraft_name.text(),
                "model": {
                    "api": existing_config.get('model', {}).get('api', 'openai'),  # 保持默认值
                    "model": self.ui.lineEdit_minecraft_model_name.text(),
                    "url": self.ui.lineEdit_minecraft_model_url.text()
                },
                "embedding": existing_config.get('embedding', {
                    "api": "openai",
                    "model": "text-embedding-ada-002",
                    "url": "https://api.zhizengzeng.com/v1"
                }),  # 保留原有embedding配置
                "conversing": self.ui.textEdit_minecraft_conversing.toPlainText()
            }

            # 保存andy.json
            with open(andy_config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)

            # 保存API KEY到keys.json
            existing_keys = {}
            if os.path.exists(keys_config_path):
                with open(keys_config_path, 'r', encoding='utf-8') as f:
                    existing_keys = json.load(f)

            # 更新API KEY
            existing_keys['OPENAI_API_KEY'] = self.ui.lineEdit_minecraft_api_key.text()

            # 保存keys.json
            with open(keys_config_path, 'w', encoding='utf-8') as f:
                json.dump(existing_keys, f, ensure_ascii=False, indent=4)

            print("Minecraft配置已保存")

        except Exception as e:
            print(f"保存Minecraft配置失败: {e}")

    def save_config(self):
        current_config = self.load_config()

        current_config['llm'] = {
            "api_key": self.ui.lineEdit.text(),
            "api_url": self.ui.lineEdit_2.text(),
            "model": self.ui.lineEdit_3.text(),
            "system_prompt": self.ui.textEdit_3.toPlainText()
        }

        current_config["ui"]["intro_text"] = self.ui.lineEdit_4.text()
        current_config['context']['max_messages'] = int(self.ui.lineEdit_5.text())
        current_config['auto_chat']['idle_time'] = int(self.ui.lineEdit_idle_time.text())
        current_config['auto_chat']['prompt'] = self.ui.textEdit_prompt.toPlainText()

        # 处理房间号
        room_id_text = self.ui.lineEdit_6.text()
        if room_id_text == "你的哔哩哔哩直播间的房间号" or room_id_text == "":
            current_config['bilibili']['roomId'] = 0
        else:
            current_config['bilibili']['roomId'] = int(room_id_text)

        # 确保tools配置存在
        if 'tools' not in current_config:
            current_config['tools'] = {}
        current_config['tools']['enabled'] = self.ui.checkBox_mcp.isChecked()
        # 确保mcp配置存在
        if 'mcp' not in current_config:
            current_config['mcp'] = {}
        current_config['mcp']['enabled'] = self.ui.checkBox_mcp_enable.isChecked()
        current_config['vision']['auto_screenshot'] = self.ui.checkBox_5.isChecked()
        current_config['context']['enable_limit'] = self.ui.checkBox_4.isChecked()
        current_config['context']['persistent_history'] = self.ui.checkBox_persistent_history.isChecked()
        current_config['auto_chat']['enabled'] = self.ui.checkBox.isChecked()
        current_config['bilibili']['enabled'] = self.ui.checkBox_2.isChecked()
        # 保存本地ASR和TTS配置（保持现有配置结构，只更新enabled状态）
        current_config['asr']['enabled'] = self.ui.checkBox_asr.isChecked()
        current_config['asr']['voice_barge_in'] = self.ui.checkBox_voice_barge_in.isChecked()
        current_config['tts']['enabled'] = self.ui.checkBox_tts.isChecked()

        # 保存TTS语言
        tts_language = self.ui.comboBox_tts_language.currentText().split(' - ')[0]
        current_config['tts']['language'] = tts_language

        # 新增：保存翻译配置
        current_config['translation'] = {
            "enabled": self.ui.checkBox_translation_enabled.isChecked(),
            "api_key": self.ui.lineEdit_translation_api_key.text(),
            "api_url": self.ui.lineEdit_translation_api_url.text(),
            "model": self.ui.lineEdit_translation_model.text(),
            "system_prompt": self.ui.textEdit_translation_prompt.toPlainText()
        }

        # 新增：保存云端配置
        if 'cloud' not in current_config:
            current_config['cloud'] = {}

        # 保存通用云端配置（从第一个标签页的控件获取，两个标签页应该同步）
        current_config['cloud']['provider'] = self.ui.lineEdit_cloud_provider.text() or self.ui.lineEdit_cloud_provider_2.text() or 'siliconflow'
        current_config['cloud']['api_key'] = self.ui.lineEdit_cloud_api_key.text() or self.ui.lineEdit_cloud_api_key_2.text()

        # 保存云端TTS配置
        if 'tts' not in current_config['cloud']:
            current_config['cloud']['tts'] = {}
        current_config['cloud']['tts']['enabled'] = self.ui.checkBox_cloud_tts_enabled.isChecked()
        current_config['cloud']['tts']['url'] = self.ui.lineEdit_cloud_tts_url.text() or 'https://api.siliconflow.cn/v1/audio/speech'
        current_config['cloud']['tts']['model'] = self.ui.lineEdit_cloud_tts_model.text() or 'FunAudioLLM/CosyVoice2-0.5B'
        current_config['cloud']['tts']['voice'] = self.ui.lineEdit_cloud_tts_voice.text()
        current_config['cloud']['tts']['response_format'] = self.ui.comboBox_cloud_tts_format.currentText()
        current_config['cloud']['tts']['speed'] = self.ui.doubleSpinBox_cloud_tts_speed.value()

        # 保存云端ASR配置
        if 'asr' not in current_config['cloud']:
            current_config['cloud']['asr'] = {}
        current_config['cloud']['asr']['enabled'] = self.ui.checkBox_cloud_asr_enabled.isChecked()
        current_config['cloud']['asr']['url'] = self.ui.lineEdit_cloud_asr_url.text() or 'https://api.siliconflow.cn/v1/audio/transcriptions'
        current_config['cloud']['asr']['model'] = self.ui.lineEdit_cloud_asr_model.text() or 'FunAudioLLM/SenseVoiceSmall'

        # 新增：保存游戏配置
        current_config['game']['Minecraft']['enabled'] = self.ui.checkBox_game_minecraft.isChecked()

        # 保存Minecraft配置到andy.json
        self.save_minecraft_config()

        # 新增：保存UI设置
        if 'subtitle_labels' not in current_config:
            current_config['subtitle_labels'] = {}
        current_config['subtitle_labels']['enabled'] = self.ui.checkBox_subtitle_enabled.isChecked()
        current_config['subtitle_labels']['user'] = self.ui.lineEdit_user_name.text() or "用户"
        current_config['subtitle_labels']['ai'] = self.ui.lineEdit_ai_name.text() or "Fake Neuro"

        # 新增：保存自动关闭服务设置
        if 'auto_close_services' not in current_config:
            current_config['auto_close_services'] = {}
        current_config['auto_close_services']['enabled'] = self.ui.checkBox_auto_close_services.isChecked()

        # 新增：保存Live2D模型选择
        selected_model = self.ui.comboBox_live2d_models.currentText()
        if selected_model and selected_model != "未找到任何模型":
            try:
                import re
                app_path = get_app_path()

                # 1. 更新main.js的优先级
                main_js_path = os.path.join(app_path, "main.js")
                with open(main_js_path, 'r', encoding='utf-8') as f:
                    main_content = f.read()

                new_priority = f"const priorityFolders = ['{selected_model}', 'Hiyouri', 'Default', 'Main']"
                main_content = re.sub(r"const priorityFolders = \[.*?\]", new_priority, main_content)

                with open(main_js_path, 'w', encoding='utf-8') as f:
                    f.write(main_content)

                # 2. 更新app.js中的角色名设置
                app_js_path = os.path.join(app_path, "app.js")
                with open(app_js_path, 'r', encoding='utf-8') as f:
                    app_content = f.read()

                # 先删除所有旧的角色名设置行
                app_content = re.sub(r'\s*global\.currentCharacterName = [\'"].*?[\'"];?\n?', '', app_content)

                # 设置全局角色名
                insert_line = f"global.currentCharacterName = '{selected_model}';"

                # 在emotionMapper创建后插入(只替换第一次匹配)
                pattern = r"(emotionMapper = new EmotionMotionMapper\(model\);)"
                if re.search(pattern, app_content):
                    replacement = f"\\1\n        {insert_line}"
                    app_content = re.sub(pattern, replacement, app_content, count=1)
                else:
                    # 备选位置：在模型设置后
                    pattern = r"(currentModel = model;)"
                    replacement = f"\\1\n        {insert_line}"
                    app_content = re.sub(pattern, replacement, app_content, count=1)

                with open(app_js_path, 'w', encoding='utf-8') as f:
                    f.write(app_content)

                print(f"已应用Live2D模型和角色: {selected_model}")

                # 重新加载动作配置以匹配新选择的角色
                try:
                    self.load_motion_config()
                    self.refresh_drag_drop_interface()
                    print(f"已更新动作界面为角色: {selected_model}")
                except Exception as refresh_error:
                    print(f"更新动作界面失败: {refresh_error}")

            except Exception as e:
                print(f"应用Live2D模型失败: {str(e)}")

        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(current_config, f, ensure_ascii=False, indent=2)
            
        self.save_motion_config() 

        

       # 尝试通知前端重新加载配置 (先检查服务是否运行)
        if is_server_running():
            try:
                import requests
                response = requests.post('http://localhost:3002/reload-config', timeout=2)
                if response.status_code == 200:
                    print("已通知前端重新加载配置")
                else:
                    print("通知前端重新加载配置失败")
            except Exception as e:
                print(f"无法通知前端重新加载配置: {e}")
        else:
            print("桌宠应用未运行，跳过实时重载通知。")

        # 重新加载配置到内存，确保立即生效
        self.config = current_config

        # 使用Toast提示替代QMessageBox
        self.toast.show_message("配置已保存，模型选择已应用", 1500)

    def init_live2d_models(self):
        """初始化Live2D模型功能"""
        try:
            self.refresh_model_list()
        except Exception as e:
            print(f"初始化Live2D模型失败: {e}")
            # 如果失败，至少设置一个默认项
            self.ui.comboBox_live2d_models.clear()
            self.ui.comboBox_live2d_models.addItem("未找到任何模型")

    def scan_live2d_models(self):
        """扫描2D文件夹下的Live2D模型"""
        models = []
        app_path = get_app_path()
        models_dir = os.path.join(app_path, "2D")

        if os.path.exists(models_dir):
            for folder in os.listdir(models_dir):
                folder_path = os.path.join(models_dir, folder)
                if os.path.isdir(folder_path):
                    # 检查文件夹里有没有.model3.json文件
                    for file in os.listdir(folder_path):
                        if file.endswith('.model3.json'):
                            models.append(folder)
                            break
        return models

    def refresh_model_list(self):
        """刷新模型列表"""
        models = self.scan_live2d_models()
        self.ui.comboBox_live2d_models.clear()

        if not models:
            self.ui.comboBox_live2d_models.addItem("未找到任何模型")
            return

        for model in models:
            self.ui.comboBox_live2d_models.addItem(model)

        # 新增：读取main.js中当前的优先级设置
        try:
            app_path = get_app_path()
            main_js_path = os.path.join(app_path, "main.js")

            with open(main_js_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取当前的优先级列表
            match = re.search(r"const priorityFolders = \[(.*?)\]", content)
            if match:
                priorities = [p.strip().strip("'\"") for p in match.group(1).split(',')]
                if priorities:
                    current_model = priorities[0]  # 第一个就是当前使用的模型

                    # 在下拉框中选择对应的模型
                    index = self.ui.comboBox_live2d_models.findText(current_model)
                    if index >= 0:
                        self.ui.comboBox_live2d_models.setCurrentIndex(index)
        except Exception as e:
            print(f"读取当前模型设置失败: {str(e)}")

        self.toast.show_message(f"找到 {len(models)} 个Live2D模型", 2000)

    def update_current_model_display(self):
        """更新当前模型显示"""
        pass  # 暂时留空

    def check_all_service_status(self):
        """启动时检查所有服务状态并更新UI"""
        self.check_service_status('tts', 5000, 'label_terminal_status')
        self.check_service_status('asr', 1000, 'label_asr_status')
        self.check_service_status('bert', 6007, 'label_bert_status')
        self.check_service_status('rag', 8002, 'label_rag_status')

    def check_service_status(self, service_name, port, status_label):
        """检查单个服务状态"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()

            if result == 0:
                # 服务正在运行
                getattr(self.ui, status_label).setText(f"状态：{service_name.upper()}服务正在运行")
                self.update_status_indicator(service_name, True)
            else:
                # 服务未运行
                getattr(self.ui, status_label).setText(f"状态：{service_name.upper()}服务未启动")
                self.update_status_indicator(service_name, False)
        except Exception:
            getattr(self.ui, status_label).setText(f"状态：{service_name.upper()}服务未启动")
            self.update_status_indicator(service_name, False)

    def update_status_indicator(self, service_name, is_running):
        """更新状态指示器"""
        indicators = {
            'tts': 'label_tts_status_indicator',
            'asr': 'label_asr_status_indicator',
            'bert': 'label_bert_status_indicator',
            'rag': 'label_rag_status_indicator'
        }

        if service_name in indicators:
            indicator = getattr(self.ui, indicators[service_name], None)
            if indicator:
                if is_running:
                    indicator.setText("●")
                    indicator.setStyleSheet("color: #00AA00; font-size: 20px;")
                else:
                    indicator.setText("○")
                    indicator.setStyleSheet("color: #888888; font-size: 20px;")

    def show_tutorial(self):
        """显示教程页面"""
        self.load_readme_content()
        self.ui.stackedWidget.setCurrentIndex(8)  # 假设教程页面是第8个

    def load_readme_content(self):
        """加载README.md内容并显示本地图片"""
        try:
            app_path = get_app_path()
            readme_path = os.path.join(app_path, "README.md")

            with open(readme_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 转换Markdown图片为HTML，使用绝对路径
            import re
            def replace_image(match):
                alt_text = match.group(1)
                img_path = match.group(2)

                # 如果是相对路径，转换为绝对路径
                if img_path.startswith('./'):
                    img_path = img_path[2:]  # 去掉 ./
                    full_path = os.path.join(app_path, img_path).replace('\\', '/')
                    # 转换为file://协议
                    full_path = f"file:///{full_path}"
                else:
                    full_path = img_path

                # 强制设置图片宽度为600px，高度自动
                return f'<br><img src="{full_path}" alt="{alt_text}" width="1300"><br>'

            # 替换图片语法
            content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_image, content)

            # 简单的Markdown转HTML
            content = content.replace('\n### ', '\n<h3>')
            content = content.replace('\n## ', '\n<h2>')
            content = content.replace('\n# ', '\n<h1>')
            content = content.replace('\n\n', '<br><br>')

            # 使用HTML模式显示
            self.ui.textEdit_tutorial.setHtml(content)

        except Exception as e:
            self.ui.textEdit_tutorial.setPlainText(f"无法加载README.md文件: {str(e)}")

    def run_startup_scan(self):
        """启动时自动运行皮套动作扫描"""
        try:
            app_path = get_app_path()
            script_file = os.path.join(app_path, "AI_set_live2d.py")

            print(f"正在检查脚本文件: {script_file}")

            if os.path.exists(script_file):
                print("找到扫描脚本，正在后台启动...")

                # --- 核心修复：直接调用python执行脚本，而不是通过.bat和shell ---
                # 'python' 会使用系统PATH中找到的python解释器，通常是当前激活的conda环境
                command = ["python", script_file]

                process = subprocess.Popen(
                    command,
                    shell=False,  # 设置为 False，避免创建额外的cmd进程
                    cwd=app_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='ignore',
                    creationflags=subprocess.CREATE_NO_WINDOW # 在Windows上不创建控制台窗口
                )

                # 启动线程读取输出
                def read_output():
                    for line in iter(process.stdout.readline, ''):
                        if line.strip():
                            print(f"扫描输出: {line.strip()}")
                    # --- 核心修复：扫描结束后，发射信号通知主线程刷新UI ---
                    self.scan_complete_signal.emit()

                from threading import Thread
                Thread(target=read_output, daemon=True).start()
                print("后台扫描进程已启动")
            else:
                print(f"未找到扫描脚本: {script_file}")

        except Exception as e:
            print(f"运行皮套动作扫描失败: {str(e)}")

    def start_minecraft_terminal(self):
        """启动Minecraft游戏终端"""
        try:
            if self.minecraft_terminal_process and hasattr(self.minecraft_terminal_process, 'poll') and self.minecraft_terminal_process.poll() is None:
                self.toast.show_message("Minecraft游戏终端已在运行中", 2000)
                return

            app_path = get_app_path()
            bat_file = os.path.join(app_path, "GAME", "Minecraft", "开启游戏终端.bat")
            
            if not os.path.exists(bat_file):
                error_msg = f"找不到文件：{bat_file}"
                print(f"错误：{error_msg}")
                self.toast.show_message(error_msg, 3000)
                return

            print("正在启动Minecraft游戏终端.....")
            
            # 启动bat文件 - 直接用os.system启动新cmd窗口
            minecraft_dir = os.path.join(app_path, "GAME", "Minecraft")
            current_dir = os.getcwd()  # 保存当前目录
            
            os.chdir(minecraft_dir)
            os.system(f'start cmd /k "{bat_file}"')
            os.chdir(current_dir)  # 恢复原来的目录
            
            # 保持进程引用为了后续管理
            self.minecraft_terminal_process = True  # 标记为已启动

            print("Minecraft游戏终端进程已启动")
            print("当前Minecraft游戏终端已成功启动！！！")
            
            self.toast.show_message("Minecraft游戏终端启动成功", 2000)

        except Exception as e:
            error_msg = f"启动Minecraft游戏终端失败：{str(e)}"
            print(f"错误：{error_msg}")
            self.toast.show_message(error_msg, 3000)

    def stop_minecraft_terminal(self):
        """关闭Minecraft游戏终端"""
        try:
            if self.minecraft_terminal_process and hasattr(self.minecraft_terminal_process, 'poll') and self.minecraft_terminal_process.poll() is None:
                self.minecraft_terminal_process.terminate()
                self.minecraft_terminal_process = None
                print("Minecraft游戏终端已关闭")
                self.toast.show_message("Minecraft游戏终端已关闭", 2000)
            else:
                self.minecraft_terminal_process = None  # 重置状态
                self.toast.show_message("Minecraft游戏终端未在运行", 2000)
        except Exception as e:
            error_msg = f"关闭Minecraft游戏终端失败：{str(e)}"
            print(f"错误：{error_msg}")
            self.toast.show_message(error_msg, 3000)

    def refresh_tools_list(self):
        """刷新工具列表"""
        try:
            # 获取server-tools文件夹路径
            base_path = get_app_path()
            tools_path = os.path.join(base_path, "server-tools")

            # 检查文件夹是否存在
            if not os.path.exists(tools_path):
                self.toast.show_message("server-tools文件夹不存在", 3000)
                return

            # 清空现有列表
            self.ui.listWidget_tools.clear()

            # 读取文件夹中的文件
            files = os.listdir(tools_path)

            for file in files:
                file_path = os.path.join(tools_path, file)

                # 只处理文件，跳过文件夹
                if os.path.isfile(file_path):
                    status = ""

                    if file.endswith('.js'):
                        # js文件，跳过index.js
                        if file.lower() == 'index.js':
                            continue
                        # 去掉.js后缀显示
                        display_name = file[:-3]  # 移除.js
                        status_icon = "●"  # 绿色实心圆圈
                        status = "已启动"
                    elif file.endswith('.txt'):
                        # txt文件，去掉.txt后缀显示
                        display_name = file[:-4]  # 移除.txt
                        status_icon = "○"  # 空白圆圈
                        status = "未启动"
                    else:
                        # 其他文件类型，跳过
                        continue

                    # 添加到列表中，同时保存原始文件名作为数据
                    item_text = f"{status_icon} {display_name} - {status}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, file)  # 保存原始文件名
                    item.setData(Qt.UserRole + 1, status)  # 保存状态信息
                    self.ui.listWidget_tools.addItem(item)

            self.toast.show_message("工具列表已刷新", 2000)

        except Exception as e:
            error_msg = f"刷新工具列表失败：{str(e)}"
            print(f"错误：{error_msg}")
            self.toast.show_message(error_msg, 3000)

    def refresh_mcp_tools_list(self):
        """刷新MCP工具列表"""
        try:
            # 获取mcp/tools文件夹路径
            base_path = get_app_path()
            mcp_tools_path = os.path.join(base_path, "mcp", "tools")

            # 检查文件夹是否存在
            if not os.path.exists(mcp_tools_path):
                self.toast.show_message("mcp/tools文件夹不存在", 3000)
                return

            # 清空现有列表
            self.ui.listWidget_mcp_tools.clear()

            # 读取文件夹中的文件
            files = os.listdir(mcp_tools_path)

            for file in files:
                file_path = os.path.join(mcp_tools_path, file)

                # 只处理文件，跳过文件夹
                if os.path.isfile(file_path):
                    status = ""

                    if file.endswith('.js'):
                        # js文件，跳过index.js
                        if file.lower() == 'index.js':
                            continue
                        # 去掉.js后缀显示
                        display_name = file[:-3]  # 移除.js
                        status_icon = "●"  # 绿色实心圆圈
                        status = "已启动"
                    elif file.endswith('.txt'):
                        # txt文件，去掉.txt后缀显示
                        display_name = file[:-4]  # 移除.txt
                        status_icon = "○"  # 空白圆圈
                        status = "未启动"
                    else:
                        # 其他文件类型，跳过
                        continue

                    # 添加到列表中，同时保存原始文件名作为数据
                    item_text = f"{status_icon} {display_name} - {status}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, file)  # 保存原始文件名
                    item.setData(Qt.UserRole + 1, status)  # 保存状态信息
                    self.ui.listWidget_mcp_tools.addItem(item)

            self.toast.show_message("MCP工具列表已刷新", 2000)

        except Exception as e:
            error_msg = f"刷新MCP工具列表失败：{str(e)}"
            print(f"错误：{error_msg}")
            self.toast.show_message(error_msg, 3000)

    def toggle_tool_status(self, item):
        """切换工具的启动状态（js <-> txt）"""
        try:
            # 获取显示的文本和原始文件名
            item_text = item.text()
            original_filename = item.data(Qt.UserRole)  # 获取保存的原始文件名
            current_status = item.data(Qt.UserRole + 1)  # 获取保存的状态信息

            # 格式：● display_name - 状态 或 ○ display_name - 状态
            if item_text.startswith("● "):
                # 移除"● "，然后分割" - "
                remaining_text = item_text[2:]
                parts = remaining_text.split(" - ")
                if len(parts) != 2:
                    return
                display_name = parts[0]
            elif item_text.startswith("○ "):
                # 移除"○ "，然后分割" - "
                remaining_text = item_text[2:]
                parts = remaining_text.split(" - ")
                if len(parts) != 2:
                    return
                display_name = parts[0]
            else:
                return

            # 获取server-tools文件夹路径
            base_path = get_app_path()
            tools_path = os.path.join(base_path, "server-tools")
            current_file_path = os.path.join(tools_path, original_filename)

            # 检查文件是否存在
            if not os.path.exists(current_file_path):
                self.toast.show_message(f"文件不存在：{original_filename}", 3000)
                return

            # 跳过index.js文件
            if original_filename.lower() == 'index.js':
                self.toast.show_message("index.js文件不能切换状态", 3000)
                return

            # 根据当前状态决定切换方向
            if current_status == "已启动" and original_filename.endswith('.js'):
                # js -> txt (启动 -> 关闭)
                new_filename = original_filename[:-3] + '.txt'  # 移除.js，添加.txt
                new_status = "未启动"
                new_status_icon = "○"  # 空白圆圈
            elif current_status == "未启动" and original_filename.endswith('.txt'):
                # txt -> js (关闭 -> 启动)
                new_filename = original_filename[:-4] + '.js'  # 移除.txt，添加.js
                new_status = "已启动"
                new_status_icon = "●"  # 绿色实心圆圈
            else:
                self.toast.show_message("文件状态异常，无法切换", 3000)
                return

            new_file_path = os.path.join(tools_path, new_filename)

            # 重命名文件
            os.rename(current_file_path, new_file_path)

            # 更新列表中的项目文本和数据
            new_item_text = f"{new_status_icon} {display_name} - {new_status}"
            item.setText(new_item_text)
            item.setData(Qt.UserRole, new_filename)  # 更新保存的原始文件名
            item.setData(Qt.UserRole + 1, new_status)  # 更新保存的状态信息

            self.toast.show_message(f"{display_name} 已{new_status}", 2000)

        except Exception as e:
            error_msg = f"切换工具状态失败：{str(e)}"
            print(f"错误：{error_msg}")
            self.toast.show_message(error_msg, 3000)

    def toggle_mcp_tool_status(self, item):
        """切换MCP工具的启动状态（js <-> txt）"""
        try:
            # 获取显示的文本和原始文件名
            item_text = item.text()
            original_filename = item.data(Qt.UserRole)  # 获取保存的原始文件名
            current_status = item.data(Qt.UserRole + 1)  # 获取保存的状态信息

            # 格式：● display_name - 状态 或 ○ display_name - 状态
            if item_text.startswith("● "):
                # 移除"● "，然后分割" - "
                remaining_text = item_text[2:]
                parts = remaining_text.split(" - ")
                if len(parts) != 2:
                    return
                display_name = parts[0]
            elif item_text.startswith("○ "):
                # 移除"○ "，然后分割" - "
                remaining_text = item_text[2:]
                parts = remaining_text.split(" - ")
                if len(parts) != 2:
                    return
                display_name = parts[0]
            else:
                return

            # 获取mcp/tools文件夹路径
            base_path = get_app_path()
            mcp_tools_path = os.path.join(base_path, "mcp", "tools")
            current_file_path = os.path.join(mcp_tools_path, original_filename)

            # 检查文件是否存在
            if not os.path.exists(current_file_path):
                self.toast.show_message(f"文件不存在：{original_filename}", 3000)
                return

            # 跳过index.js文件
            if original_filename.lower() == 'index.js':
                self.toast.show_message("index.js文件不能切换状态", 3000)
                return

            # 根据当前状态决定切换方向
            if current_status == "已启动" and original_filename.endswith('.js'):
                # js -> txt (启动 -> 关闭)
                new_filename = original_filename[:-3] + '.txt'  # 移除.js，添加.txt
                new_status = "未启动"
                new_status_icon = "○"  # 空白圆圈
            elif current_status == "未启动" and original_filename.endswith('.txt'):
                # txt -> js (关闭 -> 启动)
                new_filename = original_filename[:-4] + '.js'  # 移除.txt，添加.js
                new_status = "已启动"
                new_status_icon = "●"  # 绿色实心圆圈
            else:
                self.toast.show_message("文件状态异常，无法切换", 3000)
                return

            new_file_path = os.path.join(mcp_tools_path, new_filename)

            # 重命名文件
            os.rename(current_file_path, new_file_path)

            # 更新列表中的项目文本和数据
            new_item_text = f"{new_status_icon} {display_name} - {new_status}"
            item.setText(new_item_text)
            item.setData(Qt.UserRole, new_filename)  # 更新保存的原始文件名
            item.setData(Qt.UserRole + 1, new_status)  # 更新保存的状态信息

            self.toast.show_message(f"MCP {display_name} 已{new_status}", 2000)

        except Exception as e:
            error_msg = f"切换MCP工具状态失败：{str(e)}"
            print(f"错误：{error_msg}")
            self.toast.show_message(error_msg, 3000)

    def setup_api_key_visibility_toggles(self):
        """为API KEY输入框添加小眼睛图标"""
        try:
            # API KEY输入框列表
            api_key_fields = [
                self.ui.lineEdit,  # 主要LLM API KEY
                self.ui.lineEdit_translation_api_key,  # 同传API KEY
                self.ui.lineEdit_minecraft_api_key  # Minecraft API KEY
            ]

            for line_edit in api_key_fields:
                if line_edit:
                    # 创建眼睛图标动作
                    eye_action = QAction(line_edit)
                    eye_action.setIcon(self.create_eye_icon("🙈"))
                    eye_action.setToolTip("点击显示/隐藏API KEY")

                    # 添加到输入框右侧
                    line_edit.addAction(eye_action, QLineEdit.TrailingPosition)

                    # 绑定点击事件
                    def toggle_visibility(checked, le=line_edit, action=eye_action):
                        if le.echoMode() == QLineEdit.Password:
                            # 切换为显示
                            le.setEchoMode(QLineEdit.Normal)
                            action.setIcon(self.create_eye_icon("👁"))
                            action.setToolTip("点击隐藏API KEY")
                        else:
                            # 切换为隐藏
                            le.setEchoMode(QLineEdit.Password)
                            action.setIcon(self.create_eye_icon("🙈"))
                            action.setToolTip("点击显示API KEY")

                    eye_action.triggered.connect(toggle_visibility)

        except Exception as e:
            print(f"设置API KEY小眼睛图标失败: {e}")

    def create_eye_icon(self, emoji):
        """创建眼睛图标"""
        try:
            # 创建一个简单的图标
            pixmap = QPixmap(24, 24)
            pixmap.fill(Qt.transparent)

            painter = QPainter(pixmap)
            painter.setFont(QFont("Segoe UI Emoji", 12))
            painter.drawText(pixmap.rect(), Qt.AlignCenter, emoji)
            painter.end()

            return QIcon(pixmap)
        except:
            # 如果创建图标失败，返回空图标
            return QIcon()


if __name__ == '__main__':
    # # 分辨率自适应 - 暂时禁用，可能导致UI尺寸异常
    # QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)

    app = QApplication(sys.argv)
    w = set_pyqt()
    w.show()
    sys.exit(app.exec_())