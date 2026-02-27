import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QFileDialog, QMessageBox, QLineEdit, QCheckBox, QTextEdit
)
from ..services import MatchWorker

class AudioMatchWidget(QWidget):
    SUB_FOLDER_AUDIO = "分段音频"
    SUB_FOLDER_VIDEO = "分段视频"

    def __init__(self, config=None):
        super().__init__()
        self.config = config
        self.init_ui()
        if self.config:
            self.update_default_path(self.config.get_global_output_dir())
        
    def init_ui(self):
        layout = QVBoxLayout()
        info_label = QLabel("💡 功能说明: 将[视频文件夹]中的视频，与[音频文件夹]中的音频进行指纹比对。匹配成功自动重命名。")
        info_label.setStyleSheet("color: #666; font-style: italic; margin-bottom: 10px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        layout.addWidget(QLabel("🎵 音频源文件夹:"))
        h1 = QHBoxLayout()
        self.audio_dir_edit = QLineEdit()
        h1.addWidget(self.audio_dir_edit)
        btn1 = QPushButton("浏览...")
        btn1.clicked.connect(lambda: self.select_dir(self.audio_dir_edit))
        h1.addWidget(btn1)
        layout.addLayout(h1)
        layout.addWidget(QLabel("🎬 视频目标文件夹:"))
        h2 = QHBoxLayout()
        self.video_dir_edit = QLineEdit()
        h2.addWidget(self.video_dir_edit)
        btn2 = QPushButton("浏览...")
        btn2.clicked.connect(lambda: self.select_dir(self.video_dir_edit))
        h2.addWidget(btn2)
        layout.addLayout(h2)
        self.chk_rename = QCheckBox("匹配成功后自动重命名视频文件")
        self.chk_rename.setChecked(True)
        layout.addWidget(self.chk_rename)
        self.run_btn = QPushButton("🚀 开始分析与匹配")
        self.run_btn.setMinimumHeight(45)
        self.run_btn.clicked.connect(self.run_matching)
        layout.addWidget(self.run_btn)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)
        self.setLayout(layout)
        
    def select_dir(self, line_edit):
        d = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if d: line_edit.setText(d)
    
    def update_default_path(self, global_path):
        if global_path:
            audio_path = os.path.normpath(os.path.join(global_path, self.SUB_FOLDER_AUDIO))
            video_path = os.path.normpath(os.path.join(global_path, self.SUB_FOLDER_VIDEO))
            self.audio_dir_edit.setText(audio_path)
            self.video_dir_edit.setText(video_path)
            
    def run_matching(self):
        audio_dir = self.audio_dir_edit.text().strip()
        video_dir = self.video_dir_edit.text().strip()
        if not audio_dir or not video_dir:
            QMessageBox.warning(self, "错误", "请选择文件夹！")
            return
        self.log_area.clear()
        self.run_btn.setEnabled(False)
        self.worker = MatchWorker(video_dir, audio_dir, self.chk_rename.isChecked())
        self.worker.progress_log.connect(self.log_area.append)
        self.worker.finished.connect(lambda s: [self.run_btn.setEnabled(True), QMessageBox.information(self, "报告", s)])
        self.worker.error.connect(lambda e: [self.run_btn.setEnabled(True), self.log_area.append(f"❌ 错误: {e}")])
        self.worker.start()
