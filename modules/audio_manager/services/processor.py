import os
import subprocess
import tempfile
import wave
import numpy as np
import imageio_ffmpeg
from PyQt6.QtCore import QThread, pyqtSignal

# 尝试导入 MoviePy
try:
    from moviepy.editor import AudioFileClip
except ImportError:
    from moviepy.audio.io.AudioFileClip import AudioFileClip

class AudioUtils:
    @staticmethod
    def get_audio_info(file_path):
        if not os.path.exists(file_path): return None
        try:
            audio = AudioFileClip(file_path)
            info = {
                "channels": getattr(audio, 'nchannels', 2),
                "frame_rate": audio.fps,
                "duration_seconds": audio.duration,
            }
            audio.close()
            return info
        except:
            return None

class AudioSplitter:
    @staticmethod
    def find_best_cut_point(clip, search_start, search_end, fps=22050):
        try:
            if hasattr(clip, "subclipped"):
                 subclip = clip.subclipped(search_start, search_end)
            else:
                 subclip = clip.subclip(search_start, search_end)
            arr = subclip.to_soundarray(fps=fps)
        except Exception as e:
            print(f"Warning: Failed to analyze audio for silence: {e}")
            return search_end

        if len(arr) == 0:
            return search_end
            
        window_size = int(fps * 0.1)
        if window_size == 0: window_size = 1
        
        volumes = []
        timestamps = []
        
        for i in range(0, len(arr), window_size):
            chunk = arr[i:i+window_size]
            if len(chunk) == 0: continue
            rms = np.sqrt(np.mean(chunk**2))
            volumes.append(rms)
            timestamps.append(search_start + i / float(fps))
            
        if not volumes:
            return search_end

        volumes = np.array(volumes)
        timestamps = np.array(timestamps)
        
        min_vol = np.min(volumes)
        threshold = min_vol + 0.005
        
        candidates_indices = np.where(volumes <= threshold)[0]
        
        if len(candidates_indices) > 0:
            return timestamps[candidates_indices[-1]]
        else:
            return timestamps[np.argmin(volumes)]

    @staticmethod
    def split_audio(file_path, max_duration_sec=29.0, output_dir=None):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件未找到: {file_path}")
            
        if output_dir is None:
            output_dir = os.path.dirname(file_path)

        base_name = os.path.splitext(os.path.basename(file_path))[0]
        ext = os.path.splitext(file_path)[1].replace('.', '')
        
        audio = None
        try:
            audio = AudioFileClip(file_path)
            total_duration = audio.duration
            chunks_paths = []
            
            cut_points = [0.0]
            current_pos = 0.0
            
            while current_pos < total_duration:
                if total_duration - current_pos <= max_duration_sec:
                    cut_points.append(total_duration)
                    break
                
                search_limit = current_pos + max_duration_sec
                search_start = max(current_pos + 5, search_limit - 10)
                search_end = search_limit
                
                best_cut = AudioSplitter.find_best_cut_point(audio, search_start, search_end)
                if best_cut - current_pos < 5.0:
                    best_cut = search_limit
                
                cut_points.append(best_cut)
                current_pos = best_cut
            
            for i in range(len(cut_points) - 1):
                start_t = cut_points[i]
                end_t = cut_points[i+1]
                if end_t - start_t < 0.5: continue
                
                chunk_name = f"{base_name}_part{i+1}.{ext}"
                target_path = os.path.join(output_dir, chunk_name)
                
                if hasattr(audio, "subclipped"):
                     chunk = audio.subclipped(start_t, end_t)
                else:
                     chunk = audio.subclip(start_t, end_t)
                
                chunk.write_audiofile(target_path, codec=None, logger=None)
                chunks_paths.append(target_path)
                
            audio.close()
            return chunks_paths
        except Exception as e:
            if audio: audio.close()
            raise RuntimeError(f"分割出错: {str(e)}")

