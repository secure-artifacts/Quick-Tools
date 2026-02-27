import os
import requests
import re
from urllib.parse import urlparse

class FileManager:
    @staticmethod
    def parse_input_batch(text):
        """
        解析输入文本（支持多行）。
        使用 CSV 模块处理 Excel 复制的复杂情况（如单元格内换行、引号包裹等）。
        返回: list of (text1, text2, link)
        """
        text = text.strip()
        if not text:
            return []
            
        import csv
        import io
        
        results = []
        try:
            # 使用制表符作为分隔符，这是 Excel/Sheets 复制的标准格式
            # io.StringIO 让字符串像文件一样被读取
            f = io.StringIO(text)
            reader = csv.reader(f, delimiter='\t')
            
            for parts in reader:
                # 过滤空的列
                clean_parts = [p.strip() for p in parts if p.strip()]
                
                # 如果分列少于3列，尝试处理非标准情况 (可能是空格分隔)
                if len(clean_parts) < 3 and len(parts) > 0:
                    # 尝试把原始行用空格分一下看看 (针对非表格复制的情况)
                    # csv reader 已经处理了引号，所以我们这里重新组合一下再分有点多余
                    # 但为了兼容之前的"宽松正则"，我们可以把这一行重新当作 raw text 处理
                    raw_line = " ".join(parts) 
                    fallback_item = FileManager._parse_single_line_fallback(raw_line)
                    if fallback_item:
                        results.append(fallback_item)
                    continue

                if len(clean_parts) >= 3:
                    link = None
                    text_parts = []
                    
                    for p in clean_parts:
                        # csv 模块已经自动去除了引号，所有我们只需要查找链接
                        
                        # 检查链接 (移除可能存在的空白字符干扰)
                        potential_link = p.replace(' ', '').replace('\n', '').replace('\r', '')
                 
                        if not link and (potential_link.lower().startswith('http') or 
                                         'drive.google.com' in potential_link.lower()):
                            link = potential_link
                        else:
                            text_parts.append(p) # 保持原样文本
                    
                    if link and len(text_parts) >= 2:
                        # 找到链接和至少两个文本
                        results.append((text_parts[0], text_parts[1], link))
                        
        except Exception as e:
            FileManager.log_error(f"CSV Parse Error: {e}")
            
        return results

    @staticmethod
    def _parse_single_line_fallback(text):
        """
        后备解析逻辑：针对非标准制表符分隔的一行文本
        """
        # 尝试宽松正则分割 (空格)
        url_match = re.search(r'(https?://[^\s]+)', text.replace(' ', ''))
        parts = []
        if url_match:
            parts = re.split(r'\s{2,}', text)
        else:
            return None
            
        parts = [p.strip() for p in parts if p.strip()]
        
        if len(parts) >= 3:
            # 简化的查找逻辑
            link = None
            text_parts = []
            for p in parts:
                clean = p.replace('"', '') # 简单去引号
                if not link and ('http' in clean.lower() or 'drive.google.com' in clean.lower()):
                    link = clean
                else:
                    text_parts.append(clean)
                    
            if link and len(text_parts) >= 2:
                return text_parts[0], text_parts[1], link
        return None

    @staticmethod
    def save_batch_text(items, output_file_path):
        """
        保存批量数据到单个 TXT 文件。
        格式：
        1
        Text1
        ------------------------------ (30个-)
        Text2
        ============================== (30个=)
        """
        try:
            os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
            
            content_list = []
            for i, (t1, t2, link) in enumerate(items, 1):
                # 格式构造
                entry = f"{i}\n{t1}\n{'-' * 30}\n{t2}\n{'=' * 30}"
                content_list.append(entry)
            
            # 所有记录用换行连接
            full_content = "\n\n".join(content_list)
            
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            return True, "文件保存成功"
        except Exception as e:
            error = f"保存 TXT 失败: {str(e)}"
            FileManager.log_error(error)
            return False, error

    @staticmethod
    def clean_and_merge_text(text, threshold=300):
        """
        整理文本：
        1. 去除空行
        2. 如果行字数少于 threshold，则向下合并
        3. 合并时添加空格（优化英文）
        """
        if not text:
            return ""
            
        # 1. 拆分并去除空行
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not lines:
            return ""
            
        merged_lines = []
        current_buffer = lines[0]
        
        for i in range(1, len(lines)):
            next_line = lines[i]
            
            # 2. 检查是否需要合并
            if len(current_buffer) < threshold:
                # 合并！添加空格
                current_buffer += " " + next_line
            else:
                # 不需要合并，保存当前行，开始新的一行
                merged_lines.append(current_buffer)
                current_buffer = next_line
                
        # 保存最后一行
        merged_lines.append(current_buffer)
        
        return "\n".join(merged_lines)

    @staticmethod
    def get_google_drive_id(url):
        """
        从 Google Drive 链接中提取 File ID
        支持 formats:
        - https://drive.google.com/file/d/FILE_ID/view...
        - https://drive.google.com/open?id=FILE_ID
        """
        patterns = [
            r'/file/d/([a-zA-Z0-9_-]+)',
            r'id=([a-zA-Z0-9_-]+)'
        ]
        
        for p in patterns:
            match = re.search(p, url)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def download_file(url, save_path_base):
        """
        下载文件。尝试自动识别 Google Drive 链接。
        save_path_base: 这里是文件名（不含扩展名），需要检测内容类型后添加扩展名。
        返回: (success, final_path_or_error)
        """
        try:
            # 1. 处理 Google Drive 链接
            file_id = FileManager.get_google_drive_id(url)
            download_url = url
            
            if file_id:
                # 转换为直接下载链接
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            
            # 2. 发起请求
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            
            # 3. 确定扩展名
            content_type = response.headers.get('content-type', '')
            ext = '.bin' # 默认
            if 'image/jpeg' in content_type:
                ext = '.jpg'
            elif 'image/png' in content_type:
                ext = '.png'
            elif 'application/pdf' in content_type:
                ext = '.pdf'
            else:
                # 尝试从 Content-Disposition 获取文件名
                if "Content-Disposition" in response.headers:
                    from email.message import EmailMessage
                    msg = EmailMessage()
                    msg['content-disposition'] = response.headers["Content-Disposition"]
                    filename = msg.get_filename()
                    if filename:
                        _, ext = os.path.splitext(filename)
            
            final_path = f"{save_path_base}{ext}"
            
            # 4. 保存文件
            with open(final_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            return True, final_path
            
        except Exception as e:
            return False, str(e)
