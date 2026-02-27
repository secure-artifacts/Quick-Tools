import os
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QPlainTextEdit, QMessageBox, QLineEdit, QDialog, QGroupBox
)
from .logic import FileManager

class SmartImportDialog(QDialog):
    def __init__(self, parent=None, default_output_dir="", project_manager=None):
        super().__init__(parent)
        self.setWindowTitle("新建项目导入")
        self.resize(600, 500)
        self.output_dir = default_output_dir
        self.project_manager = project_manager
        self.parsed_data = None # (text1, text2, link)
        self.init_ui()

    def init_ui(self):
        # ... (UI setup mostly same, just updating label)
        layout = QVBoxLayout()

        # 1. 粘贴区域
        layout.addWidget(QLabel("1. 请粘贴您的数据 (Text1 - Tab - Text2 - Tab - Link):"))
        self.text_area = QPlainTextEdit()
        self.text_area.setPlaceholderText("在此处粘贴...")
        self.text_area.textChanged.connect(self.on_text_changed)
        layout.addWidget(self.text_area)

        from PyQt6.QtWidgets import QCheckBox
        
        # 2. 预览与命名
        self.preview_group = QGroupBox("2. 项目设置")
        preview_layout = QVBoxLayout()
        
        self.lbl_status = QLabel("等待粘贴...")
        self.lbl_status.setStyleSheet("color: gray;")
        preview_layout.addWidget(self.lbl_status)
        
        self.chk_clean_text = QCheckBox("启用文本自动整理 (去除空行 + 合并小于300字的行)")
        self.chk_clean_text.setChecked(True)
        preview_layout.addWidget(self.chk_clean_text)
        
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("项目名称 (将作为文件夹名):"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("例如: date")
        name_layout.addWidget(self.name_input)
        name_layout.addWidget(self.name_input)
        preview_layout.addLayout(name_layout)

        self.chk_create_folder = QCheckBox("创建同名子文件夹 (勾选后会将文件归档到子目录)")
        self.chk_create_folder.setChecked(False) # User requested no folder by default
        preview_layout.addWidget(self.chk_create_folder)
        
        self.preview_group.setLayout(preview_layout)
        layout.addWidget(self.preview_group)

        # 3. 按钮
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("创建项目并导入")
        self.btn_save.setEnabled(False)
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self.run_import)
        
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def on_text_changed(self):
        text = self.text_area.toPlainText()
        self.parsed_data = FileManager.parse_input_batch(text)
        
        count = len(self.parsed_data)
        if count > 0:
            t1, t2, link = self.parsed_data[0]
            self.lbl_status.setText(f"✅ 已识别 {count} 条数据!\n预览第一条:\n文本1: {t1[:10]}...\n链接: {link[:20]}...")
            self.lbl_status.setStyleSheet("color: green;")
            self.btn_save.setEnabled(True)
            self.btn_save.setText(f"创建项目并导入 ({count} 个文件)")
        else:
            self.lbl_status.setText("❌ 未识别到有效数据，请检查格式。")
            self.lbl_status.setStyleSheet("color: red;")
            self.btn_save.setEnabled(False)
            self.btn_save.setText("创建项目并导入")

    def run_import(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入项目名称！")
            return

        if not self.output_dir:
            QMessageBox.warning(self, "提示", "未设置全局输出目录！")
            return
            
        if not self.parsed_data:
            return

        # 创建子文件夹
        if self.chk_create_folder.isChecked():
            project_dir = os.path.join(self.output_dir, name)
        else:
            project_dir = self.output_dir
            
        try:
            os.makedirs(project_dir, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法创建/访问文件夹: {e}")
            return

        # 开始处理
        try:
            # 准备数据
            final_data = self.parsed_data
            if self.chk_clean_text.isChecked():
                cleaned_list = []
                for (t1, t2, url) in self.parsed_data:
                    c1 = FileManager.clean_and_merge_text(t1)
                    c2 = FileManager.clean_and_merge_text(t2)
                    cleaned_list.append((c1, c2, url))
                final_data = cleaned_list
            
            # 1. 保存 TXT 到项目文件夹
            txt_path = os.path.join(project_dir, f"{name}.txt")
            saved, save_msg = FileManager.save_batch_text(final_data, txt_path)
            
            if not saved:
                QMessageBox.critical(self, "错误", f"无法保存文本文件: {save_msg}")
                return

            # 2. 批量下载
            QMessageBox.information(self, "开始下载", f"正在项目文件夹 '{name}' 中创建文件...\n即将下载 {len(final_data)} 个文件。")
            
            success_count = 0
            fail_list = []
            
            for i, (t1, t2, url) in enumerate(final_data, 1):
                # 如果不是 Google Drive 链接，则跳过下载，只保留文本 (文本已在上面保存)
                # 视为成功处理
                if 'drive.google.com' not in url.lower():
                    success_count += 1
                    continue

                # 文件名：基础名 + 序号
                current_base_name = f"{name}{i}"
                full_save_path_base = os.path.join(project_dir, current_base_name)
                
                ok, msg = FileManager.download_file(url, full_save_path_base)
                if ok:
                    success_count += 1
                else:
                    fail_list.append(f"#{i}: {msg}")

            # 注册项目
            if self.project_manager:
                self.project_manager.add_project(name)

            # 3. 结果汇总
            if len(fail_list) == 0:
                QMessageBox.information(self, "成功", f"项目 '{name}' 创建成功！\n共处理 {success_count} 条数据。")
                self.accept()
            else:
                fail_msg = "\n".join(fail_list[:5])
                QMessageBox.warning(self, "部分完成", f"成功: {success_count}\n失败: {len(fail_list)}\n\n失败详情:\n{fail_msg}")
                self.accept()
                
        except Exception as e:
            QMessageBox.critical(self, "异常", str(e))
                
        except Exception as e:
            QMessageBox.critical(self, "异常", str(e))
