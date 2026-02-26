# AGENTS.md

## Project Overview

This is a Python-based vocabulary learning tool that creates Anki flashcards from two sources:
- **Book workflow** (`code/FULL/main.py`): Imports vocabulary from Koodo Reader CSV exports, looks up definitions from Cambridge Dictionary, performs NLP analysis, and creates Anki flashcards.
- **Movie workflow** (`code/movie/media_main.py`): Extracts vocabulary from movie subtitles with audio/screenshot extraction via ffmpeg.

Shared modules live under `code/`: `anki/`, `dictionary/`, `NLP/`, `save/`, `vcs/`, `info/`.

## Cursor Cloud specific instructions

### Environment notes

- Python 3.12 is used. Dependencies are installed via `pip3 install` (no virtualenv). The `~/.local/bin` directory must be on `PATH` for CLI tools like `spacy`, `nltk`, `tqdm`.
- The `requirements.txt` at `code/movie/requirements.txt` is a `pip freeze` from a Windows/conda environment and contains platform-specific paths (`file:///D:/...`, `file:///home/conda/...`). These entries fail on Linux. Core packages to install manually: `requests beautifulsoup4 lxml spacy nltk pandas numpy pillow tqdm python-dotenv pydantic`.
- After installing spaCy, you must also download the `en_core_web_sm` model: `python3 -m spacy download en_core_web_sm`.
- `ffmpeg` is pre-installed in the VM environment and required for the movie workflow.

### Running modules

- All Python modules expect `code/` on `sys.path`. To import them from the repo root, use `sys.path.insert(0, 'code')` or run scripts from within `code/`.
- The **dictionary scraper** (`code/dictionary/dict.py`) can be run standalone: `python3 code/dictionary/dict.py` — it fetches a word definition from Cambridge Dictionary.
- The **NLP module** (`code/NLP/NLP.py`) provides `analyze_word(sentence, target_word)` for lemmatization.
- The **book workflow** (`code/FULL/main.py`) is interactive (uses `input()`) and requires AnkiConnect at `localhost:8765`.
- The **movie workflow** (`code/movie/media_main.py`) requires a config file (`code/movie/config.json`), video files, and AnkiConnect.

### AnkiConnect dependency

- The Anki desktop app with AnkiConnect plugin (`localhost:8765`) is required for full end-to-end operation of both workflows. This cannot run in a headless cloud environment.
- Modules can be tested individually without AnkiConnect: `dictionary/dict.py`, `NLP/NLP.py`, `save/save.py`, `vcs/vcs.py`, `info/info.py`, and the HTML-building functions in `anki/anki.py`.

### Testing

- There are no automated tests or linting configuration in this project. Validation is done by running individual modules and verifying output.
- The `code/anki/demo.py` script is a good smoke test for the Anki integration (requires AnkiConnect running).
