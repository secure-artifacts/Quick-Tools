import os
import time
import uuid
from PyQt6.QtCore import QThread, pyqtSignal

class ElevenLabsWorker(QThread):
    progress_log = pyqtSignal(str)
    item_finished = pyqtSignal(int)
    item_result = pyqtSignal(int, bool, str) # index, success, error_msg
    finished = pyqtSignal(str) # 总结报告
    error = pyqtSignal(str)

    def __init__(self, texts_with_keys, output_dir, all_keys_pool=None, model_id="eleven_v3", default_voice_id="JBFqnCBsd6RMkjVDRZzb", clear_output=False, dict_id=None, auto_manage_voices=False):
        super().__init__()
        self.texts = texts_with_keys
        self.output_dir = output_dir
        self.model_id = model_id
        self.default_voice_id = default_voice_id
        self.clear_output = clear_output
        self.dict_id = dict_id
        self.auto_manage_voices = auto_manage_voices
        self.all_keys_pool = all_keys_pool or []
        
        assigned_keys = set(item.get('api_key') for item in self.texts if item.get('api_key'))
        self.spare_keys = [k for k in self.all_keys_pool if k not in assigned_keys]

    def _convert_and_save(self, client, api_key, item):
        name = item['name']
        content = item['content']
        item_voice_id = item.get('voice_id') or self.default_voice_id
        
        if self.auto_manage_voices and item_voice_id:
            for vm_attempt in range(3):
                try:
                    current_voices = client.voices.get_all().voices
                    # Filter for voices that likely count towards limit. Re-adding 'professional' just in case.
                    custom_voices = [v for v in current_voices if v.category in ['generated', 'cloned', 'professional']]
                    
                    # Debug info
                    # self.progress_log.emit(f"      🔍 诊断: 当前账号共有 {len(current_voices)} 个声线，其中自定义声线 {len(custom_voices)} 个。")

                    # Check if we really need to free up space (limit is usually 3 for free tier)
                    if not any(v.voice_id == item_voice_id for v in current_voices) and len(custom_voices) >= 3:
                        self.progress_log.emit(f"   🔄 槽位已满 ({len(custom_voices)}/3)，尝试释放旧声线...")
                        
                        deleted_count = 0
                        # Sort by creation date if possible, but for now just try to delete one by one until we have space
                        for cv in custom_voices:
                            try:
                                self.progress_log.emit(f"      正在删除声线: {cv.name} ({cv.voice_id})...")
                                client.voices.delete(cv.voice_id)
                                deleted_count += 1
                                self.progress_log.emit(f"      ✅ 删除成功")
                                # If we deleted enough to have space (we need 1 slot free), break
                                # But since we are adding a NEW voice, maybe we need just 1 slot.
                                if len(custom_voices) - deleted_count < 3:
                                    break
                            except Exception as del_err:
                                self.progress_log.emit(f"      ❌ 删除失败: {str(del_err)}")
                        
                        if deleted_count == 0:
                            self.progress_log.emit(f"   ⚠️ 警告: 无法释放任何声线！系统将尝试强制生成，但可能会失败。")
                        
                        time.sleep(1)
                    break # Success, exit retry loop
                    
                except Exception as e:
                    err_str = str(e)
                    if "SSL" in err_str or "EOF" in err_str or "connection" in err_str.lower():
                        if vm_attempt < 2:
                            self.progress_log.emit(f"      ⚠️ 获取声线列表失败 (网络抖动)，正在重试...")
                            time.sleep(1)
                            continue
                    self.progress_log.emit(f"   ⚠️ 自动管理声线出错: {str(e)}")
                    break

        safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
        if not safe_name.lower().endswith(".mp3"): safe_name += ".mp3"
        target_path = os.path.join(self.output_dir, safe_name)
        
        kwargs = {
            "text": content,
            "voice_id": item_voice_id,
            "model_id": self.model_id,
            "output_format": "mp3_44100_128"
        }
        if self.dict_id:
            from elevenlabs import PronunciationDictionaryVersionLocator
            kwargs["pronunciation_dictionary_locators"] = [
                PronunciationDictionaryVersionLocator(pronunciation_dictionary_id=self.dict_id, version_id="latest")
            ]

        max_retries = 10
        last_exception = None

        for attempt in range(max_retries):
            try:
                # API Call
                audio_gen = client.text_to_speech.convert(**kwargs)
                
                # Use a random UUID for the temporary filename to protect privacy during generation
                temp_filename = f"gen_{uuid.uuid4().hex}.mp3"
                temp_path = os.path.join(self.output_dir, temp_filename)
                
                with open(temp_path, "wb") as f:
                    for chunk in audio_gen:
                        if self.isInterruptionRequested():
                            raise InterruptedError("User requested stop")
                        if chunk: f.write(chunk)
                
                # Rename to final target name after successful write
                if os.path.exists(target_path):
                    try: os.remove(target_path)
                    except: pass
                os.rename(temp_path, target_path)
                
                return True # Success
                
            except Exception as e:
                last_exception = e
                err_str = str(e)
                
                # Handle Voice Limit Reached specifically
                if "voice_limit_reached" in err_str:
                     # No point retrying immediately if we are full
                     raise Exception("声线槽位已满 (3/3)，且无法自动释放。请手动登录官网清理声线或升级套餐。")

                # Check for specific network/server errors
                is_network_error = (
                    "Server disconnected" in err_str or 
                    "RemoteProtocolError" in err_str or 
                    "connection" in err_str.lower() or
                    "SSL" in err_str or
                    "EOF" in err_str
                )
                
                if self.isInterruptionRequested():
                    raise InterruptedError("User requested stop")

                # If loop finishes without returning (should be caught by last_exception check but just in case)
                if attempt < max_retries - 1:
                    wait_time = 5 + attempt * 2 # Progressive wait: 5, 7, 9...
                    self.progress_log.emit(f"   ⚠️ 网络连接不稳定 ({err_str[:20]}...)，正在重试 ({attempt+1}/{max_retries})，等待 {wait_time}秒...")
                    
                    # Sleep in small increments to respond to interruption faster
                    for _ in range(wait_time * 2):
                        if self.isInterruptionRequested(): break
                        time.sleep(0.5)
                    
                    if self.isInterruptionRequested():
                        raise InterruptedError("User requested stop")
                    continue
                
                # If we get here, cleanup temp file if exists
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    try: os.remove(temp_path)
                    except: pass
                
                # If not retryable or out of retries, re-raise
                if not is_network_error:
                    raise e
        
        # If loop finishes without returning (should be caught by last_exception check but just in case)
        if last_exception:
            raise last_exception

    def run(self):
        try:
            from elevenlabs.client import ElevenLabs
            
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
            elif self.clear_output:
                for f in os.listdir(self.output_dir):
                    try: os.remove(os.path.join(self.output_dir, f))
                    except: pass

            total = len(self.texts)
            success_count = 0
            deferred_tasks = []
            clients = {}

            for i, item in enumerate(self.texts):
                if self.isInterruptionRequested(): break
                if i > 0: time.sleep(1.2)
                
                api_key = item.get('api_key')
                if not api_key: 
                    self.item_result.emit(i, False, "未分配 API Key")
                    continue

                if api_key not in clients: clients[api_key] = ElevenLabs(api_key=api_key)
                client = clients[api_key]

                self.progress_log.emit(f"[{i+1}/{total}] 使用 Key {api_key[-4:]} 生成: {item['name']} ...")
                
                try:
                    self._convert_and_save(client, api_key, item)
                    success_count += 1
                    self.progress_log.emit(f"   ✅ 完成")
                    self.item_finished.emit(i)
                    self.item_result.emit(i, True, "")
                except Exception as e:
                    err_msg = str(e)
                    if "detected_unusual_activity" in err_msg:
                        self.progress_log.emit(f"   ❌ 失败: 账号异常(被风控)！")
                        self.item_result.emit(i, False, f"账号风控: {err_msg}")
                        self.progress_log.emit(f"🚨 触发账号安全保护，任务已整体熔断停止。")
                        self.finished.emit(f"任务因风控熔断终止。\n成功: {success_count}/{total}")
                        for rem_idx in range(i + 1, total):
                            self.item_result.emit(rem_idx, False, "由于前序任务风控导致熔断")
                        return

                    if "quota_exceeded" in err_msg or "insufficient_credits" in err_msg:
                        self.progress_log.emit(f"   ⚠️ Key {api_key[-4:]} 余额不足，正在寻找可用备用 Key...")
                        found_spare = False
                        for s_key in self.spare_keys:
                            self.progress_log.emit(f"      ↪️ 尝试备用 Key {s_key[-4:]} ...")
                            if s_key not in clients: clients[s_key] = ElevenLabs(api_key=s_key)
                            try:
                                self._convert_and_save(clients[s_key], s_key, item)
                                self.progress_log.emit(f"   ✅ 使用备用 Key {s_key[-4:]} 成功补救")
                                success_count += 1
                                self.item_finished.emit(i)
                                self.item_result.emit(i, True, "")
                                found_spare = True
                                break
                            except Exception as e:
                                self.progress_log.emit(f"      ❌ 失败: {str(e)}")
                                continue
                        
                        if not found_spare:
                            self.progress_log.emit(f"   🕒 无可用备用 Key，任务 '{item['name']}' 将移至最后尝试。")
                            deferred_tasks.append((i, item))
                    else:
                        self.progress_log.emit(f"   ❌ 失败: {err_msg}")
                        self.item_result.emit(i, False, err_msg)

            if deferred_tasks and not self.isInterruptionRequested():
                self.progress_log.emit(f"\n🔄 正在进行最后补救：刷新余额并尝试 {len(deferred_tasks)} 个延后任务...")
                for d_idx, d_item in deferred_tasks:
                    if self.isInterruptionRequested(): break
                    time.sleep(1.5)
                    self.progress_log.emit(f"⏳ 正在最后尝试: {d_item['name']} ...")
                    
                    final_success = False
                    for k in self.all_keys_pool:
                        if k not in clients: clients[k] = ElevenLabs(api_key=k)
                        try:
                            self._convert_and_save(clients[k], k, d_item)
                            self.progress_log.emit(f"   ✅ 补救成功 (Key {k[-4:]})")
                            success_count += 1
                            self.item_finished.emit(d_idx)
                            self.item_result.emit(d_idx, True, "")
                            final_success = True
                            break
                        except: continue
                    
                    if not final_success:
                        self.progress_log.emit(f"   ❌ 补救失败：所有 Key 仍余额不足。")
                        self.item_result.emit(d_idx, False, "所有可用 Key 余额均不足")

            self.finished.emit(f"批量生成任务已完成！\n成功: {success_count}/{total}")
            
        except ImportError:
            self.error.emit("未安装 elevenlabs 库。")
        except Exception as e:
            self.error.emit(f"运行出错: {str(e)}")

