"""
更新工具脚本：为已有 Anki 笔记补齐音频。
使用前请确保 Anki 客户端与 AnkiConnect 已启动。
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import sys
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import requests


CURRENT_DIR = Path(__file__).resolve().parent
ANKI_MODULE_PATH = CURRENT_DIR / "anki.py"

spec = importlib.util.spec_from_file_location("anki_module", ANKI_MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f"无法加载 anki 模块: {ANKI_MODULE_PATH}")
anki = importlib.util.module_from_spec(spec)
sys.modules["anki_module"] = anki
spec.loader.exec_module(anki)


def chunked(iterable: Iterable[int], size: int) -> Iterable[List[int]]:
    """把可迭代对象按固定大小分块。"""
    block: List[int] = []
    for item in iterable:
        block.append(item)
        if len(block) >= size:
            yield block
            block = []
    if block:
        yield block


def update_notes_audio(
    deck_name: str,
    word_info_fetcher: Optional[Callable[[str], Dict[str, Any]]] = None
) -> None:
    """
    仍可按原方式，根据外部 word_info 数据为旧笔记补齐音频。
    :param deck_name: 目标牌组名称
    :param word_info_fetcher: 自定义函数，输入单词返回 word_info 结构；默认使用 anki.get_word_info
    """
    fetcher = word_info_fetcher or anki.get_word_info
    note_ids = anki.invoke("findNotes", query=f'deck:"{deck_name}"').get("result") or []
    if not note_ids:
        print(f"[音频] 未在牌组 '{deck_name}' 中找到笔记。")
        return

    notes_details = anki.invoke("notesInfo", notes=note_ids).get("result") or []
    if not notes_details:
        print(f"[音频] 无法获取牌组 '{deck_name}' 的笔记详情。")
        return

    for note in notes_details:
        fields_data = note.get("fields") or {}
        word_value = (fields_data.get("Word") or {}).get("value", "").strip()
        if not word_value:
            continue

        word_info = fetcher(word_value)
        if not word_info:
            print(f"[音频] '{word_value}' 未获取到 word_info，跳过。")
            continue

        audio_markup = anki.ensure_pronunciation_audio(word_info)
        if not audio_markup:
            print(f"[音频] '{word_value}' 没有可用的音频链接。")
            continue

        fields_to_update: Dict[str, str] = {}
        for target_field in ("Pronunciation", "POS_Definitions"):
            current_html = (fields_data.get(target_field) or {}).get("value", "")
            if audio_markup not in current_html:
                fields_to_update[target_field] = (
                    f"{audio_markup}\n{current_html}" if current_html else audio_markup
                )

        if not fields_to_update:
            continue

        anki.invoke("updateNoteFields", note={"id": note.get("noteId"), "fields": fields_to_update})
        print(f"[音频] '{word_value}' 已补充音频。")


US_AUDIO_ROW_PATTERN = re.compile(
    r'(<div[^>]*class=["\']audio-row["\'][^>]*>.*?US:.*?src=["\']([^"\']+)["\'].*?</div>)',
    re.IGNORECASE | re.DOTALL,
)


def _store_audio_from_url(word_value: str, audio_url: str, suffix: str = "-us") -> Optional[str]:
    """下载指定音频 URL，写入媒体库并返回 sound 标记。"""
    if not audio_url:
        return None

    try:
        resp = requests.get(
            audio_url,
            timeout=max(getattr(anki, "REQUEST_TIMEOUT", 2.0), 5),
            headers=getattr(anki, "AUDIO_HTTP_HEADERS", {}),
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"[音频] 下载失败: {audio_url} ({exc})")
        return None

    extension = anki.infer_audio_extension(audio_url, resp.headers.get("Content-Type", ""))
    base_word = word_value or "audio"
    hash_tail = hashlib.md5(audio_url.encode("utf-8")).hexdigest()[:8]
    filename = f"{anki.sanitize_media_filename(base_word)}{suffix}-{hash_tail}{extension}"

    encoded = base64.b64encode(resp.content).decode("utf-8")
    store_res = anki.invoke("storeMediaFile", filename=filename, data=encoded)
    if store_res.get("error"):
        print(f"[音频] 存储失败: {store_res['error']} ({audio_url})")
        return None

    return f"[sound:{filename}]"


def backfill_sound_from_pos_definitions(deck_name: Optional[str] = None) -> None:
    """
    遍历牌组中的既有笔记（默认遍历全部），在 POS_Definitions 字段中查找 US 音频，
    下载 mp3 并追加 [sound:xxx] 标记。
    :param deck_name: 需要处理的牌组名称；为 None 时遍历所有笔记
    """
    query = f'deck:"{deck_name}"' if deck_name else ""
    note_ids = anki.invoke("findNotes", query=query).get("result") or []
    if not note_ids:
        print(f"[音频] 未找到待处理的笔记（查询: {query or '所有牌组'}）。")
        return

    processed = 0
    for batch in chunked(note_ids, 50):
        notes_info = anki.invoke("notesInfo", notes=batch).get("result") or []
        for note in notes_info:
            processed += 1
            fields_data = note.get("fields") or {}
            word_value = (fields_data.get("Word") or {}).get("value", "").strip()
            pos_field = (fields_data.get("POS_Definitions") or {}).get("value", "")
            if not pos_field:
                continue

            match = US_AUDIO_ROW_PATTERN.search(pos_field)
            if not match:
                continue

            audio_row_html, audio_url = match.groups()
            sound_markup = _store_audio_from_url(word_value, audio_url)
            if not sound_markup or sound_markup in pos_field:
                continue

            updated_html = pos_field.replace(audio_row_html, f"{audio_row_html}{sound_markup}", 1)
            anki.invoke(
                "updateNoteFields",
                note={"id": note.get("noteId"), "fields": {"POS_Definitions": updated_html}},
            )
            print(f"[音频] '{word_value}' 已补充 US 发音。")

    print(f"[音频] 处理完成，共检查 {processed} 条笔记。")


if __name__ == "__main__":
    # 示例：遍历所有牌组并补齐 POS_Definitions 中的 US 音频
    backfill_sound_from_pos_definitions("test")

