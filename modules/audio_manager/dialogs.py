import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFileDialog, QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt, QSize

class ElevenLabsSettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("ElevenLabs API 设置")
        self.setMinimumWidth(400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel("🔑 ElevenLabs API Key:"))
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setText(self.config.get_elevenlabs_api_key())
        layout.addWidget(self.api_key_edit)

        layout.addWidget(QLabel("👤 Voice ID:"))
        self.voice_id_edit = QLineEdit()
        self.voice_id_edit.setText(self.config.get_elevenlabs_voice_id())
        layout.addWidget(self.voice_id_edit)

        layout.addWidget(QLabel("🤖 Model ID:"))
        self.model_id_edit = QLineEdit()
        self.model_id_edit.setText(self.config.get_elevenlabs_model_id())
        layout.addWidget(self.model_id_edit)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def save_settings(self):
        new_key = self.api_key_edit.text().strip()
        voice_id = self.voice_id_edit.text().strip()
        model_id = self.model_id_edit.text().strip()
        
        if not new_key:
            QMessageBox.warning(self, "警告", "API Key 不能为空！")
            return
        
        self.config.set_elevenlabs_api_key(new_key)
        self.config.set_elevenlabs_voice_id(voice_id)
        self.config.set_elevenlabs_model_id(model_id)
        
        QMessageBox.information(self, "成功", "设置已保存。")
        self.accept()