class KeyInfoWorker(QThread):
    info_received = pyqtSignal(str, dict) # key, info_dict
    error = pyqtSignal(str, str) # key, error_msg

    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

    def run(self):
        import traceback
        try:
            from elevenlabs.client import ElevenLabs
            # 设置30秒超时，避免网络问题导致查询一直卡住
            client = ElevenLabs(api_key=self.api_key, timeout=30)
            sub = client.user.subscription.get()
            
            # 同时查询自定义声线数量
            voice_count = 0
            try:
                response = client.voices.get_all()
                custom_voices = [v for v in response.voices if v.category in ['generated', 'cloned', 'professional']]
                voice_count = len(custom_voices)
            except Exception:
                voice_count = -1  # 查询失败标记
            
            info = {
                'character_count': sub.character_count,
                'character_limit': sub.character_limit,
                'remaining': sub.character_limit - sub.character_count,
                'status': sub.status,
                'voice_count': voice_count,
                'voice_limit': 3,  # 免费套餐默认限制
            }
            self.info_received.emit(self.api_key, info)
        except Exception as e:
            # 记录详细错误信息用于调试
            error_detail = f"{type(e).__name__}: {str(e)}"
            print(f"[KeyInfoWorker] 查询失败 Key={self.api_key[-4:]}, Error={error_detail}")
            traceback.print_exc()
            self.error.emit(self.api_key, error_detail)

