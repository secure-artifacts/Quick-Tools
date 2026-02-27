import os
import json

CONFIG_FILE = "config.json"

class ConfigManager:
    _instance = None
    _config = {
        "global_output_dir": "",
        "elevenlabs_api_key": "",
        "elevenlabs_voice_id": "JBFqnCBsd6RMkjVDRZzb",
        "elevenlabs_model_id": "eleven_v3",
        "elevenlabs_keys": [], # [{'key': 'xxx', 'label': '备注'}]
        "google_ai_api_key": "",
        "google_ai_voice_id": "Zephyr",
        "google_ai_model_id": "gemini-2.5-flash-preview-tts", # 默认模型
        "google_ai_keys": [], # [{'key': 'xxx', 'label': '备注'}]
        "voice_library": [], # [{'category': 'GroupName', 'items': [{'name': '...', 'voice_id': '...', 'desc': '...', 'image': '...'}]}],
        "audio_tasks": [] # [{'name': '...', 'content': '...', 'voice_id': '...', 'checked': True}]
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.load_config()
        return cls._instance

    def load_config(self):
        """Load config from JSON file."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    new_data = json.load(f)
                    if isinstance(new_data, dict):
                        # Use dict.update to merge, but we might want to ensure 
                        # all default keys exist if the loaded file is partial
                        self._config.update(new_data)
            except Exception as e:
                print(f"Error loading config: {e}")
        else:
            # If not exists, save the default config immediately to create the file
            self.save_config()

    def save_config(self):
        """Save current config to JSON file."""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get_global_output_dir(self):
        return self._config.get("global_output_dir", "")

    def set_global_output_dir(self, path):
        self._config["global_output_dir"] = path
        self.save_config()

    def get_elevenlabs_api_key(self):
        return self._config.get("elevenlabs_api_key", "")

    def set_elevenlabs_api_key(self, key):
        self._config["elevenlabs_api_key"] = key
        self.save_config()

    def get_elevenlabs_voice_id(self):
        return self._config.get("elevenlabs_voice_id", "JBFqnCBsd6RMkjVDRZzb")

    def set_elevenlabs_voice_id(self, voice_id):
        self._config["elevenlabs_voice_id"] = voice_id
        self.save_config()

    def get_elevenlabs_model_id(self):
        return self._config.get("elevenlabs_model_id", "eleven_v3")

    def set_elevenlabs_model_id(self, model_id):
        self._config["elevenlabs_model_id"] = model_id
        self.save_config()

    def get_elevenlabs_keys(self):
        return self._config.get("elevenlabs_keys", [])

    def set_elevenlabs_keys(self, keys_list):
        self._config["elevenlabs_keys"] = keys_list
        self.save_config()

    def get_google_ai_keys(self):
        return self._config.get("google_ai_keys", [])

    def set_google_ai_keys(self, keys_list):
        self._config["google_ai_keys"] = keys_list
        self.save_config()

    def get_voice_library(self):
        return self._config.get("voice_library", [])

    def set_voice_library(self, library):
        self._config["voice_library"] = library
        self.save_config()

    def get_audio_tasks(self, provider="ElevenLabs"):
        # 兼容旧配置，如果 provider 是 ElevenLabs 且 audio_tasks 有值但 elevenlabs_tasks 为空，则迁移
        if provider == "ElevenLabs":
            tasks = self._config.get("elevenlabs_tasks", [])
            if not tasks and self._config.get("audio_tasks"):
                tasks = self._config.get("audio_tasks", [])
            return tasks
        elif provider == "Google AI (Gemini)" or provider == "Google AI":
            return self._config.get("google_ai_tasks", [])
        return []

    def set_audio_tasks(self, tasks_list, provider="ElevenLabs"):
        if provider == "ElevenLabs":
            self._config["elevenlabs_tasks"] = tasks_list
            # 同时更新旧的一份以防回滚版本兼容
            self._config["audio_tasks"] = tasks_list
        elif provider == "Google AI (Gemini)" or provider == "Google AI":
            self._config["google_ai_tasks"] = tasks_list
        self.save_config()