class AudioItemDialog(QDialog):
    """
    用于创建或编辑单个音频生成任务的对话框
    """
    def __init__(self, config, data=None, parent=None, provider="ElevenLabs"):
        super().__init__(parent)
        self.config = config
        self.data = data or {} # {'name': '', 'content': '', 'voice_id': '', 'style': '', 'mode': ''}
        self.provider = provider
        self.setWindowTitle(f"编辑音频任务 ({provider})" if data else f"新建音频任务 ({provider})")
        self.setMinimumWidth(450)
        self.init_ui()

    def init_ui(self):
        self.resize(600, 500)
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Google AI Specific: Mode
        if self.provider == "Google AI (Gemini)":
            from PyQt6.QtWidgets import QComboBox
            g_layout = QHBoxLayout()
            g_layout.addWidget(QLabel("<b>🎤 模式 (Mode):</b>"))
            self.mode_combo = QComboBox()
            self.mode_combo.addItems(["Single-speaker audio", "Multi-speaker audio"])
            current_mode = self.data.get('mode', "Single-speaker audio")
            self.mode_combo.setCurrentText(current_mode)
            g_layout.addWidget(self.mode_combo)
            layout.addLayout(g_layout)
            
            layout.addWidget(QLabel("<b>🎨 风格指令 (Style instructions):</b>"))
            self.style_edit = QLineEdit()
            self.style_edit.setPlaceholderText("例如: Read aloud in a warm and friendly tone:")
            self.style_edit.setText(self.data.get('style', 'Read aloud in a warm and friendly tone: '))
            layout.addWidget(self.style_edit)

        # File Name
        layout.addWidget(QLabel("<b>📄 文件名 (不含后缀):</b>"))
        self.name_edit = QLineEdit()
        self.name_edit.setText(self.data.get('name', ''))
        self.name_edit.setPlaceholderText("例如: 场景1_配音")
        self.name_edit.setStyleSheet("padding: 8px;")
        layout.addWidget(self.name_edit)

        # Content
        layout.addWidget(QLabel("<b>📝 文本内容:</b>"))
        self.content_edit = QTextEdit()
        self.content_edit.setText(self.data.get('content', ''))
        self.content_edit.setPlaceholderText("请输入要合成的文字...")
        self.content_edit.setStyleSheet("line-height: 1.5; padding: 8px;")
        layout.addWidget(self.content_edit)

        # Voice Configuration
        voice_group = QVBoxLayout()
        voice_group.setSpacing(8)
        
        if self.provider == "ElevenLabs":
            v_header = QHBoxLayout()
            v_header.addWidget(QLabel("<b>👤 Voice ID:</b>"))
            v_header.addStretch()
            self.btn_lib = QPushButton("📑 从库中选择")
            self.btn_lib.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_lib.setStyleSheet("""
                QPushButton { padding: 4px 12px; background-color: #e3f2fd; color: #1976d2; border: none; border-radius: 4px; font-weight: bold; }
                QPushButton:hover { background-color: #bbdefb; }
            """)
            self.btn_lib.clicked.connect(self.open_voice_library)
            v_header.addWidget(self.btn_lib)
            voice_group.addLayout(v_header)

            self.voice_id_edit = QLineEdit()
            self.voice_id_edit.setText(self.data.get('voice_id', ''))
            self.voice_id_edit.setPlaceholderText(f"默认: {self.config.get_elevenlabs_voice_id()}")
            self.voice_id_edit.setStyleSheet("padding: 8px;")
            voice_group.addWidget(self.voice_id_edit)
        else:
            # Google AI Voice Selection
            voice_group.addWidget(QLabel("<b>👤 选择声音 (Voice):</b>"))
            self.voice_combo = QComboBox()
            self.voice_combo.setStyleSheet("padding: 5px;")
            
            # Voice List from User (Screenshot 2026-01-17) + Known
            voice_list = [
                # Standard / Common
                "Aoede", "Charon", "Fenrir", "Kore", "Puck", "Zephyr",
                # New / Star / Constellation
                "Achernar", "Achird", "Algenib", "Algieba", "Alnilam", 
                "Autonoe", "Callirrhoe", "Despina", "Enceladus", "Erinome", 
                "Gacrux", "Iapetus", "Laomedeia", "Leda", "Orus", 
                "Pulcherrima", "Rasalgethi", "Sadachbia", "Sadaltager", 
                "Schedar", "Sulafat", "Umbriel", "Vindemiatrix", "Zubenelgenubi",
                # Others previously listed (kept for safety)
                "Callisto", "Dia", "Himalia", "Io", "Jupiter", "Mimas", "Moon", 
                "Oberon", "Phobos", "Rhea", "Telesto", "Titan", "Triton"
            ]
            all_voices = sorted(list(set(voice_list))) # Sort and deduplicate
            
            self.voice_combo.addItems(all_voices)
            
            current_voice = self.data.get('voice_id', '')
            if not current_voice:
                current_voice = self.config._config.get("google_ai_voice_id", "Zephyr")
            
            self.voice_combo.setCurrentText(current_voice)
            voice_group.addWidget(self.voice_combo)
            
        layout.addLayout(voice_group)

        # Buttons
        layout.addSpacing(10)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumHeight(35)
        cancel_btn.setMinimumWidth(80)
        cancel_btn.clicked.connect(self.reject)
        
        ok_btn = QPushButton("确定")
        ok_btn.setMinimumHeight(35)
        ok_btn.setMinimumWidth(100)
        ok_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; border: none; border-radius: 4px;")
        ok_btn.clicked.connect(self.accept_data)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def accept_data(self):
        name = self.name_edit.text().strip()
        content = self.content_edit.toPlainText().strip()
        if self.provider == "ElevenLabs":
            voice_id = self.voice_id_edit.text().strip()
        else:
            voice_id = self.voice_combo.currentText()

        if not content:
            QMessageBox.warning(self, "警告", "内容不能为空！")
            return
        
        if not name:
            # 自动取内容前10个字
            name = content[:10].replace('\n', ' ').strip()
        
        self.result_data = {
            'name': name,
            'content': content,
            'voice_id': voice_id
        }
        
        if self.provider == "Google AI (Gemini)":
            self.result_data['style'] = self.style_edit.text().strip()
            self.result_data['mode'] = self.mode_combo.currentText()
            
        self.accept()

    def get_data(self):
        return self.result_data

    def open_voice_library(self):
        dialog = VoiceSelectionDialog(self.config, self)
        if dialog.exec():
            v_id = dialog.get_selected_id()
            if v_id:
                self.voice_id_edit.setText(v_id)

