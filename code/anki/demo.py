"""
Small demo utility that exercises the Anki integration by adding the word
``rebuff`` into a test deck. Run this script with Anki and AnkiConnect open.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any
import sys
import importlib.util


CURRENT_DIR = Path(__file__).resolve().parent
ANKI_MODULE_PATH = CURRENT_DIR / "anki.py"

spec = importlib.util.spec_from_file_location("anki_module", ANKI_MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f"Unable to load anki module from {ANKI_MODULE_PATH}")
anki = importlib.util.module_from_spec(spec)
sys.modules["anki_module"] = anki
spec.loader.exec_module(anki)


def build_rebuff_info() -> Dict[str, Any]:
    """Construct a minimal word_info payload for the demo."""
    return {
        "word": "rebuff",
        "wordUrl": "",
        "partOfSpeech": [
            {
                "type": "verb",
                "wordPrototype": "rebuff",
                "pronunciationUS": {
                    "phonetic": "/rɪˈbʌf/",
                    "pronUrl": "https://dictionary.cambridge.org/media/english/us_pron/r/reb/rebuf/rebuff.mp3",
                },
                "pronunciationUK": {
                    "phonetic": "/rɪˈbʌf/",
                    "pronUrl": "https://dictionary.cambridge.org/media/english/uk_pron/u/ukr/ukrea/ukreapp029.mp3",
                },

                "definitions": [
                    {
                        "enMeaning": "to refuse to accept a helpful suggestion or offer from someone, often by answering in an unfriendly way",
                        "chMeaning": "粗鲁地拒绝（好意、提议等）",
                    }
                ],
                "phrases": [],
                "phraseDefinitions": [],
            }
        ],
        "sentences": [
            {
                "text": "rebuff",
                "notes": "She tried to help but was sharply rebuffed by her colleague.",
                "bookName": "Example Collection",
                "chapter": "Politeness",
            }
        ],
    }


def main() -> None:
    deck_name = "demo"
    anki.ensure_model_and_deck(deck_name, anki.MODEL_NAME)
    anki.add_word_to_anki(deck_name, build_rebuff_info())


if __name__ == "__main__":
    main()
