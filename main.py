import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
    QLabel, QHBoxLayout, QPushButton, QFileDialog, QLineEdit, QGroupBox
)
from PyQt6.QtCore import Qt

# 解决 modules 导入问题
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from modules.config_manager import ConfigManager

class DesktopApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quick Tools - 自媒体工具箱")
        self.resize(900, 700) # Ensure window is resizable and defaults to a reasonable size
        # self.setGeometry(100, 100, 1000, 750) # Removed fixed geometry to avoid high-DPI scaling issues
        self.config = ConfigManager()
        
        # 主容器
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        
        # --- 顶部：全局设置区域 ---
        self.init_global_settings(main_layout)
        
        # --- 中部：功能标签页 ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        self.init_tabs()
        
        # 全局样式
        # 加载外部样式表
        self.load_stylesheet()

    def load_stylesheet(self):
        try:
            style_path = os.path.join(current_dir, "resources", "style.qss")
            with open(style_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            print(f"Failed to load stylesheet: {e}")

    def init_global_settings(self, parent_layout):
        group = QGroupBox("全局设置")
        layout = QHBoxLayout()
        
        layout.addWidget(QLabel("📂 默认总输出路径:"))
        
        self.global_path_edit = QLineEdit()
        self.global_path_edit.setReadOnly(True)
        self.global_path_edit.setText(self.config.get_global_output_dir())
        self.global_path_edit.setPlaceholderText("未设置 (各模块默认保存在原目录)")
        layout.addWidget(self.global_path_edit)
        
        btn_select = QPushButton("设置路径...")
        btn_select.clicked.connect(self.set_global_path)
        layout.addWidget(btn_select)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def set_global_path(self):
        d = QFileDialog.getExistingDirectory(self, "选择全局共享输出目录")
        if d:
            self.config.set_global_output_dir(d)
            self.global_path_edit.setText(d)
            
            # [更新] 实时通知各个子模块
            if hasattr(self, 'tab_audio'):
                self.tab_audio.update_default_path(d)
            if hasattr(self, 'tab_file'):
                self.tab_file.update_default_path(d)

    def init_tabs(self):
        # 音频工具页
        from modules.audio_manager import AudioManagerUI
        self.tab_audio = AudioManagerUI()
        self.tabs.addTab(self.tab_audio, "🎵 音频工具")

        # 视频工具页占位符
        self.tab_video = QWidget()
        self.tabs.addTab(self.tab_video, "🎬 视频工具")
        self._setup_placeholder(self.tab_video, "视频拼接与编辑\n(开发中)")

        # 文本工具页占位符
        self.tab_text = QWidget()
        self.tabs.addTab(self.tab_text, "📝 文本工具")
        self._setup_placeholder(self.tab_text, "文本处理与操作\n(开发中)")

        # 文件管理页
        from modules.file_manager import FileManagerUI
        self.tab_file = FileManagerUI()
        self.tabs.addTab(self.tab_file, "📂 文件管理")
        
        # HeyGen 自动 (新模块)
        from modules.heygen_manager import HeyGenManagerUI
        self.tab_heygen = HeyGenManagerUI()
        self.tabs.addTab(self.tab_heygen, "🤖 HeyGen 自动")

    def _setup_placeholder(self, tab, message):
        layout = QVBoxLayout()
        label = QLabel(message)
        label.setStyleSheet("font-size: 18px; color: #555;")
        layout.addWidget(label)
        center_layout = QVBoxLayout()
        center_layout.addStretch()
        center_layout.addLayout(layout)
        center_layout.addStretch()
        
        from PyQt6.QtCore import Qt
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        tab.setLayout(center_layout)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DesktopApp()
    window.show()
    sys.exit(app.exec())
