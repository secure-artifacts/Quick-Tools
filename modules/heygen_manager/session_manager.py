import os
import json
import asyncio
from datetime import datetime
import glob

class SessionManager:
    def __init__(self, base_dir="modules/heygen_manager/sessions"):
        self.base_dir = base_dir
        
    def _get_date_dir(self, date_str=None):
        """Returns directory path for a specific date (YYYY-MM-DD). Defaults to today."""
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.base_dir, date_str)

    def ensure_date_dir(self, date_str=None):
        path = self._get_date_dir(date_str)
        os.makedirs(path, exist_ok=True)
        return path

    async def save_session(self, context, instance_id):
        """Saves the current browser context state to the daily backup folder."""
        if not context:
            return False
            
        try:
            # Always save to TODAY's folder
            path = self.ensure_date_dir() 
            filename = f"instance_{instance_id}.json"
            full_path = os.path.join(path, filename)
            
            # Playwright storage_state saves cookies and localStorage
            await context.storage_state(path=full_path)
            print(f"💾 Session backup saved: {full_path}")
            return True
        except Exception as e:
            print(f"❌ Failed to save session: {e}")
            return False

    def get_latest_backup_date(self):
        """Finds the most recent date folder that contains session files."""
        if not os.path.exists(self.base_dir):
            return None
            
        subdirs = [d for d in os.listdir(self.base_dir) if os.path.isdir(os.path.join(self.base_dir, d))]
        subdirs.sort(reverse=True)
        
        for date_str in subdirs:
            files = self.get_session_files(date_str)
            if files:
                return date_str
        return None

    def get_session_files(self, date_str):
        """Returns sorted list of session file paths for a given date."""
        path = self._get_date_dir(date_str)
        if not os.path.exists(path):
            return []
            
        files = glob.glob(os.path.join(path, "instance_*.json"))
        
        def extract_id(fpath):
            try:
                base = os.path.basename(fpath)
                return int(base.replace("instance_", "").replace(".json", ""))
            except:
                return 999
        
        files.sort(key=extract_id)
        return files
        
    def get_preferred_load_date(self):
        today = datetime.now().strftime("%Y-%m-%d")
        files = self.get_session_files(today)
        if files:
            return today
        return self.get_latest_backup_date()
