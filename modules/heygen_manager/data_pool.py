import asyncio
import time
import queue
from dataclasses import dataclass, field
from typing import Optional


# --- Legacy Pools (Keep for compatibility if needed) ---
class EmailPool:
    def __init__(self):
        self.queue = queue.Queue()
        self.total_added = 0

    def add_emails(self, email_list):
        for email in email_list:
            if email.strip():
                self.queue.put(email.strip())
                self.total_added += 1

    async def get_email(self):
        while True:
            try:
                return self.queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(1)

    def remaining_count(self):
        return self.queue.qsize()

class LinkPool:
    def __init__(self, ttl_seconds=60):
        self.queue = queue.Queue()
        self.ttl = ttl_seconds

    def add_link(self, link):
        if link and link.strip():
            expire_at = time.time() + self.ttl
            self.queue.put((link.strip(), expire_at))

    async def get_valid_link(self):
        while True:
            try:
                link, expire_at = self.queue.get_nowait()
                time_left = expire_at - time.time()
                if time_left > 0:
                    return link
                else:
                    continue
            except queue.Empty:
                await asyncio.sleep(0.5)

    def remaining_count(self):
        return self.queue.qsize()
