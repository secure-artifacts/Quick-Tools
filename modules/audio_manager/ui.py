from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from modules.config_manager import ConfigManager
from .widgets import AudioSplitWidget, AudioMatchWidget, AudioGenerateWidget, HistoryWidget

class AudioManagerUI(QWidget):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        
        self.split_widget = AudioSplitWidget(self.config)
        self.tabs.addTab(self.split_widget, "🔪 智能分割")
        
        self.match_widget = AudioMatchWidget(self.config)
        self.tabs.addTab(self.match_widget, "🔗 音画匹配")
        
        # Instantiate separate widgets for each provider
        self.eleven_widget = AudioGenerateWidget(self.config, provider="ElevenLabs")
        self.tabs.addTab(self.eleven_widget, "🎤 ElevenLabs 生成")

        self.google_widget = AudioGenerateWidget(self.config, provider="Google AI (Gemini)")
        self.tabs.addTab(self.google_widget, "🤖 Google AI 生成")
        
        self.history_widget = HistoryWidget()
        self.tabs.addTab(self.history_widget, "📜 历史记录")
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)

    def update_default_path(self, global_path):
        self.split_widget.update_default_path(global_path)
        self.match_widget.update_default_path(global_path)
        self.eleven_widget.update_default_path(global_path)
        self.google_widget.update_default_path(global_path)
