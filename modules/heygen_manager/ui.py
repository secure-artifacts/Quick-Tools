import os
import time
import asyncio
import threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QGroupBox, QTableWidget, QTableWidgetItem, 
    QHeaderView, QCheckBox, QTextEdit, QFileDialog, QSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from .automation import HeyGenAutomation
from .data_pool import EmailPool, LinkPool
from .session_manager import SessionManager

# --- 1. 异步执行 Worker (单实例执行逻辑) ---
class SingleInstanceWorker(QThread):
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(int, str, str, str) # index, status, url, action
    finished_signal = pyqtSignal(int, str, bool) # index, action_type, success

    def __init__(self, instance_id, email_pool=None, link_pool=None, parent=None):
        super().__init__(parent)
        self.instance_id = instance_id
        self.email_pool = email_pool
        self.link_pool = link_pool
        self.automation = None
        self.loop = None
        self._tasks_queue = None
        
    def run(self):
        try:
            if os.name == 'nt':
                try:
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                except:
                    pass 
            
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            self.automation = HeyGenAutomation(
                instance_id=self.instance_id,
                log_callback=self.emit_log,
                status_callback=self.emit_status
            )

            self.loop.run_forever()
        except Exception as e:
            self.log_signal.emit(f"❌ Worker 线程启动崩溃: {str(e)}")

    def stop_worker(self):
        if self.loop and self.loop.is_running():
            if self.automation:
                asyncio.run_coroutine_threadsafe(self.automation.close(), self.loop)
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.quit()
        self.wait()

    # --- 外部调用接口 (Thread Safe) ---
    def queue_launch(self, headless=False, storage_path=None):
        if self.loop and self.loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._async_launch(headless, storage_path), self.loop)
            future.add_done_callback(lambda f: self._handle_future_exception(f, "Launch"))
        else:
            self.log_signal.emit(f"⚠️ 无法启动: 线程循环未就绪 (ID: {self.instance_id})")

    def queue_action(self, action_type, tasks=None):
        if self.loop and self.loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._async_execute(action_type, tasks), self.loop)
            future.add_done_callback(lambda f: self._handle_future_exception(f, action_type))
        else:
            self.log_signal.emit(f"⚠️ 无法执行 {action_type}: 线程循环未就绪 (ID: {self.instance_id})")
            

    def _handle_future_exception(self, future, context):
        try:
            future.result()
        except Exception as e:
            self.log_signal.emit(f"❌ {context} 任务执行抛出异常: {str(e)}")

    # --- 内部 Async 逻辑 ---
    async def _async_launch(self, headless, storage_path):
        await self.automation.start_browser(headless=headless, storage_state_path=storage_path)

    async def _async_backup(self, session_manager):
        if self.automation and self.automation.context:
            await session_manager.save_session(self.automation.context, self.instance_id)
            self.emit_log(f"💾 实例#{self.instance_id} 会话已备份")
        

    async def _async_execute(self, action_type, tasks):
        try:
            if action_type == "fill_form":
                await self.automation.onboarding_flow()
            
            elif action_type == "batch_login":
                await self._async_batch_login()
            
            
            elif action_type == "monitor":
                self.emit_log("👁️ 开启分钟级监控模式...")
            self.finished_signal.emit(self.instance_id, action_type, True)
        except Exception as e:
            self.emit_log(f"❌ 执行 {action_type} 异常: {str(e)}")
            self.finished_signal.emit(self.instance_id, action_type, False)

    async def _async_batch_login(self):
        """批量登录逻辑: 取邮箱 -> 登录 -> 等待 -> 取链接 -> 完成"""
        self.emit_log("🚀 开始批量登录流程...")
        
        # 1. 获取邮箱
        self.emit_log("📧 正在请求邮箱资源...")
        if not self.email_pool:
            self.emit_log("❌ Email Pool 未初始化")
            return
        
        try:
            if self.email_pool.remaining_count() == 0:
                 self.emit_log("⏳ 邮箱池为空，等待加入...")
            email = await asyncio.wait_for(self.email_pool.get_email(), timeout=300) 
        except asyncio.TimeoutError:
            self.emit_log("⚠️ 等待邮箱超时，任务终止")
            return
        
        self.emit_log(f"✅ 领取邮箱: {email}")
        
        success = await self.automation.login_via_email(email)
        if not success:
            self.emit_log(f"❌ 邮箱登录失败: {email}")
            return
        
        self.emit_log("⏳ 登录请求已发送，等待 10 秒后开始轮询链接...")
        await asyncio.sleep(10)
        
        self.emit_log("🔗 开始轮询获取有效 Magic Link...")
        magic_link = None
        
        end_time = time.time() + 600
        
        while time.time() < end_time:
            if self.link_pool.remaining_count() > 0:
                try:
                    magic_link = await asyncio.wait_for(self.link_pool.get_valid_link(), timeout=5)
                    if magic_link:
                        break
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(2)
        
        if not magic_link:
            self.emit_log("❌ 等待 Magic Link 超时 (10分钟)")
            return
            
        self.emit_log(f"✅ 捕获有效链接: {magic_link[:30]}...")
        
        await self.automation.login_via_magic_link(magic_link)
        self.emit_log("🎉 登录流程完成！")

    def emit_log(self, text):
        self.log_signal.emit(text)

    def emit_status(self, idx, status, url, action):
        self.status_signal.emit(idx, status, url, action)

