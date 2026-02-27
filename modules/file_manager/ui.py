import os
import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QMessageBox, QLineEdit, QSplitter, QListWidget, QListView, 
    QAbstractItemView, QFileDialog
)
from PyQt6.QtCore import Qt, QDir, QSize
from PyQt6.QtGui import QAction, QFileSystemModel
from modules.config_manager import ConfigManager
from .dialogs import SmartImportDialog
from .data import ProjectManager

class FileManagerUI(QWidget):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.current_root = self.config.get_global_output_dir()
        self.project_manager = ProjectManager(self.current_root)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # 1. 顶部工具栏 (路径显示 + 导入按钮)
        top_bar = QHBoxLayout()
        
        top_bar.addWidget(QLabel("当前路径:"))
        self.path_label = QLineEdit()
        self.path_label.setReadOnly(True)
        self.path_label.setText(self.current_root if self.current_root else "未设置")
        top_bar.addWidget(self.path_label)
        
        btn_import = QPushButton("➕ 新建导入 (Import)")
        btn_import.setStyleSheet("background-color: #0078d7; color: white; font-weight: bold; padding: 5px 15px;")
        btn_import.clicked.connect(self.open_import_dialog)
        top_bar.addWidget(btn_import)
        
        main_layout.addLayout(top_bar)
        
        # 2. 主体区域 (左右拆分)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # === 左侧：项目列表 ===
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("📦 项目列表"))
        self.project_list = QListWidget()
        self.project_list.itemClicked.connect(self.on_project_selected)
        left_layout.addWidget(self.project_list)
        left_widget.setLayout(left_layout)
        
        # === 右侧：文件浏览器 (原生体验) ===
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        
        # 右侧工具栏
        r_toolbar = QHBoxLayout()
        self.lbl_current_project = QLabel("请选择左侧项目")
        self.lbl_current_project.setStyleSheet("font-weight: bold; font-size: 14px;")
        r_toolbar.addWidget(self.lbl_current_project)
        
        r_toolbar.addStretch()
        
        self.btn_view_mode = QPushButton("切换视图 (列表/大图)")
        self.btn_view_mode.clicked.connect(self.toggle_view_mode)
        self.btn_view_mode.setEnabled(False)
        r_toolbar.addWidget(self.btn_view_mode)
        
        self.btn_open_folder = QPushButton("📂 打开文件夹")
        self.btn_open_folder.clicked.connect(self.open_current_folder)
        self.btn_open_folder.setEnabled(False)
        r_toolbar.addWidget(self.btn_open_folder)
        
        right_layout.addLayout(r_toolbar)
        
        # 文件列表 (QListView + QFileSystemModel)
        self.file_model = QFileSystemModel()
        # 设置只读，防止误删，如果需要文件操作可以开启
        self.file_model.setReadOnly(False) 
        
        self.file_list = QListView()
        self.file_list.setModel(self.file_model)
        
        # 启用拖拽
        self.file_list.setDragEnabled(True)
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        # self.file_list.setAcceptDrops(True) # 如果需要支持把文件拖进来，开启这个
        
        # 双击打开
        self.file_list.doubleClicked.connect(self.on_file_double_click)
        
        right_layout.addWidget(self.file_list)
        right_widget.setLayout(right_layout)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 3) 
        
        main_layout.addWidget(splitter)
        
        self.setLayout(main_layout)
        
        # 初始化状态
        self.current_project_path = None
        self.refresh_projects()

    def update_default_path(self, path):
        """主程序调用：更新根目录"""
        self.current_root = path
        self.path_label.setText(path if path else "未设置 (请在全局设置中选择)")
        self.project_manager.set_root_dir(path)
        self.refresh_projects()
        
        # 重置右侧
        self.lbl_current_project.setText("请选择左侧项目")
        self.file_list.setRootIndex(self.file_model.index("")) # Reset
        self.current_project_path = None
        self.btn_view_mode.setEnabled(False)
        self.btn_open_folder.setEnabled(False)

    def refresh_projects(self):
        self.project_list.clear()
        if not self.current_root:
            self.project_list.addItem("⚠️ 请先设置全局路径")
            return
            
        projects = self.project_manager.get_projects()
        for p in projects:
            self.project_list.addItem(p["name"])

    def on_project_selected(self, item):
        name = item.text()
        if name.startswith("⚠️"):
            return
            
        # Try folder mode first
        path = self.project_manager.get_project_path(name)
        
        if path and os.path.exists(path) and os.path.isdir(path):
            self.lbl_current_project.setText(f"📂 项目: {name}")
            self.current_project_path = path
            
            # Show all files in the subfolder
            self.file_model.setNameFilters([]) 
            
            # Set model root path
            root_index = self.file_model.setRootPath(path)
            self.file_list.setRootIndex(root_index)
            
            self.btn_view_mode.setEnabled(True)
            self.btn_open_folder.setEnabled(True)
        elif self.current_root and os.path.exists(self.current_root):
            # Flat mode: Filter files in root by project name prefix
            self.lbl_current_project.setText(f"📄 项目: {name} (根目录筛选)")
            self.current_project_path = self.current_root
            
            # Apply filter
            self.file_model.setNameFilters([f"{name}*"])
            self.file_model.setNameFilterDisables(False) # Hide non-matching
            
            root_index = self.file_model.setRootPath(self.current_root)
            self.file_list.setRootIndex(root_index)
            
            self.btn_view_mode.setEnabled(True)
            self.btn_open_folder.setEnabled(True)
        else:
            self.lbl_current_project.setText(f"❌ 路径不存在: {name}")
            self.btn_view_mode.setEnabled(False)
            self.btn_open_folder.setEnabled(False)

    def toggle_view_mode(self):
        if self.file_list.viewMode() == QListView.ViewMode.ListMode:
            self.file_list.setViewMode(QListView.ViewMode.IconMode)
            self.file_list.setIconSize(QSize(100, 100)) # 大图
            self.file_list.setGridSize(QSize(120, 120))
            self.file_list.setResizeMode(QListView.ResizeMode.Adjust)
        else:
            self.file_list.setViewMode(QListView.ViewMode.ListMode)
            self.file_list.setIconSize(QSize(16, 16)) # 小图

    def open_current_folder(self):
        if self.current_project_path and os.path.exists(self.current_project_path):
            os.startfile(self.current_project_path)

    def on_file_double_click(self, index):
        file_path = self.file_model.filePath(index)
        if file_path and os.path.exists(file_path):
            if os.path.isdir(file_path):
                # 如果是文件夹，进入 (虽然我们是扁平设计，但为了通用性)
                self.file_list.setRootIndex(index)
            else:
                os.startfile(file_path)

    def open_import_dialog(self):
        # ... (Same as before)
        path = self.current_root
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "提示", "请先在上方【全局设置】中选择一个有效的输出保存路径！")
            return
    
        dialog = SmartImportDialog(self, default_output_dir=path, project_manager=self.project_manager)
        if dialog.exec():
            self.refresh_projects()
