# pylint: disable=all
import os
import sys
import platform
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class AppConfig:
    app_name: str = "Machine Translator"
    version: str = "2.0.0"
    theme: str = "dark"
    color_theme: str = "blue"

    # Supported Languages
    source_languages: List[str] = field(default_factory=lambda: [
        "Auto", "en", "fa", "de", "fr", "es", "ar", "ru", "zh-CN"
    ])

    destination_languages: List[str] = field(default_factory=lambda: [
        "fa", "en", "de", "fr", "es", "ar", "ru", "zh-CN", "pl",
        "pt-pt", "th", "hu", "hi", "he", "ko", "id", "bg", "vi", "ja", "ms", "pa"
    ])

    # Engines
    engines: List[str] = field(default_factory=lambda: [
        "Google", "Perplexity", "ChatGPT (API)", "ChatGPT (Web)"
    ])

    # Paths
    base_dir: str = field(init=False)
    legacy_script_path: str = field(init=False)

    def __post_init__(self):
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # Locate the legacy script
        potential_paths = [
            os.path.join(self.base_dir, "src", "machine-translate-docx.py"),
            os.path.join(self.base_dir, "machine-translate-docx.py"),
        ]

        self.legacy_script_path = ""
        for path in potential_paths:
            if os.path.exists(path):
                self.legacy_script_path = path
                break

    def get_legacy_script_path(self) -> str:
        if not self.legacy_script_path:
            raise FileNotFoundError("Could not find 'machine-translate-docx.py' in expected locations.")
        return self.legacy_script_path
