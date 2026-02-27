import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QFileDialog, QMessageBox, QAbstractItemView, QLineEdit, QTabWidget,
    QCheckBox, QComboBox, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QStyleOptionButton, QStyle
)
from PyQt6.QtCore import Qt, QEventLoop, QTimer, QRect, pyqtSignal

from ..services import ElevenLabsWorker, GoogleAIWorker, KeyInfoWorker
from ..dialogs import (
    ElevenLabsSettingsDialog, AudioItemDialog, ElevenLabsKeyManagerDialog, 
    BatchImportDialog, OnlineVoiceManagerDialog,
    GoogleAISettingsDialog, GoogleAIKeyManagerDialog
)
from ...history_manager import HistoryManager
from .voice_vault_widget import VoiceLibraryWidget

class CheckBoxHeader(QHeaderView):
    """
    带复选框的表头，仅第一列显示
    """
    toggled = pyqtSignal(bool)

    def __init__(self, orientation, parent=None):
        super(CheckBoxHeader, self).__init__(orientation, parent)
        self.isOn = False 

    def set_checked(self, checked):
        if self.isOn != checked:
            self.isOn = checked
            self.viewport().update()

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()
        super(CheckBoxHeader, self).paintSection(painter, rect, logicalIndex)
        painter.restore()

        if logicalIndex == 0:
            option = QStyleOptionButton()
            option.rect = QRect(rect.left() + 10, rect.top() + (rect.height() - 15) // 2, 15, 15)
            option.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Active
            if self.isOn:
                option.state |= QStyle.StateFlag.State_On
            else:
                option.state |= QStyle.StateFlag.State_Off
            self.style().drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorCheckBox, option, painter)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            x = self.logicalIndexAt(event.pos())
            if x == 0:
                self.isOn = not self.isOn
                self.viewport().update()
                self.toggled.emit(self.isOn)
                return # Consume the event
        super(CheckBoxHeader, self).mousePressEvent(event)