class VoiceSelectionDialog(QDialog):
    """
    可视化的声音库选择对话框
    """
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.selected_id = None
        self.setWindowTitle("从声音库选择 Voice ID")
        self.setMinimumSize(700, 600)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        info_label = QLabel("📢 请双击选择一个预存的声线：")
        info_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        layout.addWidget(info_label)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["声线名称", "Voice ID", "描述"])
        self.tree.setColumnWidth(0, 260) # Increased width for name + icon
        self.tree.setColumnWidth(1, 150)
        self.tree.setIconSize(QSize(40, 40)) # Larger icon size correctly using QSize
        self.tree.setIndentation(20)
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setStyleSheet("""
            QTreeWidget {
                font-size: 13px;
                border: 1px solid #dcdfe6;
                border-radius: 6px;
                padding: 5px;
            }
            QTreeWidget::item {
                height: 50px; /* Taller rows for images */
                padding: 5px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTreeWidget::item:hover {
                background-color: #ecf5ff;
            }
            QTreeWidget::item:selected {
                background-color: #c6e2ff;
                color: #333;
            }
        """)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.tree)
        
        self.load_data()
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumHeight(40)
        cancel_btn.setMinimumWidth(90)
        cancel_btn.clicked.connect(self.reject)
        
        self.ok_btn = QPushButton("确定选择")
        self.ok_btn.clicked.connect(self.accept_selection)
        self.ok_btn.setMinimumHeight(40)
        self.ok_btn.setMinimumWidth(120)
        self.ok_btn.setStyleSheet("font-weight: bold; background-color: #0078d4; color: white; border-radius: 4px;")
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.ok_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

    def load_data(self):
        library = self.config.get_voice_library()
        for cat in library:
            cat_item = QTreeWidgetItem([cat['category']])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable) # 分类不可选
            
            # Category Icon (Folder style)
            # cat_item.setIcon(0, QIcon("path/to/folder_icon.png")) # Optional
            
            self.tree.addTopLevelItem(cat_item)
            
            for v_data in cat['items']:
                name = v_data['name']
                v_id = v_data['voice_id']
                desc = v_data.get('desc', '')
                img_path = v_data.get('image', '')
                
                item = QTreeWidgetItem([name, v_id, desc])
                item.setData(1, Qt.ItemDataRole.UserRole, v_id)
                
                # Load Image
                if img_path and os.path.exists(img_path):
                    pixmap = QPixmap(img_path)
                    if not pixmap.isNull():
                        # Scale properly
                        icon = QIcon(pixmap)
                        item.setIcon(0, icon)
                
                cat_item.addChild(item)
        
        self.tree.expandAll()

    def on_item_double_clicked(self, item, column):
        if item.childCount() == 0: # 只有子项（具体声音）可以双击
            self.accept_selection()

    def accept_selection(self):
        item = self.tree.currentItem()
        if not item or item.childCount() > 0:
            QMessageBox.warning(self, "提示", "请选择一个具体的声线，而不是分类。")
            return
            
        self.selected_id = item.text(1)
        # Fallback if text is empty (hidden col issues)
        if not self.selected_id:
             self.selected_id = item.data(1, Qt.ItemDataRole.UserRole)
             
        self.accept()

    def get_selected_id(self):
        return self.selected_id

from .services import KeyInfoWorker

