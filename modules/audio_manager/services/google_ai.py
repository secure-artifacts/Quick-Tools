import os
import mimetypes
import struct
import uuid
from PyQt6.QtCore import QThread, pyqtSignal
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

def parse_audio_mime_type(mime_type: str) -> dict[str, int]:
    """Parses bits per sample and rate from an audio MIME type string."""
    bits_per_sample = 16
    rate = 24000
    parts = mime_type.split(";")
    for param in parts:
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate_str = param.split("=", 1)[1]
                rate = int(rate_str)
            except (ValueError, IndexError): pass
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError): pass
    return {"bits_per_sample": bits_per_sample, "rate": rate}

def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Generates a WAV file header for the given audio data and parameters."""
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", chunk_size, b"WAVE", b"fmt ", 16, 1,
        num_channels, sample_rate, byte_rate, block_align, bits_per_sample,
        b"data", data_size
    )
    return header + audio_data

class GoogleAIWorker(QThread):
    progress_log = pyqtSignal(str)
    item_finished = pyqtSignal(int)
    item_result = pyqtSignal(int, bool, str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, texts_with_keys, output_dir, all_keys_pool=None, model_id="gemini-2.5-flash-preview-tts", default_voice_id="Zephyr", clear_output=False):
        super().__init__()
        self.texts = texts_with_keys
        self.output_dir = output_dir
        self.all_keys_pool = all_keys_pool or []
        self.model_id = model_id
        self.default_voice_id = default_voice_id
        self.clear_output = clear_output
        self._current_key_pool = self.all_keys_pool.copy()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    def _generate_content_stream(self, client, model_id, contents, config):
        return client.models.generate_content_stream(
            model=model_id,
            contents=contents,
            config=config,
        )

    def _convert_and_save(self, client, item):
        from google.genai import types
        
        name = item['name']
        content = item['content']
        voice_name = item.get('voice_id') or self.default_voice_id
        style = item.get('style', '')
        
        # Prepend prompt to force audio-only generation (fixes 400 INVALID_ARGUMENT on TTS models)
        # And include style instruction here instead of system_instruction to avoid 500 INTERNAL errors
        prompt_text = f"{style}\n\nPlease read the following text aloud: {content}"
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt_text)])]
        
        config_kwargs = {
            "temperature": 1, 
            "response_modalities": ["audio"],
            "speech_config": types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                )
            ),
        }

        # Removed system_instruction injection as it caused 500 INTERNAL errors on this model
        
        generate_content_config = types.GenerateContentConfig(**config_kwargs)

        safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
        
        full_audio_data = b""
        final_mime_type = None

        # Use the retrying method
        stream = self._generate_content_stream(client, self.model_id, contents, generate_content_config)

        for chunk in stream:
            if self.isInterruptionRequested():
                raise InterruptedError("User requested stop")
            if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                part = chunk.candidates[0].content.parts[0]
                if part.inline_data:
                    full_audio_data += part.inline_data.data
                    if not final_mime_type:
                        final_mime_type = part.inline_data.mime_type
        
        if not full_audio_data:
            raise RuntimeError("未生成任何音频数据")

        ext = mimetypes.guess_extension(final_mime_type) if final_mime_type else ".wav"
        if ext is None:
            ext = ".wav"
            full_audio_data = convert_to_wav(full_audio_data, final_mime_type or "audio/L16;rate=24000")
        
        if not safe_name.lower().endswith(ext): safe_name += ext
        
        # Use a random UUID for the temporary filename to protect privacy during generation
        temp_filename = f"gen_{uuid.uuid4().hex}{ext}"
        temp_path = os.path.join(self.output_dir, temp_filename)
        target_path = os.path.join(self.output_dir, safe_name)
        
        try:
            with open(temp_path, "wb") as f:
                f.write(full_audio_data)
            
            # Rename to final target name after successful write
            if os.path.exists(target_path):
                try: os.remove(target_path)
                except: pass
            os.rename(temp_path, target_path)
        except Exception as e:
            if os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass
            raise e
            
        return True

    def run(self):
        try:
            from google import genai
            
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
            elif self.clear_output:
                for f in os.listdir(self.output_dir):
                    try: os.remove(os.path.join(self.output_dir, f))
                    except: pass

            total = len(self.texts)
            success_count = 0
            clients = {}

            for i, item in enumerate(self.texts):
                if self.isInterruptionRequested(): break
                
                # Use allocated key first, but allow rotation
                api_key = item.get('api_key')
                if api_key not in self._current_key_pool and api_key in self.all_keys_pool:
                    # If current key was removed from pool due to error, pick a new one
                    if self._current_key_pool:
                        api_key = self._current_key_pool[0]
                
                if not api_key and self._current_key_pool:
                    api_key = self._current_key_pool[0]
                
                if not api_key:
                    self.item_result.emit(i, False, "无可用 API Key (所有 Key 额度已耗尽)")
                    continue

                self.progress_log.emit(f"[{i+1}/{total}] 使用 Google AI (Key {api_key[-4:]}) 生成: {item['name']} ...")
                
                while True:
                    if api_key not in clients: clients[api_key] = genai.Client(api_key=api_key)
                    client = clients[api_key]
                    
                    try:
                        self._convert_and_save(client, item)
                        success_count += 1
                        self.progress_log.emit(f"   ✅ 完成")
                        self.item_finished.emit(i)
                        self.item_result.emit(i, True, "")
                        break # Success, move to next item
                    except Exception as e:
                        err_str = str(e)
                        # Check for 429 quota errors (specifically the 10 request limit or limit:0)
                        if "429" in err_str and ("RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower()):
                            self.progress_log.emit(f"   ⚠️ 当前 Key ({api_key[-4:]}) 额度耗尽，尝试轮换...")
                            
                            # Remove failed key from pool
                            if api_key in self._current_key_pool:
                                self._current_key_pool.remove(api_key)
                            
                            # Try next key
                            if self._current_key_pool:
                                api_key = self._current_key_pool[0]
                                self.progress_log.emit(f"   🔄 切换至新 Key ({api_key[-4:]}) 重试...")
                                continue # Retry the SAME task with new key
                            else:
                                msg = f"   ❌ 失败: 所有 API Key 额度均已耗尽。错误: {err_str}"
                                self.progress_log.emit(msg)
                                self.item_result.emit(i, False, msg)
                                break # No more keys, move to next item (which will probably also fail)
                        else:
                            msg = f"   ❌ 失败: {err_str}"
                            self.progress_log.emit(msg)
                            self.item_result.emit(i, False, msg)
                            break # Non-quota error, move to next item

            self.finished.emit(f"Google AI 批量生成任务已完成！\n成功: {success_count}/{total}")
        except Exception as e:
            self.error.emit(f"运行出错: {str(e)}")
