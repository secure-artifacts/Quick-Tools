import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QFileDialog, QListWidget, QAbstractItemView, QMessageBox,
    QSplitter, QTableWidget, QTableWidgetItem, QApplication
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from ..dialogs import VoiceItemDialog

class VoiceLibraryWidget(QWidget):
    """
    分层级的声音 ID 库界面 (现改为悬浮窗)
    """
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("🎤 层级声音 ID 库 (看板模式)")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint) # 默认可以置顶，方便观看
        self.resize(800, 600)
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 使用 QSplitter 分割分类和内容
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e0e0e0;
                width: 1px;
            }
        """)
        
        # 左侧：分类列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)
        
        cat_header = QLabel("📂 声音分类")
        cat_header.setStyleSheet("font-weight: bold; color: #555; margin-bottom: 5px;")
        left_layout.addWidget(cat_header)
        
        self.category_list = QListWidget()
        self.category_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: #fafafa;
                padding: 5px;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 5px;
                margin-bottom: 2px;
            }
            QListWidget::item:hover {
                background-color: #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
        """)
        self.category_list.currentRowChanged.connect(self.load_category_items)
        left_layout.addWidget(self.category_list)
        
        cat_btn_layout = QHBoxLayout()
        btn_add_cat = QPushButton("新建")
        btn_rename_cat = QPushButton("重命名")
        btn_del_cat = QPushButton("删除")
        
        # Style category buttons
        for btn in [btn_add_cat, btn_rename_cat, btn_del_cat]:
            btn.setStyleSheet("""
                QPushButton {
                    padding: 5px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: white;
                }
                QPushButton:hover {
                    background-color: #f5f5f5;
                }
            """)
        
        btn_add_cat.clicked.connect(self.add_category)
        btn_rename_cat.clicked.connect(self.rename_category)
        btn_del_cat.clicked.connect(self.delete_category)
        cat_btn_layout.addWidget(btn_add_cat)
        cat_btn_layout.addWidget(btn_rename_cat)
        cat_btn_layout.addWidget(btn_del_cat)
        left_layout.addLayout(cat_btn_layout)
        
        # 右侧：条目列表与预览
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)
        
        top_bar = QHBoxLayout()
        self.current_cat_label = QLabel("未选择分类")
        self.current_cat_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #333;")
        top_bar.addWidget(self.current_cat_label)
        top_bar.addStretch()
        
        self.btn_add_voice = QPushButton("➕ 添加声音条目")
        self.btn_add_voice.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.btn_add_voice.clicked.connect(self.add_voice_item)
        self.btn_add_voice.setEnabled(False)
        top_bar.addWidget(self.btn_add_voice)
        right_layout.addLayout(top_bar)
        
        # 使用 QTableWidget 展示，带图片预览
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["预览", "名称", "Voice ID", "描述", "操作"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.edit_voice_item)
        self.table.setColumnWidth(0, 80) # 预览列宽度稍大
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 120)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 8px;
                gridline-color: transparent;
                background-color: white;
            }
            QTableWidget::item {
                padding: 5px;
                border-bottom: 1px solid #f0f0f0;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #0078d4;
                font-weight: bold;
                color: #555;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #000;
            }
        """)
        right_layout.addWidget(self.table)
        
        btn_del_item = QPushButton("🗑️ 删除选中条目")
        btn_del_item.setStyleSheet("""
            QPushButton {
                background-color: #fff1f0;
                color: #ff4d4f;
                border: 1px solid #ffccc7;
                border-radius: 6px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ffccc7;
            }
        """)
        btn_del_item.clicked.connect(self.delete_voice_item)
        right_layout.addWidget(btn_del_item)
        
        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(right_widget)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 4)
        
        layout.addWidget(self.splitter)
        self.setLayout(layout)
        
        self.refresh_categories()

    def refresh_categories(self):
        self.category_list.clear()
        library = self.config.get_voice_library()
        for cat_data in library:
            self.category_list.addItem(cat_data['category'])

    def add_category(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "新建分类", "请输入分类名称:")
        if ok and name.strip():
            library = self.config.get_voice_library()
            if any(c['category'] == name.strip() for c in library):
                QMessageBox.warning(self, "提示", "分类已存在！")
                return
            library.append({'category': name.strip(), 'items': []})
            self.config.set_voice_library(library)
            self.refresh_categories()

    def rename_category(self):
        row = self.category_list.currentRow()
        if row < 0: return
        cat_name = self.category_list.item(row).text()
        
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self, "重命名分类", "请输入新的分类名称:", text=cat_name)
        if ok and new_name.strip() and new_name.strip() != cat_name:
            library = self.config.get_voice_library()
            if any(c['category'] == new_name.strip() for c in library):
                QMessageBox.warning(self, "提示", "该分类名称已存在！")
                return
            
            for cat in library:
                if cat['category'] == cat_name:
                    cat['category'] = new_name.strip()
                    break
            self.config.set_voice_library(library)
            self.refresh_categories()

    def delete_category(self):
        row = self.category_list.currentRow()
        if row < 0: return
        cat_name = self.category_list.item(row).text()
        if QMessageBox.question(self, "确认", f"确定删除分类 '{cat_name}' 及其下所有声音吗？") == QMessageBox.StandardButton.Yes:
            library = self.config.get_voice_library()
            library = [c for c in library if c['category'] != cat_name]
            self.config.set_voice_library(library)
            self.refresh_categories()

    def load_category_items(self, row):
        if row < 0:
            self.table.setRowCount(0)
            self.current_cat_label.setText("未选择分类")
            self.btn_add_voice.setEnabled(False)
            return
        
        cat_name = self.category_list.item(row).text()
        self.current_cat_label.setText(f"📂 {cat_name}")
        self.btn_add_voice.setEnabled(True)
        
        library = self.config.get_voice_library()
        cat_data = next((c for c in library if c['category'] == cat_name), None)
        
        self.table.setRowCount(0)
        self.table.verticalHeader().setDefaultSectionSize(70) # 进一步增加行高以适应更大的图片
        
        if cat_data:
            for item in cat_data['items']:
                self.insert_table_row(self.table.rowCount(), item)

    def insert_table_row(self, row, data):
        self.table.insertRow(row)
        
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if data.get('image') and os.path.exists(data['image']):
            pix = QPixmap(data['image']).scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            img_label.setPixmap(pix)
        else:
            img_label.setText("无图")
        self.table.setCellWidget(row, 0, img_label)
        
        self.table.setItem(row, 1, QTableWidgetItem(data['name']))
        self.table.setItem(row, 2, QTableWidgetItem(data['voice_id']))
        self.table.setItem(row, 3, QTableWidgetItem(data['desc']))
        
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(5, 5, 5, 5)
        action_layout.setSpacing(8)
        
        btn_copy = QPushButton("复制 ID")
        btn_copy.clicked.connect(lambda: self.copy_id(data['voice_id']))
        btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #e6f7ff;
                color: #1890ff;
                border: 1px solid #91d5ff;
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #91d5ff;
                color: white;
            }
        """)
        
        btn_edit = QPushButton("编辑")
        btn_edit.clicked.connect(self.edit_voice_item)
        btn_edit.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #555;
                border: 1px solid #d9d9d9;
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
        """)
        
        action_layout.addWidget(btn_copy)
        action_layout.addWidget(btn_edit)
        action_layout.addStretch()
        self.table.setCellWidget(row, 4, action_widget)

    def copy_id(self, voice_id):
        clipboard = QApplication.clipboard()
        clipboard.setText(voice_id)
        QMessageBox.information(self, "成功", f"Voice ID 已复制到剪贴板！\n{voice_id}")

    def add_voice_item(self):
        dialog = VoiceItemDialog(parent=self)
        if dialog.exec():
            new_data = dialog.get_data()
            cat_name = self.category_list.currentItem().text()
            library = self.config.get_voice_library()
            for cat in library:
                if cat['category'] == cat_name:
                    cat['items'].append(new_data)
                    break
            self.config.set_voice_library(library)
            self.load_category_items(self.category_list.currentRow())

    def edit_voice_item(self):
        row = self.table.currentRow()
        if row < 0: return
        cat_row = self.category_list.currentRow()
        cat_name = self.category_list.item(cat_row).text()
        
        library = self.config.get_voice_library()
        cat_data = next((c for c in library if c['category'] == cat_name), None)
        item_data = cat_data['items'][row]
        
        dialog = VoiceItemDialog(data=item_data, parent=self)
        if dialog.exec():
            new_data = dialog.get_data()
            cat_data['items'][row] = new_data
            self.config.set_voice_library(library)
            self.load_category_items(cat_row)

    def delete_voice_item(self):
        row = self.table.currentRow()
        if row < 0: return
        if QMessageBox.question(self, "确认", "确定删除该声音条目吗？") == QMessageBox.StandardButton.Yes:
            cat_row = self.category_list.currentRow()
            cat_name = self.category_list.item(cat_row).text()
            library = self.config.get_voice_library()
            for cat in library:
                if cat['category'] == cat_name:
                    cat['items'].pop(row)
                    break
            self.config.set_voice_library(library)
            self.load_category_items(cat_row)