class ElevenLabsKeyManagerDialog(QDialog):
    """
    管理多个 ElevenLabs API Key 及其积分
    """
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("ElevenLabs 多 Key 管理器")
        self.setMinimumSize(800, 500)
        self.workers = [] 
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ 添加新 Key")
        btn_add.clicked.connect(self.add_key)
        btn_batch_add = QPushButton("🚀 批量导入 Key")
        btn_batch_add.clicked.connect(self.batch_import_keys)
        btn_refresh = QPushButton("🔄 联网全量刷新")
        btn_refresh.clicked.connect(self.refresh_all_balances)
        
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_batch_add)
        toolbar.addWidget(btn_refresh)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["备注", "API Key (隐写)", "已用积分", "总计限额", "剩余可用", "声线槽位", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 100)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True) # 开启排序
        
        # 美化表格样式
        self.table.alternatingRowColors()
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e0e0e0;
                gridline-color: #f0f0f0;
                font-size: 13px;
                selection-background-color: #e3f2fd;
                selection-color: #333;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #ddd;
                font-weight: bold;
                color: #444;
            }
            QTableWidget::item {
                padding: 5px;
            }
        """)
        
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        btn_delete = QPushButton("🗑️ 删除选中")
        btn_delete.setStyleSheet("QPushButton{ color: white; background-color: #ff4d4f; border-radius: 4px; padding: 5px 15px; font-weight: bold; } QPushButton:hover{ background-color: #ff7875; }")
        btn_delete.clicked.connect(self.delete_selected)
        btn_delete_all = QPushButton("🗑️ 全部删除")
        btn_delete_all.setStyleSheet("QPushButton{ color: white; background-color: #d32f2f; border-radius: 4px; padding: 5px 15px; font-weight: bold; } QPushButton:hover{ background-color: #e57373; }")
        btn_delete_all.clicked.connect(self.delete_all)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_delete)
        btn_layout.addWidget(btn_delete_all)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.load_keys_to_table()

    def load_keys_to_table(self):
        self.table.setSortingEnabled(False) # 加载数据前关闭排序，提高性能
        keys = self.config.get_elevenlabs_keys()
        self.table.setRowCount(0)
        for k_data in keys:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(k_data.get('label', '未命名')))
            
            full_key = k_data.get('key', '')
            masked_key = f"{full_key[:4]}****{full_key[-4:]}" if len(full_key) > 8 else full_key
            key_item = QTableWidgetItem(masked_key)
            key_item.setData(Qt.ItemDataRole.UserRole, full_key) 
            self.table.setItem(row, 1, key_item)
            
            # 显示本地缓存数据 (使用数字类型以支持正确排序)
            used = k_data.get('character_count', 0)
            limit = k_data.get('character_limit', 0)
            remaining = k_data.get('remaining', 0)
            
            # 兼容处理: 如果是 '-' 或 None 则设为 -1 方便排序
            def to_int(val):
                try:
                    return int(val)
                except:
                    return -1

            item_used = QTableWidgetItem()
            item_used.setData(Qt.ItemDataRole.DisplayRole, to_int(used))
            self.table.setItem(row, 2, item_used)

            item_limit = QTableWidgetItem()
            item_limit.setData(Qt.ItemDataRole.DisplayRole, to_int(limit))
            self.table.setItem(row, 3, item_limit)

            item_remaining = QTableWidgetItem()
            item_remaining.setData(Qt.ItemDataRole.DisplayRole, to_int(remaining))
            self.table.setItem(row, 4, item_remaining)

            # 声线槽位 (本地缓存)
            vc = k_data.get('voice_count', -1)
            vl = k_data.get('voice_limit', 3)
            slot_text = f"{vc}/{vl}" if vc >= 0 else "-"
            self.table.setItem(row, 5, QTableWidgetItem(slot_text))

            # 操作按钮: 清空声线 (用 API Key 定位，而非行号，避免排序后错位)
            btn_clear = QPushButton("🧹 清空声线")
            btn_clear.setStyleSheet("QPushButton{ color: white; background-color: #ff9800; border-radius: 3px; padding: 3px 8px; font-size: 12px; } QPushButton:hover{ background-color: #ffb74d; }")
            btn_clear.clicked.connect(lambda checked, k=full_key: self.clear_voices_for_key(k))
            self.table.setCellWidget(row, 6, btn_clear)

        self.table.setSortingEnabled(True) # 加载完成后重新开启排序

    def add_key(self):
        from PyQt6.QtWidgets import QInputDialog
        key, ok = QInputDialog.getText(self, "添加 Key", "请输入 ElevenLabs API Key:")
        if not ok or not key.strip(): return
        
        label, ok = QInputDialog.getText(self, "添加备注", "请输入 Key 备注 (可选):", text="我的 Key")
        if not ok: label = "新 Key"
        
        keys = self.config.get_elevenlabs_keys()
        if any(k['key'] == key.strip() for k in keys):
            QMessageBox.warning(self, "提示", "该 Key 已存在！")
            return
            
        keys.append({'key': key.strip(), 'label': label.strip()})
        self.config.set_elevenlabs_keys(keys)
        self.load_keys_to_table()
        self.refresh_balance_for_key(key.strip())

    def batch_import_keys(self):
        dialog = BatchKeyImportDialog(self)
        if dialog.exec():
            new_keys = dialog.get_data()
            if not new_keys: return
            
            existing_keys = self.config.get_elevenlabs_keys()
            existing_key_values = [k['key'] for k in existing_keys]
            
            added_count = 0
            for k_item in new_keys:
                if k_item['key'] not in existing_key_values:
                    existing_keys.append(k_item)
                    existing_key_values.append(k_item['key'])
                    added_count += 1
            
            if added_count > 0:
                self.config.set_elevenlabs_keys(existing_keys)
                self.load_keys_to_table()
                QMessageBox.information(self, "成功", f"成功导入 {added_count} 个新 Key！")
                self.refresh_all_balances()
            else:
                QMessageBox.information(self, "提示", "未发现新的有效 Key 或 Key 已存在。")

    def _find_row_by_key(self, api_key):
        """根据 API Key 查找当前表格中的实际行号（排序安全）"""
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 1)
            if item and item.data(Qt.ItemDataRole.UserRole) == api_key:
                return r
        return -1

    def refresh_all_balances(self):
        for r in range(self.table.rowCount()):
            full_key = self.table.item(r, 1).data(Qt.ItemDataRole.UserRole)
            self.refresh_balance_for_key(full_key)

    def refresh_balance_for_key(self, api_key):
        """根据 API Key 刷新余额（排序安全）"""
        row = self._find_row_by_key(api_key)
        if row < 0: return
        print(f"[ElevenLabsKeyManagerDialog] 开始查询 Key={api_key[-4:]}")
        self.table.setItem(row, 2, QTableWidgetItem("查询中..."))
        self.table.setItem(row, 3, QTableWidgetItem("-"))
        self.table.setItem(row, 4, QTableWidgetItem("-"))
        
        worker = KeyInfoWorker(api_key)
        worker.info_received.connect(lambda k, info: self.on_info_received(k, info))
        worker.error.connect(lambda k, err: self.on_info_error(k, err))
        worker.finished.connect(lambda w=worker: self.workers.remove(w) if w in self.workers else None)
        self.workers.append(worker)
        worker.start()

    def on_info_received(self, api_key, info):
        """查询成功回调，用 API Key 定位行（排序安全）"""
        row = self._find_row_by_key(api_key)
        if row < 0: return
        print(f"[ElevenLabsKeyManagerDialog] 查询成功 Key={api_key[-4:]}, Used={info['character_count']}, Limit={info['character_limit']}")
        
        self.table.setItem(row, 2, QTableWidgetItem(str(info['character_count'])))
        self.table.setItem(row, 3, QTableWidgetItem(str(info['character_limit'])))
        self.table.setItem(row, 4, QTableWidgetItem(str(info['remaining'])))
        
        # 声线槽位
        vc = info.get('voice_count', -1)
        vl = info.get('voice_limit', 3)
        slot_text = f"{vc}/{vl}" if vc >= 0 else "查询失败"
        slot_item = QTableWidgetItem(slot_text)
        if vc >= vl:
            slot_item.setForeground(Qt.GlobalColor.red)
        self.table.setItem(row, 5, slot_item)
        
        # 更新清空按钮状态
        btn = self.table.cellWidget(row, 6)
        if btn and vc == 0:
            btn.setEnabled(False)
            btn.setText("✅ 已清空")
        elif btn:
            btn.setEnabled(True)
            btn.setText("🧹 清空声线")
        
        # 同步回 ConfigManager
        keys = self.config.get_elevenlabs_keys()
        for k in keys:
            if k['key'] == api_key:
                k['character_count'] = info['character_count']
                k['character_limit'] = info['character_limit']
                k['remaining'] = info['remaining']
                k['voice_count'] = vc
                k['voice_limit'] = vl
                break
        self.config.set_elevenlabs_keys(keys)

    def on_info_error(self, api_key, err):
        """查询失败回调，用 API Key 定位行（排序安全）"""
        row = self._find_row_by_key(api_key)
        if row < 0: return
        print(f"[ElevenLabsKeyManagerDialog] 查询失败 Key={api_key[-4:]}, Error={err}")
        
        self.table.setItem(row, 2, QTableWidgetItem("查询失败"))
        self.table.setItem(row, 3, QTableWidgetItem("查询失败"))
        
        # 在剩余可用列显示错误信息(截断以适应列宽)
        error_display = err[:50] + "..." if len(err) > 50 else err
        error_item = QTableWidgetItem(error_display)
        error_item.setToolTip(err)  # 完整错误信息显示在工具提示中
        self.table.setItem(row, 4, error_item)
        self.table.setItem(row, 5, QTableWidgetItem("查询失败"))

    def delete_selected(self):
        row = self.table.currentRow()
        if row < 0: return
        
        if QMessageBox.question(self, "确认", "确定删除该 Key 吗？") == QMessageBox.StandardButton.Yes:
            full_key = self.table.item(row, 1).data(Qt.ItemDataRole.UserRole)
            keys = self.config.get_elevenlabs_keys()
            new_keys = [k for k in keys if k['key'] != full_key]
            self.config.set_elevenlabs_keys(new_keys)
            self.load_keys_to_table()

    def delete_all(self):
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "提示", "当前没有任何 Key 可删除。")
            return
        
        reply = QMessageBox.warning(
            self, "⚠️ 确认全部删除",
            f"确定要删除全部 {self.table.rowCount()} 个 Key 吗？\n此操作不可撤销！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.set_elevenlabs_keys([])
            self.load_keys_to_table()

    def clear_voices_for_key(self, api_key):
        """清空指定 Key 的所有自定义声线（排序安全）"""
        masked = f"{api_key[:4]}****{api_key[-4:]}" if len(api_key) > 8 else api_key
        
        reply = QMessageBox.question(
            self, "确认清空声线",
            f"确定要清空 Key ({masked}) 下的所有自定义声线吗？\n清空后该 Key 的声线槽位将被释放。"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 禁用按钮并显示进度（实时查找行号）
        row = self._find_row_by_key(api_key)
        if row >= 0:
            btn = self.table.cellWidget(row, 6)
            if btn:
                btn.setEnabled(False)
                btn.setText("⏳ 清空中...")
            self.table.setItem(row, 5, QTableWidgetItem("清空中..."))
        
        from .services import ClearVoicesWorker
        worker = ClearVoicesWorker(api_key)
        worker.finished.connect(lambda ok, msg, k=api_key: self.on_clear_voices_finished(k, ok, msg))
        self.workers.append(worker)
        worker.finished.connect(lambda ok, msg, w=worker: self.workers.remove(w) if w in self.workers else None)
        worker.start()

    def on_clear_voices_finished(self, api_key, success, msg):
        """清空声线完成回调（排序安全）"""
        if success:
            QMessageBox.information(self, "完成", msg)
        else:
            QMessageBox.critical(self, "失败", msg)
        
        # 刷新该 Key 的最新数据
        self.refresh_balance_for_key(api_key)

class VoiceItemDialog(QDialog):
    """
    用于创建或编辑声音库条目的对话框
    """
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self.data = data or {} # {'name': '', 'voice_id': '', 'desc': '', 'image': ''}
        self.setWindowTitle("编辑声音" if data else "添加声音")
        self.setMinimumWidth(400)
        self.asset_dir = os.path.join(os.getcwd(), "resources", "voice_assets")
        if not os.path.exists(self.asset_dir):
            os.makedirs(self.asset_dir)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel("🏷️ 声音名称:"))
        self.name_edit = QLineEdit()
        self.name_edit.setText(self.data.get('name', ''))
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("🆔 Voice ID:"))
        self.id_edit = QLineEdit()
        self.id_edit.setText(self.data.get('voice_id', ''))
        layout.addWidget(self.id_edit)

        layout.addWidget(QLabel("📝 描述/备注:"))
        self.desc_edit = QTextEdit()
        self.desc_edit.setText(self.data.get('desc', ''))
        self.desc_edit.setMaximumHeight(80)
        layout.addWidget(self.desc_edit)

        layout.addWidget(QLabel("🖼️ 图片头像:"))
        img_layout = QHBoxLayout()
        self.img_path_label = QLineEdit()
        self.img_path_label.setReadOnly(True)
        self.img_path_label.setText(self.data.get('image', ''))
        img_layout.addWidget(self.img_path_label)
        
        btn_browse = QPushButton("上传图片")
        btn_browse.clicked.connect(self.browse_image)
        img_layout.addWidget(btn_browse)
        layout.addLayout(img_layout)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("保存")
        ok_btn.clicked.connect(self.save_data)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择头像", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if file_path:
            # 自动备份
            try:
                import uuid
                import shutil
                ext = os.path.splitext(file_path)[1]
                new_name = f"{uuid.uuid4()}{ext}"
                target_path = os.path.normpath(os.path.join(self.asset_dir, new_name))
                shutil.copy2(file_path, target_path)
                # 记录相对路径或完整路径，为了通用稳妥建议记录相对于项目根目录的路径或存到resources
                # 这里我们记录备份后的绝对路径
                self.img_path_label.setText(target_path)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"图片备份失败: {e}")

    def save_data(self):
        name = self.name_edit.text().strip()
        voice_id = self.id_edit.text().strip()
        if not name or not voice_id:
            QMessageBox.warning(self, "警告", "名称和 ID 不能为空！")
            return
        
        self.result_data = {
            'name': name,
            'voice_id': voice_id,
            'desc': self.desc_edit.toPlainText().strip(),
            'image': self.img_path_label.text().strip()
        }
        self.accept()

    def get_data(self):
        return self.result_data

class BatchImportDialog(QDialog):
    """
    音频制作批量导入对话框
    支持格式：文件名 | 文案内容 | VoiceID (可选)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量导入音频任务")
        self.setMinimumSize(700, 500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        info = QLabel("💡 请粘贴数据，支持 Tab 或 竖线(|) 分隔：\n格式: 文件名 | 文案内容 | VoiceID (可选)")
        info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info)
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("第一条任务文件名 | 第一条任务文案 | voice_id_1\n第二条任务文件名 | 第二条任务文案")
        layout.addWidget(self.text_edit)
        
        from PyQt6.QtWidgets import QCheckBox
        self.chk_clear_existing = QCheckBox("导入前清空当前任务列表")
        self.chk_clear_existing.setChecked(True)
        layout.addWidget(self.chk_clear_existing)

        btn_layout = QHBoxLayout()
        self.import_btn = QPushButton("🚀 立即导入")
        self.import_btn.setMinimumHeight(40)
        self.import_btn.setStyleSheet("font-weight: bold; background-color: #2196F3; color: white;")
        self.import_btn.clicked.connect(self.parse_and_accept)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.import_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

    def parse_and_accept(self):
        raw_text = self.text_edit.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "提示", "内容不能为空！")
            return
            
        lines = raw_text.split('\n')
        self.results = []
        for line in lines:
            if not line.strip(): continue
            # 兼容 Tab, Pipe, 逗号
            parts = []
            if '\t' in line: parts = line.split('\t')
            elif '|' in line: parts = line.split('|')
            else: parts = [line] # 只有文案？
            
            parts = [p.strip() for p in parts]
            
            if len(parts) >= 2:
                name = parts[0]
                content = parts[1]
                v_id = parts[2] if len(parts) >= 3 else ""
            else:
                # 只有一列则视为文案，文件名自动生成
                content = parts[0]
                name = content[:10].replace('\n', ' ')
                v_id = ""
                
            self.results.append({'name': name, 'content': content, 'voice_id': v_id})
            
        if not self.results:
            QMessageBox.warning(self, "错误", "未能解析到任何有效任务，请检查格式。")
            return
            
        self.accept()

    def get_data(self):
        return self.results, self.chk_clear_existing.isChecked()