class AudioComparator:
    @staticmethod
    def get_head_signature(file_path, duration=5.0, fps=12000):
        if not os.path.exists(file_path): return None
        try:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            fd, temp_wav = tempfile.mkstemp(suffix=".wav")
            os.close(fd) 
            try:
                cmd = [
                    ffmpeg_exe, "-y", "-i", file_path,
                    "-ss", "0", "-t", str(duration),
                    "-vn", "-acodec", "pcm_s16le",
                    "-ar", str(fps), "-ac", "1",
                    temp_wav
                ]
                creation_flags = 0
                if os.name == 'nt':
                     creation_flags = subprocess.CREATE_NO_WINDOW
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, creationflags=creation_flags)
                
                with wave.open(temp_wav, 'rb') as wf:
                    raw_frames = wf.readframes(wf.getnframes())
                    arr = np.frombuffer(raw_frames, dtype=np.int16).astype(np.float32)
                
                if len(arr) == 0: return None
                arr = arr - np.mean(arr)
                std_dev = np.sqrt(np.mean(arr**2))
                if std_dev < 10.0: return None
                norm = np.linalg.norm(arr)
                if norm > 0: arr = arr / norm
                return arr
            finally:
                if os.path.exists(temp_wav):
                    try: os.remove(temp_wav)
                    except: pass
        except:
            return None

    @staticmethod
    def find_best_match_from_db_cached(audio_head_sig, audio_duration, video_db):
        if audio_head_sig is None: return None
        best_match_name = None
        best_score = -1.0
        duration_tolerance = 20.0 
        len_aud = len(audio_head_sig)
        scan_step = 20 
        fps = 12000

        for item in video_db:
            if item.get('matched'): continue
            if abs(item['duration'] - audio_duration) > duration_tolerance: continue
            vid_sig = item.get('head_sig')
            if vid_sig is None: continue
            
            len_vid = len(vid_sig)
            if len_vid < len_aud:
                val_len = min(len_vid, len_aud)
                if val_len < 1000: continue
                s1 = audio_head_sig[:val_len]
                s2 = vid_sig[:val_len]
                try: score = np.corrcoef(s1, s2)[0,1]
                except: score = 0.0
            else:
                max_offset_val = -1.0
                max_shift_frames = int(2.0 * fps)
                search_range = min(len_vid - len_aud, max_shift_frames)
                
                if search_range <= 0:
                    try: max_offset_val = np.corrcoef(audio_head_sig, vid_sig[:len_aud])[0,1]
                    except: max_offset_val = 0.0
                else:
                    found_best_idx = 0
                    local_max = -1.0
                    for start_idx in range(0, search_range + 1, scan_step):
                        v_slice = vid_sig[start_idx : start_idx + len_aud]
                        dot_val = np.dot(audio_head_sig, v_slice)
                        norm_v = np.linalg.norm(v_slice)
                        if norm_v > 0.001:
                            raw_score = dot_val / norm_v
                            if raw_score > local_max:
                                local_max = raw_score
                                found_best_idx = start_idx
                    
                    refine_range = 100 
                    r_start = max(0, found_best_idx - refine_range)
                    r_end = min(search_range, found_best_idx + refine_range)
                    final_local_max = -1.0
                    for start_idx in range(r_start, r_end + 1, 5): 
                        v_slice = vid_sig[start_idx : start_idx + len_aud]
                        norm_v = np.linalg.norm(v_slice)
                        if norm_v > 0.001:
                            score = np.dot(audio_head_sig, v_slice) / norm_v
                            if score > final_local_max:
                                final_local_max = score
                    max_offset_val = final_local_max
                score = max_offset_val

            if score > best_score:
                best_score = score
                best_match_name = item['name']

        if best_match_name and best_score > 0.82:
            return (best_match_name, best_score)
        return None

