# pylint: disable=all
from abc import ABC, abstractmethod
from typing import List, Optional

class BaseTranslator(ABC):
    @abstractmethod
    def translate(self,
                  docx_path: str,
                  src_lang: str,
                  dest_lang: str,
                  split_sentences: bool = True,
                  show_browser: bool = False) -> None:
        pass
