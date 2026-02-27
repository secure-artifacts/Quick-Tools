from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit,
    QAbstractItemView, QMessageBox, QTextEdit, QDialog
)
from PyQt6.QtCore import Qt, QDate
from ...history_manager import HistoryManager

class HistoryDetailDialog(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("历史记录详情")
        self.resize(500, 400)
        layout = QVBoxLayout()
        
        name_label = QLabel(f"<b>文件名:</b> {data.get('name')}")
        name_label.setWordWrap(True)
        layout.addWidget(name_label)
        
        layout.addWidget(QLabel(f"<b>时间:</b> {data.get('timestamp')}"))
        layout.addWidget(QLabel(f"<b>Voice ID:</b> {data.get('voice_id')}"))
        
        status = data.get('status', 'unknown')
        status_text = "✅ 成功" if status == "success" else f"❌ 失败 ({data.get('error_msg')})"
        status_label = QLabel(f"<b>状态:</b> {status_text}")
        status_label.setWordWrap(True)
        layout.addWidget(status_label)
        
        layout.addWidget(QLabel("<b>文案内容:</b>"))
        content_edit = QTextEdit()
        content_edit.setPlainText(data.get('content', ''))
        content_edit.setReadOnly(True)
        layout.addWidget(content_edit)
        
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
        
        self.setLayout(layout)

class HistoryWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.manager = HistoryManager()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # 顶部工具栏
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("📅 按日期查找:"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        top_layout.addWidget(self.date_edit)
        
        btn_search = QPushButton("🔍 搜索")
        btn_search.clicked.connect(self.load_history)
        top_layout.addWidget(btn_search)
        
        btn_show_all = QPushButton("📋 显示全部")
        btn_show_all.clicked.connect(lambda: self.load_history(all_time=True))
        top_layout.addWidget(btn_show_all)
        
        top_layout.addSpacing(10)
        
        self.btn_load_archive = QPushButton("📂 加载存档")
        self.btn_load_archive.clicked.connect(self.load_archive)
        top_layout.addWidget(self.btn_load_archive)
        
        self.btn_home = QPushButton("🏠 返回主库")
        self.btn_home.clicked.connect(self.return_to_main)
        self.btn_home.setVisible(False)
        top_layout.addWidget(self.btn_home)
        
        top_layout.addStretch()
        
        btn_clear = QPushButton("🗑️ 清空当前页记录")
        btn_clear.clicked.connect(self.clear_history)
        btn_clear.setStyleSheet("color: red;")
        top_layout.addWidget(btn_clear)
        
        layout.addLayout(top_layout)

        self.db_label = QLabel("📍 当前数据库: 主库 (history.db)")
        self.db_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.db_label)

        # 表格
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["生成时间", "文件名", "文案摘要", "Voice ID", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.show_detail)
        layout.addWidget(self.table)
        
        layout.addWidget(QLabel("💡 双击行可查看完整文案及错误信息"))

        self.setLayout(layout)
        self.load_history()

    def load_history(self, all_time=False):
        date_str = None if all_time else self.date_edit.date().toString("yyyy-MM-dd")
        records = self.manager.get_records(date_str=date_str, all_time=all_time)
        
        self.table.setRowCount(0)
        for r in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            self.table.setItem(row, 0, QTableWidgetItem(r.get('timestamp', '')))
            self.table.setItem(row, 1, QTableWidgetItem(r.get('name', '')))
            
            content = r.get('content', '')
            short_content = content[:30] + "..." if len(content) > 30 else content
            self.table.setItem(row, 2, QTableWidgetItem(short_content))
            
            self.table.setItem(row, 3, QTableWidgetItem(r.get('voice_id', '')))
            
            status = r.get('status', 'unknown')
            status_item = QTableWidgetItem("✅ 成功" if status == "success" else "❌ 失败")
            if status != "success":
                status_item.setToolTip(r.get('error_msg', ''))
            self.table.setItem(row, 4, status_item)
            
            # 存储原始数据用于详情显示
            for col in range(5):
                item = self.table.item(row, col)
                if item: item.setData(Qt.ItemDataRole.UserRole, r)

    def load_archive(self):
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择历史存档数据库", "", "SQLite Database (history_*.db);;All Files (*)"
        )
        if file_path:
            if self.manager.switch_database(file_path):
                self.btn_home.setVisible(True)
                self.db_label.setText(f"📍 当前数据库: 存档 ({os.path.basename(file_path)})")
                self.load_history(all_time=True)

    def return_to_main(self):
        self.manager.switch_database(None)
        self.btn_home.setVisible(False)
        self.db_label.setText("📍 当前数据库: 主库 (history.db)")
        self.load_history()

    def show_detail(self):
        row = self.table.currentRow()
        if row < 0: return
        data = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        dialog = HistoryDetailDialog(data, self)
        dialog.exec()

    def clear_history(self):
        if QMessageBox.question(self, "确认", "确定清空所有历史记录吗？此操作不可撤销。") == QMessageBox.StandardButton.Yes:
            self.manager.clear_history()
            self.load_history()