class AudioGenerateWidget(QWidget):
    SUB_FOLDER_NAME = "生成音频"
    def __init__(self, config, provider=None):
        super().__init__()
        self.config = config
        self.key_info_workers = [] # 存储 Worker 引用，防止被垃圾回收
        self.fixed_provider = provider
        self.current_provider = provider if provider else "ElevenLabs" # Default provider
        self.init_ui()
        if self.config:
            self.load_tasks()
            # If sub folders for different providers are needed in future, change here. 
            # Currently sharing "生成音频" but potentially different files.
            self.update_default_path(self.config.get_global_output_dir())

    def init_ui(self):
        layout = QVBoxLayout()
        
        # --- Top Row 1: Settings & Tools (Moved to Top) ---
        row2_layout = QHBoxLayout()
        row2_layout.setContentsMargins(0, 5, 0, 5) # Add some spacing
        
        # Left side: Platform & Keys
        if not self.fixed_provider:
             row2_layout.addWidget(QLabel("🚀 平台:"))
             self.provider_combo = QComboBox()
             self.provider_combo.addItems(["ElevenLabs", "Google AI (Gemini)"])
             row2_layout.addWidget(self.provider_combo)
        else:
             row2_layout.addWidget(QLabel(f"🚀 平台: {self.fixed_provider}"))
             
        row2_layout.addWidget(QLabel("🔑 Key:"))
        self.key_combo = QComboBox()
        self.key_combo.setMinimumWidth(200) # Give it some width
        self.refresh_key_combo()
        row2_layout.addWidget(self.key_combo)
        
        row2_layout.addStretch()
        
        # Right side: Tools
        online_voice_btn = QPushButton("☁️ 云端声线")
        online_voice_btn.clicked.connect(self.open_online_voice_manager)
        row2_layout.addWidget(online_voice_btn)
        
        vault_btn = QPushButton("📑 声音 ID 库")
        vault_btn.clicked.connect(self.open_voice_vault)
        row2_layout.addWidget(vault_btn)
        
        settings_btn = QPushButton("⚙️ 管理 Key")
        settings_btn.clicked.connect(self.open_settings)
        row2_layout.addWidget(settings_btn)

        global_settings_btn = QPushButton("🛠️ 全局设置")
        global_settings_btn.clicked.connect(self.open_global_settings)
        row2_layout.addWidget(global_settings_btn)

        layout.addLayout(row2_layout)

        # --- Top Row 2: Task Management (Moved Lower) ---
        row1_layout = QHBoxLayout()
        
        # Left side: Creation
        row1_layout.addWidget(QLabel("📝 任务操作:"))
        btn_add = QPushButton("➕ 新建任务")
        btn_add.clicked.connect(self.add_new_item)
        row1_layout.addWidget(btn_add)
        
        btn_batch = QPushButton("🚀 批量导入")
        btn_batch.clicked.connect(self.batch_import_tasks)
        row1_layout.addWidget(btn_batch)
        
        row1_layout.addStretch()
        
        # Right side: Selection & Cleanup
        # (Select All/None buttons removed, moved to header)
        
        btn_delete = QPushButton("🗑️ 删除选中")
        btn_delete.clicked.connect(self.delete_selected_items)
        row1_layout.addWidget(btn_delete)
        
        btn_clear = QPushButton("🧹 清空列表")
        btn_clear.clicked.connect(self.clear_list)
        row1_layout.addWidget(btn_clear)
        
        layout.addLayout(row1_layout)

        # 任务列表表格
        self.table = QTableWidget(0, 4)
        
        # Set custom header
        self.header_checkbox = CheckBoxHeader(Qt.Orientation.Horizontal, self.table)
        self.header_checkbox.toggled.connect(self.set_all_checked)
        self.table.setHorizontalHeader(self.header_checkbox)

        self.table.setHorizontalHeaderLabels(["", "文件名", "文案内容", "Voice ID (空则默认)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 40)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.edit_item)
        layout.addWidget(self.table)

        # 输出目录设置
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("输出目录:"))
        self.out_edit = QLineEdit()
        self.update_default_path(self.config.get_global_output_dir())
        out_layout.addWidget(self.out_edit)
        out_btn = QPushButton("浏览...")
        out_btn.clicked.connect(self.select_output_dir)
        out_layout.addWidget(out_btn)
        layout.addLayout(out_layout)

        # 批处理高级设置
        adv_settings = QHBoxLayout()
        self.chk_clear_out = QCheckBox("🚧 生成前清空输出文件夹 (慎选)")
        adv_settings.addWidget(self.chk_clear_out)
        
        self.chk_auto_voice = QCheckBox("🌌 自动管理云端声线 (动态释放 3/3 额度)")
        self.chk_auto_voice.setChecked(True)
        adv_settings.addWidget(self.chk_auto_voice)
        
        adv_settings.addStretch()
        
        adv_settings.addWidget(QLabel("📚 发音字典 ID (可选):"))
        self.dict_id_edit = QLineEdit()
        self.dict_id_edit.setPlaceholderText("填入字典 ID...")
        self.dict_id_edit.setFixedWidth(150)
        adv_settings.addWidget(self.dict_id_edit)
        layout.addLayout(adv_settings)

        # 运行按钮
        self.run_btn = QPushButton("🎤 开始批量生成音频 (ElevenLabs)")
        self.run_btn.setMinimumHeight(45)
        self.run_btn.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white;")
        self.run_btn.clicked.connect(self.toggle_generation)
        layout.addWidget(self.run_btn)

        # 日志区域
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(150)
        layout.addWidget(self.log_area)
        
        self.setLayout(layout)

        # Connect signal after UI initialization to prevent crash on startup
        if not self.fixed_provider and hasattr(self, 'provider_combo'):
            self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        elif self.fixed_provider:
            # Manually trigger updates for fixed provider startup state
             self.refresh_key_combo()
             if self.fixed_provider == "ElevenLabs":
                self.run_btn.setText("🎤 开始批量生成音频 (ElevenLabs)")
                self.run_btn.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white;")
             else:
                self.run_btn.setText("🎤 开始批量生成音频 (Google AI)")
                self.run_btn.setStyleSheet("font-weight: bold; background-color: #4285F4; color: white;")

    def update_default_path(self, global_path):
        if global_path:
            full_path = os.path.normpath(os.path.join(global_path, self.SUB_FOLDER_NAME))
            self.out_edit.setText(full_path)
        else:
            self.out_edit.setText("")

    def select_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d: self.out_edit.setText(d)

    def open_settings(self):
        provider = self.current_provider
        if provider == "ElevenLabs":
            dialog = ElevenLabsKeyManagerDialog(self.config, self)
        else:
            dialog = GoogleAIKeyManagerDialog(self.config, self)
        dialog.exec()
        self.refresh_key_combo()

    def open_global_settings(self):
        provider = self.current_provider
        if provider == "ElevenLabs":
            dialog = ElevenLabsSettingsDialog(self.config, self)
        else:
            dialog = GoogleAISettingsDialog(self.config, self)
        dialog.exec()

    def open_voice_vault(self):
        if not hasattr(self, 'vault_win') or self.vault_win is None:
            self.vault_win = VoiceLibraryWidget(self.config)
        
        if self.vault_win.isHidden():
            self.vault_win.show()
        else:
            self.vault_win.activateWindow()
            self.vault_win.raise_()

    def on_provider_changed(self, provider):
        # Save tasks for the previous provider before switching contexts
        if hasattr(self, 'current_provider'):
             self.save_all_tasks() # Saves to self.current_provider (OLD)
        
        self.current_provider = provider
        
        # Load tasks for the new provider
        self.load_tasks()

        self.refresh_key_combo()
        if provider == "ElevenLabs":
            self.run_btn.setText("🎤 开始批量生成音频 (ElevenLabs)")
            self.run_btn.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white;")
        else:
            self.run_btn.setText("🎤 开始批量生成音频 (Google AI)")
            self.run_btn.setStyleSheet("font-weight: bold; background-color: #4285F4; color: white;")

    def refresh_key_combo(self):
        self.key_combo.clear()
        provider = self.current_provider
        if provider == "ElevenLabs":
            self.key_combo.addItem("✨ 智能自动分配 (推荐)", "auto")
            keys = self.config.get_elevenlabs_keys()
            for k in keys:
                label = k.get('label', '未命名')
                key = k.get('key', '')
                display = f"👤 {label} ({key[-4:] if len(key)>4 else key})"
                self.key_combo.addItem(display, key)
            if not keys:
                self.key_combo.setItemText(0, "⚠️ 请先添加 Key")
        else:
            self.key_info_workers = [] # Clear workers if any
            self.key_combo.addItem("✨ 智能自动分配", "auto")
            keys = self.config.get_google_ai_keys()
            for k in keys:
                label = k.get('label', '未命名')
                key = k.get('key', '')
                display = f"👤 {label} ({key[-4:] if len(key)>4 else key})"
                self.key_combo.addItem(display, key)
            if not keys:
                self.key_combo.setItemText(0, "⚠️ 请先添加 Google Key")

    def open_online_voice_manager(self):
        provider = self.current_provider
        if provider != "ElevenLabs":
            QMessageBox.information(self, "提示", "目前仅支持 ElevenLabs 的声线管理。")
            return

        key = self.key_combo.currentData()
        if key == "auto":
            keys = self.config.get_elevenlabs_keys()
            if not keys:
                QMessageBox.warning(self, "提示", "请先在“管理 Key”中添加至少一个 Key！")
                return
            key = keys[0]['key']
        
        dialog = OnlineVoiceManagerDialog(key, self)
        dialog.exec()

    def add_new_item(self):
        dialog = AudioItemDialog(self.config, parent=self, provider=self.current_provider)
        if dialog.exec():
            data = dialog.get_data()
            self.insert_row(self.table.rowCount(), data)
            self.save_all_tasks()

    def batch_import_tasks(self):
        dialog = BatchImportDialog(self)
        if dialog.exec():
            tasks, clear_existing = dialog.get_data()
            if clear_existing:
                self.table.setRowCount(0)
            
            for t in tasks:
                self.insert_row(self.table.rowCount(), t)
            self.save_all_tasks()

    def insert_row(self, row, data, is_checked=True):
        self.table.insertRow(row)
        
        chk_container = QWidget()
        chk_layout = QHBoxLayout(chk_container)
        chk = QCheckBox()
        chk.setChecked(is_checked)
        chk.stateChanged.connect(lambda: self.save_all_tasks())
        chk_layout.addWidget(chk)
        chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chk_layout.setContentsMargins(0, 0, 0, 0)
        self.table.setCellWidget(row, 0, chk_container)

        name_item = QTableWidgetItem(data.get('name', ''))
        # Store full data in Name item to persist hidden fields like 'style', 'mode'
        name_item.setData(Qt.ItemDataRole.UserRole, data)
        self.table.setItem(row, 1, name_item)

        content = data.get('content', '')
        short_content = content[:20] + "..." if len(content) > 20 else content
        item_content = QTableWidgetItem(short_content)
        item_content.setData(Qt.ItemDataRole.UserRole, content) # 存原文
        self.table.setItem(row, 2, item_content)
        self.table.setItem(row, 3, QTableWidgetItem(data.get('voice_id', '')))

    def load_tasks(self):
        provider = getattr(self, 'current_provider', "ElevenLabs")
        tasks = self.config.get_audio_tasks(provider)
        self.table.setRowCount(0)
        for t in tasks:
            self.insert_row(self.table.rowCount(), t, is_checked=t.get('checked', True))
        
        # Sync header checkbox state
        if tasks:
            all_checked = all(t.get('checked', True) for t in tasks)
            self.header_checkbox.set_checked(all_checked)
        else:
            self.header_checkbox.set_checked(False)

    def save_all_tasks(self):
        tasks = []
        for r in range(self.table.rowCount()):
            chk_container = self.table.cellWidget(r, 0)
            checked = True
            if chk_container:
                chk = chk_container.findChild(QCheckBox)
                if chk: checked = chk.isChecked()
            
            # Retrieve original data to preserve hidden fields
            original_data = self.table.item(r, 1).data(Qt.ItemDataRole.UserRole) or {}
            
            item_name = self.table.item(r, 1).text()
            item_content_obj = self.table.item(r, 2)
            full_content = item_content_obj.data(Qt.ItemDataRole.UserRole) if item_content_obj else ""
            if not full_content and item_content_obj:
                full_content = item_content_obj.text()
            
            # Update original data with current table values
            task_data = original_data.copy()
            task_data.update({
                'name': item_name,
                'content': full_content,
                'voice_id': self.table.item(r, 3).text(),
                'checked': checked
            })
            tasks.append(task_data)
        provider = getattr(self, 'current_provider', "ElevenLabs")
        self.config.set_audio_tasks(tasks, provider)

    def set_all_checked(self, checked):
        for r in range(self.table.rowCount()):
            chk_container = self.table.cellWidget(r, 0)
            if chk_container:
                chk = chk_container.findChild(QCheckBox)
                if chk: chk.setChecked(checked)
        self.header_checkbox.set_checked(checked)
        self.save_all_tasks()

    def _on_item_success(self, worker_idx):
        if hasattr(self, 'process_mapping') and worker_idx in self.process_mapping:
            row = self.process_mapping[worker_idx]
            chk_container = self.table.cellWidget(row, 0)
            if chk_container:
                chk = chk_container.findChild(QCheckBox)
                if chk: 
                    chk.setChecked(False)
                    self.save_all_tasks()

    def _on_item_result(self, worker_idx, success, error_msg):
        """
        Record generation history
        """
        if hasattr(self, 'current_batch_tasks') and worker_idx < len(self.current_batch_tasks):
            task = self.current_batch_tasks[worker_idx]
            status = "success" if success else "failed"
            HistoryManager().add_record(
                name=task.get('name', 'unknown'),
                content=task.get('content', ''),
                voice_id=task.get('voice_id', ''),
                status=status,
                error_msg=error_msg
            )
            # Find the history widget in the parent tabs and refresh it
            from .history_widget import HistoryWidget
            parent = self.parentWidget()
            while parent and not isinstance(parent, QTabWidget):
                parent = parent.parentWidget()
            if parent:
                for i in range(parent.count()):
                    w = parent.widget(i)
                    if isinstance(w, HistoryWidget):
                        w.load_history()
                        break

    def edit_item(self):
        row = self.table.currentRow()
        if row < 0: return
        
        # Get full data from Name item
        data = self.table.item(row, 1).data(Qt.ItemDataRole.UserRole)
        if not data:
            # Fallback reconstruction if data missing
            data = {
                'name': self.table.item(row, 1).text(),
                'content': self.table.item(row, 2).data(Qt.ItemDataRole.UserRole) or self.table.item(row, 2).text(),
                'voice_id': self.table.item(row, 3).text()
            }
        
        # Update displayed values in case they were edited manually (though set to NoEditTriggers)
        # Actually, double click triggers this, so manual edit isn't possible directly.
        
        dialog = AudioItemDialog(self.config, data=data, parent=self, provider=self.current_provider)
        if dialog.exec():
            new_data = dialog.get_data()
            
            # Update Table Items and Hidden Data
            name_item = self.table.item(row, 1)
            name_item.setText(new_data['name'])
            name_item.setData(Qt.ItemDataRole.UserRole, new_data) # Update hidden full data
            
            self.table.item(row, 2).setText(new_data['content'][:20] + "...")
            self.table.item(row, 2).setData(Qt.ItemDataRole.UserRole, new_data['content'])
            self.table.item(row, 3).setText(new_data['voice_id'])
            
            self.save_all_tasks()

    def delete_selected_items(self):
        rows_to_delete = []
        for r in range(self.table.rowCount()):
            chk_container = self.table.cellWidget(r, 0)
            if chk_container:
                chk = chk_container.findChild(QCheckBox)
                if chk and chk.isChecked():
                    rows_to_delete.append(r)
        
        if not rows_to_delete:
            rows_to_delete = sorted(list(set(index.row() for index in self.table.selectedIndexes())), reverse=True)
        else:
            rows_to_delete.sort(reverse=True)

        if not rows_to_delete:
            return

        for r in rows_to_delete:
            self.table.removeRow(r)
        
        self.save_all_tasks()

    def clear_list(self):
        if self.table.rowCount() > 0:
            if QMessageBox.question(self, "确认", "确定清空所有任务吗？") == QMessageBox.StandardButton.Yes:
                self.table.setRowCount(0)
                self.save_all_tasks()

    def toggle_generation(self):
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            self.stop_generation()
        else:
            self.run_generation()

    def stop_generation(self):
        self._is_stopping = True
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            self.log_area.append("🛑 正在请求停止生成，请稍候...")
            self.worker.requestInterruption()
        
        if hasattr(self, '_loop') and self._loop and self._loop.isRunning():
            self.log_area.append("🛑 正在请求停止，同步完成后将不再进行生成任务...")
            # We don't call self._loop.quit() here to allow existing sync workers to finish 
            # as requested ("等待积分同步完成"), but do_scheduling_and_run will check the flag.
        
        self.run_btn.setEnabled(False)
        self.run_btn.setText("⏳ 正在停止...")

    def run_generation(self):
        self._is_stopping = False
        selected_mode = self.key_combo.currentData()
        provider = self.current_provider
        
        keys_data = []
        if provider == "ElevenLabs":
            keys_data = self.config.get_elevenlabs_keys()
            if not keys_data:
                QMessageBox.warning(self, "错误", "请先在“管理 Key”中添加至少一个 ElevenLabs API Key！")
                return
        else:
            keys_data = self.config.get_google_ai_keys()
            if not keys_data:
                QMessageBox.warning(self, "错误", "请先添加 Google AI API Key！")
                return
            
        row_count = self.table.rowCount()
        if row_count == 0:
            QMessageBox.warning(self, "提示", "列表中没有任务！")
            return

        tasks = []
        self.process_mapping = {} # worker_index -> table_row

        for r in range(row_count):
            chk_container = self.table.cellWidget(r, 0)
            if chk_container:
                chk = chk_container.findChild(QCheckBox)
                if chk and chk.isChecked():
                    worker_idx = len(tasks)
                    self.process_mapping[worker_idx] = r
                    
                    # Retrieve full data to get 'style', 'mode'
                    original_data = self.table.item(r, 1).data(Qt.ItemDataRole.UserRole) or {}
                    
                    item_name = self.table.item(r, 1).text()
                    item_content_obj = self.table.item(r, 2)
                    full_content = item_content_obj.data(Qt.ItemDataRole.UserRole) if item_content_obj else ""
                    if not full_content and item_content_obj:
                        full_content = item_content_obj.text()
                    
                    task_obj = original_data.copy()
                    task_obj.update({
                        'name': item_name,
                        'content': full_content,
                        'voice_id': self.table.item(r, 3).text(),
                        'length': len(full_content)
                    })
                    tasks.append(task_obj)
        
        if not tasks:
            QMessageBox.warning(self, "提示", "请先勾选要处理的任务！")
            return

        # Check for large tasks constraint
        large_tasks = [t for t in tasks if t['length'] > 3000]
        if large_tasks:
            # If there are large tasks, we only allow SINGLE execution (len(tasks) == 1)
            # The user requested: "if > 3000 chars ... separate generation, separate generation definition is only one task"
            if len(tasks) > 1:
                names = ", ".join([t['name'] for t in large_tasks[:3]])
                if len(large_tasks) > 3: names += "..."
                QMessageBox.warning(self, "批量生成限制", 
                    f"检测到以下任务文本量超过 3000 字符：\n{names}\n\n"
                    "为保证生成稳定性，大文本任务禁止批量生成。\n"
                    "请取消勾选其他任务，仅保留**一个**大文本任务单独运行。")
                return

        output_dir = self.out_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "错误", "请指定输出目录！")
            return
            
        self.log_area.append("🚀 正在启动生成任务，请稍候...")
        self.log_area.repaint() # Force update UI
            
        if provider == "ElevenLabs":
            self.update_run_button_state(True)
            self.log_area.append("🔄 正在联网同步 Key 余额...")
            self.process_scheduling(tasks, selected_mode, keys_data, output_dir)
        else:
            self.log_area.append("🔄 正在准备 Google AI 生成任务...")
            allocated = []
            for i, task in enumerate(tasks):
                t = task.copy()
                if selected_mode == "auto":
                    t['api_key'] = keys_data[i % len(keys_data)]['key']
                else:
                    t['api_key'] = selected_mode
                allocated.append(t)
            self.do_scheduling_and_run(allocated, selected_mode, output_dir, keys_data)

    def process_scheduling(self, tasks, selected_mode, keys_data, output_dir):
        from ..services import KeyInfoWorker
        
        self.balance_results = {} # key: remaining
        self.pending_balance_count = len(keys_data)
        
        if self.pending_balance_count == 0:
            self.log_area.append("⚠️ 未检测到有效 Key。")
            self.run_btn.setEnabled(True)
            return

        self._loop = QEventLoop()
        self.key_info_workers.clear()
        
        for k_item in keys_data:
            key = k_item['key']
            worker = KeyInfoWorker(key)
            worker.info_received.connect(self._on_balance_sync_success)
            worker.error.connect(self._on_balance_sync_error)
            self.key_info_workers.append(worker)
            worker.start()
        
        QTimer.singleShot(10000, self._loop.quit)
        self._loop.exec()

        if self._is_stopping:
            self.log_area.append("🛑 积分同步已完成/结束，后续生成任务已取消。")
            self.update_run_button_state(False)
            return

        self.do_scheduling_and_run(tasks, selected_mode, output_dir, keys_data)

    def update_run_button_state(self, running=True):
        provider = self.current_provider
        if running:
            self.run_btn.setText(f"🛑 停止生成 ({provider})")
            self.run_btn.setStyleSheet("font-weight: bold; background-color: #f44336; color: white;")
        else:
            if provider == "ElevenLabs":
                self.run_btn.setText("🎤 开始批量生成音频 (ElevenLabs)")
                self.run_btn.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white;")
            else:
                self.run_btn.setText("🎤 开始批量生成音频 (Google AI)")
                self.run_btn.setStyleSheet("font-weight: bold; background-color: #4285F4; color: white;")
            self.run_btn.setEnabled(True)

    def do_scheduling_and_run(self, tasks, selected_mode, output_dir, keys_data):
        if self._is_stopping:
            self.update_run_button_state(False)
            return
            
        provider = self.current_provider
        allocated_tasks = []
        unallocated_names = []

        if provider == "ElevenLabs":
            allocated_tasks, unallocated_names = self.schedule_algorithm(tasks, selected_mode, self.balance_results)
            if unallocated_names:
                summary = f"📊 调度完成报告：\n- 成功分配: {len(allocated_tasks)} 个任务\n- 积分不足无法分配: {len(unallocated_names)} 个\n"
                ret = QMessageBox.warning(self, "积分不足", summary + "\n\n是否继续生成已成功分配的任务？", 
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if ret == QMessageBox.StandardButton.No:
                    self.run_btn.setEnabled(True)
                    return
        else:
            allocated_tasks = tasks

        if not allocated_tasks:
            self.update_run_button_state(False)
            return

        self.update_run_button_state(True)
        clear_out = self.chk_clear_out.isChecked()

        if provider == "ElevenLabs":
            model_id = self.config.get_elevenlabs_model_id()
            default_voice_id = self.config.get_elevenlabs_voice_id()
            dict_id = self.dict_id_edit.text().strip() or None
            auto_voice = self.chk_auto_voice.isChecked()
            all_keys = [k['key'] for k in keys_data]
            self.worker = ElevenLabsWorker(allocated_tasks, output_dir, 
                                           all_keys_pool=all_keys,
                                           model_id=model_id, 
                                           default_voice_id=default_voice_id,
                                           clear_output=clear_out,
                                           dict_id=dict_id,
                                           auto_manage_voices=auto_voice)
        else:
            model_id = self.config._config.get("google_ai_model_id", "gemini-2.5-flash-preview-tts")
            default_voice_id = self.config._config.get("google_ai_voice_id", "Zephyr")
            all_keys = [k['key'] for k in keys_data]
            self.worker = GoogleAIWorker(allocated_tasks, output_dir,
                                         all_keys_pool=all_keys,
                                         model_id=model_id,
                                         default_voice_id=default_voice_id,
                                         clear_output=clear_out)
            
        self.worker.item_finished.connect(self._on_item_success)
        self.worker.item_result.connect(self._on_item_result)
        self.current_batch_tasks = allocated_tasks
        self.worker.progress_log.connect(self.log_area.append)
        
        def on_finished(msg):
            self.update_run_button_state(False)
            QMessageBox.information(self, "完成", msg)
            if provider == "ElevenLabs":
                self.auto_sync_used_keys(allocated_tasks)

        self.worker.finished.connect(on_finished)
        self.worker.error.connect(lambda e: [self.update_run_button_state(False), self.log_area.append(f"❌ 错误: {e}")])
        self.worker.start()

    def auto_sync_used_keys(self, allocated_tasks):
        used_keys = list(set(t['api_key'] for t in allocated_tasks if t.get('api_key')))
        if not used_keys: return
        self.log_area.append(f"📡 任务结束，正在后台静默同步 {len(used_keys)} 个已用 Key 的余额...")
        for key in used_keys:
            worker = KeyInfoWorker(key)
            worker.info_received.connect(self._update_local_key_cache)
            self.key_info_workers.append(worker)
            worker.start()

    def _update_local_key_cache(self, key, info):
        keys = self.config.get_elevenlabs_keys()
        changed = False
        for k in keys:
            if k['key'] == key:
                k['character_count'] = info['character_count']
                k['character_limit'] = info['character_limit']
                k['remaining'] = info['remaining']
                changed = True
                break
        if changed:
            self.config.set_elevenlabs_keys(keys)
            self.log_area.append(f"✅ 后台同步完成: Key {key[-4:]} 剩余 {info['remaining']}")

    def _on_balance_sync_success(self, key, info):
        self.balance_results[key] = info['remaining']
        self.log_area.append(f"✅ Key {key[-4:]} 余额同步成功: {info['remaining']} 字符")
        self.pending_balance_count -= 1
        if self.pending_balance_count <= 0: self._loop.quit()

    def _on_balance_sync_error(self, key, err):
        self.balance_results[key] = 0
        self.log_area.append(f"⚠️ 无法获取 Key {key[-4:]} 的余额: {err}")
        self.pending_balance_count -= 1
        if self.pending_balance_count <= 0: self._loop.quit()

    def schedule_algorithm(self, tasks, selected_mode, balance_map):
        if selected_mode != "auto":
            key_pool = {selected_mode: balance_map.get(selected_mode, 0)}
            self.log_area.append(f"⚙️ 已选择特定 Key ({selected_mode[-4:]}) 进行生成。")
        else:
            key_pool = balance_map.copy()
            self.log_area.append("✨ 智能自动分配模式已启用。")

        key_pool = {k: v for k, v in key_pool.items() if v > 0}
        if not key_pool:
            self.log_area.append("❌ 所有可用 Key 余额均为 0，无法分配任务。")
            return [], [t['name'] for t in tasks]

        sorted_tasks = sorted(tasks, key=lambda x: x['length'], reverse=True)
        allocated = []
        unallocated_names = []
        
        for t in sorted_tasks:
            eligible_keys = [(k, bal) for k, bal in key_pool.items() if bal >= t['length']]
            if not eligible_keys:
                unallocated_names.append(t['name'])
                self.log_area.append(f"🚫 任务 '{t['name']}' ({t['length']}字) 无法分配，所有 Key 余额不足。")
                continue
            best_key, _ = min(eligible_keys, key=lambda x: x[1])
            key_pool[best_key] -= t['length']
            t_copy = t.copy()
            t_copy['api_key'] = best_key
            allocated.append(t_copy)
            self.log_area.append(f"✅ 任务 '{t['name']}' ({t['length']}字) 分配给 Key {best_key[-4:]}。")
            
        return allocated, unallocated_names