class OnlineVoiceWorker(QThread):
    voices_received = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

    def run(self):
        try:
            from elevenlabs.client import ElevenLabs
            client = ElevenLabs(api_key=self.api_key)
            response = client.voices.get_all()
            voice_list = []
            for v in response.voices:
                if v.category in ['generated', 'cloned', 'professional']:
                    voice_list.append({
                        'id': v.voice_id,
                        'name': v.name,
                        'category': v.category,
                        'preview_url': v.preview_url
                    })
            self.voices_received.emit(voice_list)
        except Exception as e:
            self.error.emit(str(e))

class DeleteVoiceWorker(QThread):
    finished = pyqtSignal(bool, str) # success, msg

    def __init__(self, api_key, voice_id):
        super().__init__()
        self.api_key = api_key
        self.voice_id = voice_id

    def run(self):
        try:
            from elevenlabs.client import ElevenLabs
            client = ElevenLabs(api_key=self.api_key)
            client.voices.delete(self.voice_id)
            self.finished.emit(True, "声音已成功删除")
        except Exception as e:
            self.finished.emit(False, str(e))

class ClearVoicesWorker(QThread):
    """清空指定 API Key 下的所有自定义声线"""
    progress = pyqtSignal(str)  # 进度消息
    finished = pyqtSignal(bool, str)  # success, summary_msg

    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

    def run(self):
        try:
            from elevenlabs.client import ElevenLabs
            client = ElevenLabs(api_key=self.api_key, timeout=30)
            response = client.voices.get_all()
            custom_voices = [v for v in response.voices if v.category in ['generated', 'cloned', 'professional']]
            
            if not custom_voices:
                self.finished.emit(True, "该 Key 下没有自定义声线。")
                return
            
            total = len(custom_voices)
            deleted = 0
            failed = 0
            for v in custom_voices:
                try:
                    self.progress.emit(f"正在删除: {v.name} ({v.voice_id})...")
                    client.voices.delete(v.voice_id)
                    deleted += 1
                except Exception as e:
                    self.progress.emit(f"删除 {v.name} 失败: {str(e)}")
                    failed += 1
            
            msg = f"清空完成！成功删除 {deleted}/{total} 个声线。"
            if failed > 0:
                msg += f" ({failed} 个失败)"
            self.finished.emit(True, msg)
        except Exception as e:
            self.finished.emit(False, f"操作失败: {str(e)}")