# --- 2. 主界面组件 ---
class HeyGenManagerUI(QWidget):
    def __init__(self):
        super().__init__()
        self.email_pool = EmailPool()
        self.link_pool = LinkPool()
        self.session_manager = SessionManager()
        self.workers = {} 
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # A. 监控与核心控制 (分段按钮)
        ctrl_box = QGroupBox("🎮 自动化流水线控制")
        ctrl_layout = QVBoxLayout()
        
        # 第一行：启动控制
        launch_layout = QHBoxLayout()
        launch_layout.addWidget(QLabel("并发浏览器数量:"))
        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 10)
        self.spin_count.setValue(1)
        launch_layout.addWidget(self.spin_count)
        
        self.btn_launch = QPushButton("🌐 1. 启动浏览器")
        self.btn_launch.clicked.connect(self.run_launch)
        self.btn_launch.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
        launch_layout.addWidget(self.btn_launch)
        
        # New: Load Backup Checkbox
        self.chk_load_backup = QCheckBox("📂 读取备份")
        self.chk_load_backup.stateChanged.connect(self.on_chk_backup_changed)
        launch_layout.addWidget(self.chk_load_backup)

        # New: Backup Button
        self.btn_backup = QPushButton("💾 备份今日会话")
        self.btn_backup.clicked.connect(self.action_backup_all)
        launch_layout.addWidget(self.btn_backup)

        launch_layout.addStretch()
        ctrl_layout.addLayout(launch_layout)

        # 第二行：分段操作
        action_layout = QHBoxLayout()
        self.btn_fill = QPushButton("📝 2. 自动填单")
        self.btn_fill.clicked.connect(lambda: self.run_phase("fill_form"))
        
        
        self.btn_monitor = QPushButton("👁️ 4. 单次检查")
        self.btn_monitor.clicked.connect(lambda: self.run_phase("monitor"))
        
        action_layout.addWidget(self.btn_fill)
        action_layout.addWidget(self.btn_monitor)
        ctrl_layout.addLayout(action_layout)
        
        # 第三行： 邮箱与链接池管理 (新建)
        pool_box = QGroupBox("🏊 资源池管理 (邮箱 & Magic Link)")
        pool_layout = QHBoxLayout()
        
        # 邮箱池
        self.input_emails = QTextEdit()
        self.input_emails.setPlaceholderText("在此粘贴邮箱列表 (一行一个)...")
        self.input_emails.setMaximumHeight(60)
        btn_add_emails = QPushButton("📥 导入邮箱到池")
        btn_add_emails.clicked.connect(self.action_add_emails)
        
        email_layout = QVBoxLayout()
        email_layout.addWidget(self.input_emails)
        email_layout.addWidget(btn_add_emails)
        pool_layout.addLayout(email_layout, 1)
        
        # 链接池
        self.input_link = QTextEdit()
        self.input_link.setPlaceholderText("在此粘贴 Magic Link (自动提取)...")
        self.input_link.setMaximumHeight(60)
        btn_add_link = QPushButton("🔗 投递链接 (60s有效)")
        btn_add_link.clicked.connect(self.action_add_link)
        
        link_layout = QVBoxLayout()
        link_layout.addWidget(self.input_link)
        link_layout.addWidget(btn_add_link)
        pool_layout.addLayout(link_layout, 1)
        
        # 批量登录按钮
        self.btn_batch_login = QPushButton("🚀 5. 开始批量登录")
        self.btn_batch_login.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; padding: 10px;")
        self.btn_batch_login.clicked.connect(lambda: self.run_phase("batch_login"))
        pool_layout.addWidget(self.btn_batch_login, 0)
        
        pool_box.setLayout(pool_layout)
        ctrl_layout.addWidget(pool_box)
        
        ctrl_box.setLayout(ctrl_layout)
        layout.addWidget(ctrl_box)

        # B. 实例监控列表 (恢复)
        monitor_box = QGroupBox("📊 浏览器运行状态")
        monitor_layout = QVBoxLayout()
        self.table_monitor = QTableWidget(0, 4)
        self.table_monitor.setHorizontalHeaderLabels(["ID", "状态", "当前网址", "最后动作"])
        self.table_monitor.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        monitor_layout.addWidget(self.table_monitor)
        monitor_box.setLayout(monitor_layout)
        layout.addWidget(monitor_box, 1)


        # C. 底部：任务配置与日志
        bottom_layout = QHBoxLayout()
        
        
        # 日志输出
        log_group = QGroupBox("📜 详细执行日志")
        log_vbox = QVBoxLayout()
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas; font-size: 11px;")
        log_vbox.addWidget(self.log_area)
        log_group.setLayout(log_vbox)
        bottom_layout.addWidget(log_group, 1)
        
        layout.addLayout(bottom_layout, 2)

    def log(self, text):
        self.log_area.append(text)
        self.log_area.ensureCursorVisible()

    def update_monitor(self, idx, status, url, action):
        """更新监控表格中的状态"""
        row = -1
        for r in range(self.table_monitor.rowCount()):
            if self.table_monitor.item(r, 0).text() == f"#{idx}":
                row = r; break
        if row == -1:
            row = self.table_monitor.rowCount()
            self.table_monitor.insertRow(row)
            self.table_monitor.setItem(row, 0, QTableWidgetItem(f"#{idx}"))
        
        if status: self.table_monitor.setItem(row, 1, QTableWidgetItem(status))
        if url: self.table_monitor.setItem(row, 2, QTableWidgetItem(url))
        if action: self.table_monitor.setItem(row, 3, QTableWidgetItem(action))



    def action_add_emails(self):
        text = self.input_emails.toPlainText()
        if not text: return
        emails = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Directly call synchronous add method
        self.email_pool.add_emails(emails)
        self.log(f"📥 已将 {len(emails)} 个邮箱加入池中")
        self.input_emails.clear()

    def action_add_link(self):
        text = self.input_link.toPlainText()
        if not text: return
        # 支持一次贴多个吗？假设一次一个，或者按行
        links = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Directly call synchronous add method
        for link in links:
            self.link_pool.add_link(link)
        
        self.log(f"🔗 已投递 {len(links)} 个链接 (60s 过期)")
        self.input_link.clear()

    # --- Backup Logic ---
    def on_chk_backup_changed(self):
        if self.chk_load_backup.isChecked():
            # 1. Check for backups
            date_str = self.session_manager.get_preferred_load_date()
            if not date_str:
                self.log("⚠️ 未找到任何可用备份！")
                self.chk_load_backup.setChecked(False)
                return
            
            # 2. Get files count
            files = self.session_manager.get_session_files(date_str)
            count = len(files)
            if count == 0:
                self.log(f"⚠️ 目录 {date_str} 为空")
                self.chk_load_backup.setChecked(False)
                return
                
            self.log(f"📂 发现备份 ({date_str}): {count} 个实例")
            self.spin_count.setValue(count)
            self.spin_count.setEnabled(False) # Lock input
        else:
            self.spin_count.setEnabled(True)

    def action_backup_all(self):
        if not self.workers:
            self.log("❌ 没有运行中的实例，无法备份")
            return
            
        self.log(f"💾 正在请求 {len(self.workers)} 个实例进行备份...")
        for w in self.workers.values():
            w.queue_backup(self.session_manager)

    def run_launch(self):
        count = self.spin_count.value()
        load_backup = self.chk_load_backup.isChecked()
        backup_files = []
        
        if load_backup:
            date_str = self.session_manager.get_preferred_load_date()
            if date_str:
                backup_files = self.session_manager.get_session_files(date_str)
                self.log(f"📂 模式: 读取备份 ({date_str}) - {len(backup_files)} 文件")
            else:
                self.log("❌ 备份文件读取失败，取消启动")
                return

        self.log(f"🚀 准备开启 {count} 个浏览器实例...")
        self.table_monitor.setRowCount(0)
        
        # Cleanup
        for w in self.workers.values():
            w.stop_worker()
        self.workers = {}

        for i in range(1, count + 1):
            worker = SingleInstanceWorker(i, email_pool=self.email_pool, link_pool=self.link_pool)
            worker.log_signal.connect(self.log)
            worker.status_signal.connect(self.update_monitor)
            worker.finished_signal.connect(self.on_action_finished)
            
            worker.start()
            time.sleep(0.1)
            
            # Determine storage path
            storage_path = None
            if load_backup and i <= len(backup_files):
                # Map worker #1 -> backup_files[0]
                storage_path = backup_files[i-1] 
            
            worker.queue_launch(headless=False, storage_path=storage_path)
            
            self.workers[i] = worker
            self.log(f"Started Worker Thread #{i} (Backup: {os.path.basename(storage_path) if storage_path else 'None'})")

    def run_phase(self, phase_type):
        if not self.workers:
            self.log("⚠️ 请先点击“启动浏览器”！")
            return
        
        tasks = []

        self.log(f"⚡ 向所有 Worker 发送指令: {phase_type}")
        for worker in self.workers.values():
            worker.queue_action(phase_type, tasks)

    def on_action_finished(self, idx, action_type, success):
        self.log(f"🏁 实例#{idx} 的 {action_type} 操作已完成 ({'成功' if success else '失败'})")

    def closeEvent(self, event):
        for w in self.workers.values():
            w.stop_worker()
        super().closeEvent(event)