class OnlineVoiceManagerDialog(QDialog):
    """
    云端声线管理，解决 3/3 免费额度问题
    """
    def __init__(self, api_key, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.setWindowTitle(f"ElevenLabs 云端声线管理 ({api_key[-4:]})")
        self.setMinimumSize(600, 400)
        self.init_ui()
        self.refresh_list()

    def init_ui(self):
        layout = QVBoxLayout()
        
        info_label = QLabel("💡 此处仅列出您的“自定义/克隆”声线。\n删除这些声线可以释放您的 3/3 免费额度限制。系统内置声音不统计在内。")
        info_label.setStyleSheet("color: #d32f2f; font-weight: bold;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.status_label = QLabel("正在获取云端列表...")
        layout.addWidget(self.status_label)
        
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["名称", "分类", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self.refresh_list)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

    def refresh_list(self):
        from .services import OnlineVoiceWorker
        self.table.setRowCount(0)
        self.status_label.setText("⌛ 正在同步云端数据...")
        
        self.worker = OnlineVoiceWorker(self.api_key)
        self.worker.voices_received.connect(self.on_voices_loaded)
        self.worker.error.connect(lambda e: QMessageBox.critical(self, "错误", f"获取失败: {e}"))
        self.worker.start()

    def on_voices_loaded(self, voices):
        self.status_label.setText(f"✅ 共发现 {len(voices)} 条声线。")
        self.table.setRowCount(0)
        for v in voices:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(v['name']))
            self.table.setItem(row, 1, QTableWidgetItem(v['category']))
            
            btn_del = QPushButton("🗑️ 删除")
            btn_del.setStyleSheet("color: white; background-color: #f44336; padding: 2px;")
            btn_del.clicked.connect(lambda checked, vid=v['id'], name=v['name']: self.delete_voice(vid, name))
            self.table.setCellWidget(row, 2, btn_del)

    def delete_voice(self, voice_id, voice_name):
        if QMessageBox.question(self, "确认删除", f"确定要永久删除云端声线 '{voice_name}' 吗？\n删除后不可恢复，但可以腾出额度。") == QMessageBox.StandardButton.Yes:
            from .services import DeleteVoiceWorker
            self.status_label.setText(f"⌛ 正在删除 {voice_name}...")
            
            self.del_worker = DeleteVoiceWorker(self.api_key, voice_id)
            self.del_worker.finished.connect(self.on_delete_finished)
            self.del_worker.start()

    def on_delete_finished(self, success, msg):
        if success:
            QMessageBox.information(self, "成功", msg)
            self.refresh_list()
        else:
            QMessageBox.critical(self, "失败", f"删除失败: {msg}")
            self.status_label.setText("❌ 操作失败。")

class BatchKeyImportDialog(QDialog):
    """
    批量导入 API Key 对话框
    格式：
    名字
    Key
    (空行)
    名字
    Key
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量导入 ElevenLabs Keys")
        self.setMinimumSize(500, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        info = QLabel(
            "💡 请按照以下格式粘贴 Key 列表：\n\n"
            "第一行：名字 (备注)\n"
            "第二行：API Key\n"
            "(空行分隔不同 Key)\n\n"
            "示例：\n"
            "我的账号1\n"
            "sk_123456...\n\n"
            "我的账号2\n"
            "sk_abcdef..."
        )
        info.setStyleSheet("color: #666; background-color: #f9f9f9; padding: 10px; border-radius: 5px;")
        layout.addWidget(info)
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("在此粘贴内容...")
        layout.addWidget(self.text_edit)
        
        btn_layout = QHBoxLayout()
        import_btn = QPushButton("🚀 立即导入")
        import_btn.setMinimumHeight(40)
        import_btn.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white;")
        import_btn.clicked.connect(self.parse_and_accept)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(import_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

    def parse_and_accept(self):
        content = self.text_edit.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "提示", "输入内容不能为空！")
            return
            
        # 按照双换行或多换行切分块
        import re
        blocks = re.split(r'\n\s*\n', content)
        
        self.results = []
        for block in blocks:
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            if len(lines) >= 2:
                name = lines[0]
                key = lines[1]
                self.results.append({'label': name, 'key': key})
        
        if not self.results:
            QMessageBox.warning(self, "错误", "未能解析出有效的 Key，请检查格式是否正确。")
            return
            
        self.accept()

    def get_data(self):
        return self.results

class GoogleAISettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Google AI (Gemini) 设置")
        self.setMinimumWidth(400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel("🤖 Model ID:"))
        self.model_id_edit = QLineEdit()
        self.model_id_edit.setText(self.config._config.get("google_ai_model_id", "gemini-2.5-pro-preview-tts"))
        layout.addWidget(self.model_id_edit)

        layout.addWidget(QLabel("👤 Default Voice (e.g., Zephyr, Puck):"))
        self.voice_id_edit = QLineEdit()
        self.voice_id_edit.setText(self.config._config.get("google_ai_voice_id", "Zephyr"))
        layout.addWidget(self.voice_id_edit)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def save_settings(self):
        self.config._config["google_ai_model_id"] = self.model_id_edit.text().strip()
        self.config._config["google_ai_voice_id"] = self.voice_id_edit.text().strip()
        self.config.save_config()
        QMessageBox.information(self, "成功", "设置已保存。")
        self.accept()

class GoogleAIKeyManagerDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Google AI 多 Key 管理器")
        self.setMinimumSize(700, 450)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ 添加新 Key")
        btn_add.clicked.connect(self.add_key)
        toolbar.addWidget(btn_add)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["备注", "API Key (隐写)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        btn_delete = QPushButton("🗑️ 删除选中")
        btn_delete.setStyleSheet("color: red;")
        btn_delete.clicked.connect(self.delete_selected)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_delete)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.load_keys()

    def load_keys(self):
        keys = self.config._config.get("google_ai_keys", [])
        self.table.setRowCount(0)
        for k_data in keys:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(k_data.get('label', '未命名')))
            
            full_key = k_data.get('key', '')
            masked_key = f"{full_key[:4]}****{full_key[-4:]}" if len(full_key) > 8 else full_key
            key_item = QTableWidgetItem(masked_key)
            key_item.setData(Qt.ItemDataRole.UserRole, full_key)
            self.table.setItem(row, 1, key_item)

    def add_key(self):
        from PyQt6.QtWidgets import QInputDialog
        key, ok = QInputDialog.getText(self, "添加 Key", "请输入 Google AI API Key:")
        if not ok or not key.strip(): return
        
        label, ok = QInputDialog.getText(self, "添加备注", "请输入 Key 备注 (可选):", text="Google Key")
        if not ok: label = "新 Key"
        
        keys = self.config._config.get("google_ai_keys", [])
        keys.append({'key': key.strip(), 'label': label.strip()})
        self.config._config["google_ai_keys"] = keys
        self.config.save_config()
        self.load_keys()

    def delete_selected(self):
        row = self.table.currentRow()
        if row < 0: return
        if QMessageBox.question(self, "确认", "确定删除该 Key 吗？") == QMessageBox.StandardButton.Yes:
            full_key = self.table.item(row, 1).data(Qt.ItemDataRole.UserRole)
            keys = self.config._config.get("google_ai_keys", [])
            new_keys = [k for k in keys if k['key'] != full_key]
            self.config._config["google_ai_keys"] = new_keys
            self.config.save_config()
            self.load_keys()

    def get_data(self):
        return self.results