class SplitWorker(QThread):
    progress_log = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, file_paths, segment_length_sec, output_dir):
        super().__init__()
        self.file_paths = file_paths
        self.segment_length_sec = segment_length_sec
        self.output_dir = output_dir

    def run(self):
        try:
            if self.output_dir and not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
            total = len(self.file_paths)
            for i, file_path in enumerate(self.file_paths):
                self.progress_log.emit(f"[{i+1}/{total}] 正在处理: {os.path.basename(file_path)} ...")
                result_paths = AudioSplitter.split_audio(
                    file_path, 
                    max_duration_sec=self.segment_length_sec, 
                    output_dir=self.output_dir
                )
                self.progress_log.emit(f"   > 完成。生成了 {len(result_paths)} 个片段。")
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class MatchWorker(QThread):
    progress_log = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, video_dir, audio_dir, auto_rename):
        super().__init__()
        self.video_dir = video_dir
        self.audio_dir = audio_dir
        self.auto_rename = auto_rename

    def run(self):
        try:
            self.progress_log.emit("🔍 [Step 1] 扫描视频并预加载指纹...")
            video_files = [f for f in os.listdir(self.video_dir) 
                           if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.flv'))]
            if not video_files:
                self.finished.emit("❌ 视频文件夹为空！")
                return

            video_db = []
            total_vid = len(video_files)
            for i, v_name in enumerate(video_files):
                if i % 5 == 0:
                     self.progress_log.emit(f"   ... 已索引 {i}/{total_vid} 个视频")
                v_path = os.path.join(self.video_dir, v_name)
                try:
                    info = AudioUtils.get_audio_info(v_path)
                    dur = info['duration_seconds'] if info else 0
                    if dur > 0:
                        head_sig = AudioComparator.get_head_signature(v_path, duration=7.0)
                        video_db.append({'name': v_name, 'path': v_path, 'duration': dur, 'head_sig': head_sig, 'matched': False})
                except: pass
            self.progress_log.emit(f"✅ 视频索引完成. 有效数据: {len(video_db)} 条")

            audio_files = [f for f in os.listdir(self.audio_dir) 
                          if f.lower().endswith(('.mp3', '.wav', '.ogg', '.flac', '.m4a'))]
            audio_files.sort()
            total_audio = len(audio_files)
            self.progress_log.emit(f"\n🔍 [Step 2] 开始匹配...")
            
            success_count = 0
            fail_list = []
            report_interval = max(1, total_audio // 20)
            
            for i, aud_name in enumerate(audio_files):
                aud_path = os.path.join(self.audio_dir, aud_name)
                if i % report_interval == 0:
                    self.progress_log.emit(f"   正在处理 {i+1}/{total_audio} ...")
                
                aud_info = AudioUtils.get_audio_info(aud_path)
                if not aud_info:
                    fail_list.append(f"{aud_name} (坏文件)")
                    continue
                aud_dur = aud_info['duration_seconds']
                aud_head_sig = AudioComparator.get_head_signature(aud_path, duration=5.0)
                if aud_head_sig is None:
                    fail_list.append(f"{aud_name} (静音/错误)")
                    continue
                    
                result = AudioComparator.find_best_match_from_db_cached(aud_head_sig, aud_dur, video_db)
                if result:
                    vid_name, score = result
                    self.progress_log.emit(f"   ✅ [匹配] {aud_name} == {vid_name} ({score:.3f})")
                    matched_item = next((v for v in video_db if v['name'] == vid_name), None)
                    if matched_item:
                        matched_item['matched'] = True
                        if self.auto_rename:
                            old_path = matched_item['path']
                            vid_ext = os.path.splitext(vid_name)[1]
                            aud_base = os.path.splitext(aud_name)[0]
                            new_name = f"{aud_base}{vid_ext}"
                            new_path = os.path.join(self.video_dir, new_name)
                            if os.path.normpath(old_path) != os.path.normpath(new_path):
                                try:
                                    if os.path.exists(new_path):
                                         counter = 1
                                         while True:
                                             root, ext = os.path.splitext(new_name)
                                             temp_name = f"{root}_{counter}{ext}"
                                             temp_path = os.path.join(self.video_dir, temp_name)
                                             if not os.path.exists(temp_path):
                                                 new_name = temp_name
                                                 new_path = temp_path
                                                 break
                                             counter += 1
                                    os.rename(old_path, new_path)
                                    matched_item['path'] = new_path
                                    matched_item['name'] = new_name
                                except Exception as e:
                                    self.progress_log.emit(f"      ❌ 重命名出错: {e}")
                    success_count += 1
                else:
                    self.progress_log.emit(f"      ❌ 未匹配: {aud_name}")
                    fail_list.append(aud_name)
            
            summary = f"匹配完成！\n总音频: {total_audio}\n成功: {success_count}\n失败/静音: {len(fail_list)}"
            self.finished.emit(summary)
        except Exception as e:
            self.error.emit(str(e))
