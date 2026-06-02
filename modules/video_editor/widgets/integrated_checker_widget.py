import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QScrollArea, QCheckBox, QMessageBox, QFrame, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from ..services.integrated_worker import ScanWorker, MultiAssembleWorker

class ProjectRow(QFrame):
    merge_clicked = pyqtSignal(dict)
    
    def __init__(self, project_data):
        super().__init__()
        self.data = project_data
        self.setObjectName("project_row")
        self.init_ui()
        
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)
        
        # 1. 复选框
        self.checkbox = QCheckBox()
        self.checkbox.setFixedWidth(20)
        layout.addWidget(self.checkbox)
        
        # 2. 状态图标
        self.status_label = QLabel()
        self.status_label.setFixedWidth(24)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if self.data["is_complete"]:
            self.status_label.setText("✅")
            self.status_label.setStyleSheet("font-size: 16px;")
            self.status_label.setToolTip("所有片段完整")
        else:
            self.status_label.setText("⚠️")
            self.status_label.setStyleSheet("font-size: 16px; color: #ff4d4f; font-weight: bold;")
            self.status_label.setCursor(Qt.CursorShape.PointingHandCursor)
            self.status_label.setToolTip("发现缺失！点击查看详情")
            self.status_label.mousePressEvent = self.show_details
        layout.addWidget(self.status_label)
        
        # 3. 项目名称
        name_label = QLabel(self.data["name"])
        name_label.setStyleSheet("font-weight: 600; font-size: 14px; color: #5C4A32;")
        layout.addWidget(name_label, 1) # 占据空间
        
        # 4. 进度/统计
        count_label = QLabel(f"片段: {self.data['found_actual']} / {self.data['total_expected']}")
        count_label.setStyleSheet("color: #A88A5A; font-weight: 500;")
        layout.addWidget(count_label)
        
        # 5. 单独合并按钮
        self.merge_btn = QPushButton("单独合并")
        self.merge_btn.setFixedWidth(100) # 稍微加宽防止截断
        self.merge_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.merge_btn.clicked.connect(lambda: self.merge_clicked.emit(self.data))
        layout.addWidget(self.merge_btn)
        
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            #project_row { 
                background-color: #FFFBF4; 
                border: 1px solid #E3D9C9; 
                border-radius: 12px; 
            }
            #project_row:hover { 
                background-color: #FDF6E9;
                border-color: #D1B585;
            }
            QPushButton {
                background-color: #FFFDF8;
                border: 1px solid #E0D2BE;
                border-radius: 15px;
                padding: 4px;
                color: #5C4A32;
            }
            QPushButton:hover {
                background-color: #F4E3C5;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)

    def show_details(self, event):
        missing = [f"part{p}" for p in self.data["missing_parts"]]
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("项目缺失明细")
        msg_box.setIcon(QMessageBox.Icon.Warning)
        
        content = f"<b>项目:</b> {self.data['name']}<br><br><b>缺失片段:</b><br>" + "<br>".join(missing)
        msg_box.setText(content)
        
        # 显式指定样式，确保在任何全局主题下都能看清
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #FFFCF7;
            }
            QLabel {
                color: #5C4A32;
                font-family: 'Segoe UI', 'Microsoft YaHei';
                font-size: 13px;
                min-width: 250px;
            }
            QPushButton {
                background-color: #FFFDF8;
                border: 1px solid #E0D2BE;
                border-radius: 12px;
                padding: 6px 20px;
                color: #5C4A32;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #F4E3C5;
            }
        """)
        msg_box.exec()

class VideoIntegratedWidget(QWidget):
    SUB_FOLDER_AUDIO = "分段音频"
    SUB_FOLDER_VIDEO = "分段视频"
    SUB_FOLDER_OUTPUT = "半成品"

    def __init__(self, config=None):
        super().__init__()
        self.config = config
        self.current_root = None
        self.projects = []
        self.rows = [] # 存储项目行引用以便更新
        # 设置全局背景色
        self.setStyleSheet("background-color: #F7F3EC;")
        self.init_ui()
        if self.config:
            self.update_default_path(self.config.get_global_output_dir())

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 头部工具栏
        header_card = QFrame()
        header_card.setStyleSheet("background-color: #FFFBF4; border: 1px solid #E3D9C9; border-radius: 12px;")
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        self.path_label = QLabel("当前目录: 未设置")
        self.path_label.setStyleSheet("color: #8A5B2E; font-weight: 600; border: none;")
        header_layout.addWidget(self.path_label, 1)

        self.btn_refresh = QPushButton("🔄 重新扫描")
        self.btn_refresh.setMinimumHeight(32)
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.setStyleSheet("""
            QPushButton { 
                background-color: #FFFDF8; border: 1px solid #E0D2BE; border-radius: 16px; padding: 0 15px; color: #5C4A32;
            }
            QPushButton:hover { background-color: #F4EBDE; }
        """)
        self.btn_refresh.clicked.connect(self.scan_projects)
        header_layout.addWidget(self.btn_refresh)

        # 批量选择按钮组
        selection_layout = QHBoxLayout()
        selection_layout.setSpacing(8)
        
        btn_all = QPushButton("全选")
        btn_none = QPushButton("全不选")
        btn_inv = QPushButton("反选")
        
        for btn in [btn_all, btn_none, btn_inv]:
            btn.setFixedWidth(80) # 进一步增加宽度防止截断
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton { 
                    background-color: #FDF6E9; border: 1px solid #DDCFBC; border-radius: 12px; font-size: 12px; color: #8A5B2E;
                }
                QPushButton:hover { background-color: #F4E3C5; }
            """)
            selection_layout.addWidget(btn)
            
        btn_all.clicked.connect(lambda: self.set_all_selection(True))
        btn_none.clicked.connect(lambda: self.set_all_selection(False))
        btn_inv.clicked.connect(self.invert_selection)
        
        header_layout.addLayout(selection_layout)

        self.btn_batch_merge = QPushButton("🚀 一键合并选中项目")
        self.btn_batch_merge.setMinimumHeight(36)
        self.btn_batch_merge.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_batch_merge.setStyleSheet("""
            QPushButton { 
                background-color: #F1A94A; color: #4A310F; border: none; border-radius: 18px; padding: 0 20px; font-weight: 600;
            }
            QPushButton:hover { background-color: #F7B963; }
            QPushButton:disabled { background-color: #F3EEE5; color: #B9B1A4; }
        """)
        self.btn_batch_merge.clicked.connect(self.batch_merge)
        header_layout.addWidget(self.btn_batch_merge)
        
        layout.addWidget(header_card)

        # 列表滚动区域
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        self.list_container = QWidget()
        self.list_container.setStyleSheet("background-color: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.list_layout.setContentsMargins(0, 5, 0, 5)
        self.list_layout.setSpacing(10)
        
        self.scroll.setWidget(self.list_container)
        layout.addWidget(self.scroll, 1)

    def update_default_path(self, global_path):
        self.current_root = global_path
        if global_path:
            self.path_label.setText(f"当前目录: {global_path}")
            self.scan_projects()
        else:
            self.path_label.setText("当前目录: 未设置")
            self.clear_list()

    def clear_list(self):
        for row in self.rows:
            self.list_layout.removeWidget(row)
            row.deleteLater()
        self.rows = []

    def scan_projects(self):
        root = self.path_label.text().split(": ", 1)[1]
        if not os.path.exists(root):
            return
        
        # 清空当前显示
        self.clear_list()
        
        audio_dir = os.path.join(root, self.SUB_FOLDER_AUDIO)
        video_dir = os.path.join(root, self.SUB_FOLDER_VIDEO)
        
        self.scan_worker = ScanWorker(audio_dir, video_dir)
        self.scan_worker.finished.connect(self.on_scan_finished)
        self.scan_worker.error.connect(self.on_error)
        self.scan_worker.start()
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("⏳ 扫描中...")

    def set_all_selection(self, checked):
        for row in self.rows:
            row.checkbox.setChecked(checked)

    def invert_selection(self):
        for row in self.rows:
            row.checkbox.setChecked(not row.checkbox.isChecked())

    def on_scan_finished(self, projects):
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("🔄 重新扫描")
        self.projects = projects
        
        if not projects:
            self.list_layout.addWidget(QLabel("📭 没找到任何匹配的项目片段，请检查分段音频/视频文件夹。"))
            return

        self.rows = []
        for p in projects:
            row = ProjectRow(p)
            row.merge_clicked.connect(self.start_merge_one)
            self.list_layout.addWidget(row)
            self.rows.append(row)

    def start_merge_one(self, project_data):
        self.do_merge([project_data])

    def batch_merge(self):
        selected = []
        for row in self.rows:
            if row.checkbox.isChecked():
                selected.append(row.data)
        
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选需要合并的项目。")
            return
            
        self.do_merge(selected)

    def do_merge(self, project_list):
        output_dir = os.path.join(self.current_root, self.SUB_FOLDER_OUTPUT)
        video_dir = os.path.join(self.current_root, self.SUB_FOLDER_VIDEO)
        
        # 检查是否包含不完整的项目
        incompletes = [p["name"] for p in project_list if not p["is_complete"]]
        if incompletes:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("确认合并")
            msg_box.setIcon(QMessageBox.Icon.Question)
            msg_box.setText(f"<b>以下项目存在缺失片段：</b><br>{', '.join(incompletes)}<br><br>是否仍然强制合并？(缺失部分将导致输出视频变短)")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.No)
            
            msg_box.setStyleSheet("""
                QMessageBox { background-color: #FFFCF7; }
                QLabel { color: #5C4A32; font-family: 'Segoe UI', 'Microsoft YaHei'; }
                QPushButton { 
                    background-color: #FFFDF8; border: 1px solid #E0D2BE; border-radius: 12px; 
                    padding: 6px 20px; color: #5C4A32; min-width: 80px;
                }
                QPushButton:hover { background-color: #F4E3C5; }
            """)
            
            if msg_box.exec() == QMessageBox.StandardButton.No:
                return

        # 开始合并
        self.btn_batch_merge.setEnabled(False)
        self.btn_batch_merge.setText("合并中...")
        
        self.merge_worker = MultiAssembleWorker(video_dir, output_dir, project_list)
        self.merge_worker.progress_log.connect(print) # 可以扩展一个进度对话框或日志区
        self.merge_worker.finished.connect(self.on_merge_finished)
        self.merge_worker.error.connect(self.on_error)
        self.merge_worker.start()

    def on_merge_finished(self, msg):
        self.btn_batch_merge.setEnabled(True)
        self.btn_batch_merge.setText("🚀 批量合并选中项目")
        self.show_styled_message("任务完成", msg, QMessageBox.Icon.Information)

    def on_error(self, err_msg):
        self.btn_refresh.setEnabled(True)
        self.btn_batch_merge.setEnabled(True)
        self.btn_batch_merge.setText("🚀 批量合并选中项目")
        self.show_styled_message("发生错误", err_msg, QMessageBox.Icon.Critical)

    def show_styled_message(self, title, text, icon):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setIcon(icon)
        msg_box.setText(text)
        msg_box.setStyleSheet("""
            QMessageBox { background-color: #FFFCF7; }
            QLabel { color: #5C4A32; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 13px; min-width: 200px; }
            QPushButton { 
                background-color: #FFFDF8; border: 1px solid #E0D2BE; border-radius: 12px; 
                padding: 6px 20px; color: #5C4A32; min-width: 80px;
            }
            QPushButton:hover { background-color: #F4E3C5; }
        """)
        msg_box.exec()
