import os
import sqlite3
from datetime import datetime

DEFAULT_DB = "history.db"
MAX_DB_SIZE_MB = 10 # 超过 10MB 就切库

class HistoryManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HistoryManager, cls).__new__(cls)
            cls._instance.current_db_path = DEFAULT_DB
            cls._init_db(DEFAULT_DB)
        return cls._instance

    @staticmethod
    def _init_db(db_path):
        """初始化数据库表结构"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                date TEXT,
                name TEXT,
                content TEXT,
                voice_id TEXT,
                status TEXT,
                error_msg TEXT
            )
        ''')
        # 为日期增加索引，提高查找效率
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON records(date)')
        conn.commit()
        conn.close()

    def _check_rotation(self):
        """检查数据库大小并执行轮转"""
        # 只有在主库时才自动轮转，打开存档库时不轮转
        if self.current_db_path != DEFAULT_DB:
            return

        if not os.path.exists(DEFAULT_DB):
            return

        size_mb = os.path.getsize(DEFAULT_DB) / (1024 * 1024)
        if size_mb >= MAX_DB_SIZE_MB:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_path = f"history_{timestamp}.db"
            try:
                # 尝试关闭所有连接（如果有的话，但在我们的单例逻辑中通常是短连接）
                # 重命名
                os.rename(DEFAULT_DB, archive_path)
                # 重新初始化主库
                self._init_db(DEFAULT_DB)
                print(f"Database rotated: {DEFAULT_DB} -> {archive_path}")
            except Exception as e:
                print(f"Error rotating database: {e}")

    def add_record(self, name, content, voice_id, status, error_msg=""):
        """
        添加新记录，添加前检查轮转
        """
        self._check_rotation()
        
        # 始终写入主库，除非正在显式使用某个库（单例状态下 add 通常写主库）
        # 但为了稳健，我们这里固定写 DEFAULT_DB
        db_to_write = DEFAULT_DB
        
        try:
            conn = sqlite3.connect(db_to_write)
            cursor = conn.cursor()
            now = datetime.now()
            cursor.execute('''
                INSERT INTO records (timestamp, date, name, content, voice_id, status, error_msg)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                now.strftime("%Y-%m-%d %H:%M:%S"),
                now.strftime("%Y-%m-%d"),
                name,
                content,
                voice_id,
                status,
                error_msg
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error adding record to DB: {e}")

    def get_records(self, date_str=None, all_time=False, db_path=None):
        """
        查询记录
        db_path: 若指定则从该库查，否则从当前 active 库查
        """
        target_db = db_path or self.current_db_path
        if not os.path.exists(target_db):
            return []

        try:
            conn = sqlite3.connect(target_db)
            conn.row_factory = sqlite3.Row # 使返回结果可以通过列名访问
            cursor = conn.cursor()
            
            if all_time:
                cursor.execute('SELECT * FROM records ORDER BY id DESC')
            elif date_str:
                cursor.execute('SELECT * FROM records WHERE date = ? ORDER BY id DESC', (date_str,))
            else:
                cursor.execute('SELECT * FROM records ORDER BY id DESC LIMIT 500')
            
            rows = cursor.fetchall()
            # 转换为 dict 列表保持兼容性
            results = [dict(row) for row in rows]
            conn.close()
            return results
        except Exception as e:
            print(f"Error querying DB: {e}")
            return []

    def switch_database(self, db_path):
        """切换当前查阅的数据库"""
        if db_path and os.path.exists(db_path):
            self.current_db_path = db_path
            return True
        elif db_path is None: # 切回主库
            self.current_db_path = DEFAULT_DB
            return True
        return False

    def clear_history(self, db_path=None):
        target_db = db_path or self.current_db_path
        try:
            conn = sqlite3.connect(target_db)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM records')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error clearing DB: {e}")
