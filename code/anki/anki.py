# -*- coding: utf-8 -*-
"""
Anki 导入与更新脚本:
- 功能1: 将 word_info 转为 Anki note，包含词性/发音/释义/短语等。
- 功能2: 'Examples' 字段中的目标词用 <strong> 加粗。
- 功能3: 'Blanked_Examples' 字段中，例句的所有单词字母被替换为下划线 `_`。
- 功能4: 提供一个函数，用于更新牌组中已有笔记的空字段。

需要 AnkiConnect（http://localhost:8765）和已打开的 Anki 客户端。
"""

import requests
import sys
import time
import html
import re
import json
from typing import Dict, Any, List, Tuple

# ==================== 配置项 ====================
ANKI_CONNECT_URL = "http://localhost:8765"
MODEL_NAME = "WordType" # 您可以根据需要修改模型名称
REQUEST_TIMEOUT = 2.0
# ================================================

def get_word_info(word: str) -> Dict[str, Any]:
    """
    [占位符] 根据单词获取其详细信息。
    请您务必将其替换为您自己的数据获取实现（例如，网络爬虫或API调用）。
    """
    print(f"--- [模拟] 正在为 '{word}' 获取信息... ---")
    if "juvenile prison" in word:
        return {
            "word": "juvenile prison",
            "wordUrl": "",
            "partOfSpeech": [{
                "type": "", "wordPrototype": "juvenile prison",
                "pronunciationUK": {"phonetic": "", "pronUrl": ""},
                "pronunciationUS": {"phonetic": "", "pronUrl": ""},
                "definitions": [{"enMeaning": "a prison for people who are young", "chMeaning": "青少年监狱"}],
                "phrases": [], "phraseDefinitions": []
            }],
            "sentences": [{
                "key": 1758084501416, "bookKey": 1738143464138, "date": "2025-09-17", "chapter": "Cover",
                "text": "juvenile prison",
                "notes": "The perpetrator ended up being sent to juvenile prison for it.",
                "bookName": "Elon Musk", "bookAuthor": "Walter Isaacson"
            }, {
                "text": "juvenile prison",
                "notes": "This is another example sentence about the juvenile prison.",
                "bookName": "Example Book"
            }]
        }
    print(f"--- [模拟] 未找到单词 '{word}' 的信息。 ---")
    return {}





def replace_alnum_with_underscores(match_obj: re.Match) -> str:
    """
    接收一个正则表达式匹配对象，
    并将其中的字母和数字替换为下划线。
    """
    word = match_obj.group(0)
    return ''.join(['_' if char.isalnum() else char for char in word])

def invoke(action: str, **params):
    """向 AnkiConnect 发送请求的辅助函数"""
    try:
        r = requests.post(
            ANKI_CONNECT_URL,
            json={"action": action, "version": 6, "params": params},
            timeout=REQUEST_TIMEOUT
        )
        r.raise_for_status()
        response_json = r.json()
        if response_json.get("error"):
            print(f"[AnkiConnect 错误] Action: {action}, Error: {response_json['error']}")
        return response_json
    except requests.RequestException as e:
        print(f"[错误] 无法连接 AnkiConnect ({ANKI_CONNECT_URL}): {e}")
        sys.exit(1)


def blank_out_all_words(sentence: str) -> str:
    """
    将句子中所有单词的英文字母替换为下划线，保留非字母字符（如标点、数字）和空格。
    例如："Hello world!" -> "_____ _____!"
    """
    if not sentence:
        return ""
    
    words = sentence.split(' ')
    blanked_words = []
    for word in words:
        # 对单词中的每个字符进行判断，是字母则替换，否则保留
        blanked_word = ''.join(['_' if char.isalpha() else char for char in word])
        blanked_words.append(blanked_word)
    return ' '.join(blanked_words)


def build_html_from_word_info(word_info: Dict[str, Any]) -> Dict[str, str]:
    """
    根据 word_info 构建笔记中各个字段的 HTML 内容。
    """
    # ... (此函数的其他部分与您原脚本类似，为了简洁此处省略了定义和短语部分)
    pos_html_parts: List[str] = []
    pronunciation_parts: List[str] = []
    definition_parts: List[str] = []
    examples_parts: List[str] = []
    blanked_examples_parts: List[str] = []
    
    word_to_highlight = word_info.get("word", "")

    # 处理发音、释义等
    for pos in word_info.get("partOfSpeech", []):
        pos_type = pos.get("type", "")
        pos_title_html = f"<div class='pos-title'>{html.escape(str(pos_type)).capitalize()}</div>" if pos_type else ""
        
        # 发音
        uk_p = pos.get("pronunciationUK", {}).get("phonetic", "")
        us_p = pos.get("pronunciationUS", {}).get("phonetic", "")
        if uk_p or us_p:
            pronunciation_parts.append(f"<div>{pos_title_html}UK: {html.escape(uk_p)} | US: {html.escape(us_p)}</div>")
        
        # 释义
        defs = pos.get("definitions") or []
        if defs:
            def_block = [pos_title_html, "<ul>"]
            for d in defs:
                en = (d.get("enMeaning") or "").strip()
                ch = (d.get("chMeaning") or "").strip()
                def_block.append(f"<li><div class='definition-en'>{html.escape(en)}</div><div class='definition-ch'>{html.escape(ch)}</div></li>")
            def_block.append("</ul>")
            definition_parts.append("".join(def_block))
        # 处理词性/定义/短语
    
    for pos in word_info.get("partOfSpeech", []):
        pos_type = pos.get("type", "")
        part_lines: List[str] = []
        part_lines.append(f"<div class='pos-title'>{html.escape(str(pos_type)).capitalize()}</div>")

        # 发音
        uk = pos.get("pronunciationUK") or {}
        us = pos.get("pronunciationUS") or {}
        audio_lines: List[str] = []
        if uk.get("phonetic") or uk.get("pronUrl"):
            aud = f"UK: {html.escape(uk.get('phonetic',''))}"
            if uk.get("pronUrl"):
                aud += f" <audio controls src=\"{html.escape(uk.get('pronUrl'))}\"></audio>"
            audio_lines.append(f"<div class='audio-row'>{aud}</div>")
        if us.get("phonetic") or us.get("pronUrl"):
            aud = f"US: {html.escape(us.get('phonetic',''))}"
            if us.get("pronUrl"):
                aud += f" <audio controls src=\"{html.escape(us.get('pronUrl'))}\"></audio>"
            audio_lines.append(f"<div class='audio-row'>{aud}</div>")
        if audio_lines:
            part_lines.extend(audio_lines)

        # 定义
        defs = pos.get("definitions") or []
        if defs:
            part_lines.append("<ul>")
            for d in defs:
                en = (d.get("enMeaning") or d.get("en") or "").strip()
                ch = (d.get("chMeaning") or d.get("ch") or "").strip()
                part_lines.append(
                    "<li>"
                    f"<div class='definition-en'>{html.escape(en)}</div>"
                    f"<div class='definition-ch'>{html.escape(ch)}</div>"
                    "</li>"
                )
            part_lines.append("</ul>")

        # 短语
        phrases = pos.get("phrases") or []
        phrase_defs = pos.get("phraseDefinitions") or []
        if phrases:
            part_lines.append("<div><b>Phrases:</b><ul>")
            for i, ph in enumerate(phrases):
                pd = phrase_defs[i] if i < len(phrase_defs) else {}
                en = (pd.get("enMeaning") or pd.get("en") or "").strip()
                ch = (pd.get("chMeaning") or pd.get("ch") or "").strip()
                part_lines.append(
                    "<li>"
                    f"<span class='phrase'>{html.escape(ph)}</span> — <span class='definition-en'>{html.escape(en)}</span>"
                    f"<div class='definition-ch'>{html.escape(ch)}</div>"
                    "</li>"
                )
            part_lines.append("</ul></div>")

        pos_html_parts.append("<div>" + "\n".join(part_lines) + "</div>")

    # 处理例句
    for s in word_info.get("sentences", []):
        sentence_text = s.get("notes").strip()
        if not sentence_text:
            continue
        
        # 1. 'Examples' 字段: 目标词加粗
        escaped_sentence = html.escape(sentence_text)
        highlighted = escaped_sentence
        target_word = s.get("text") or word_to_highlight # 用于加粗的目标词
        if target_word:
            try:
                pattern = re.compile(r'\b' + re.escape(html.escape(target_word.strip())) + r'\b', re.IGNORECASE)

                highlighted = pattern.sub(lambda m: f"<strong>{m.group(0)}</strong>", escaped_sentence)
            except re.error:
                pass # 忽略正则错误
        escaped_target = html.escape(target_word.strip())
        if " " in target_word:
            # 多词短语，不加 \b
            pattern_for_blanking = re.compile(re.escape(escaped_target), re.IGNORECASE)
        else:
            # 单词，加边界防止误匹配
            pattern_for_blanking = re.compile(r'\b' + re.escape(escaped_target) + r'\b', re.IGNORECASE)
        # pattern_for_blanking = re.compile(r'\b' + re.escape(target_word) + r'\b', re.IGNORECASE)
        # 2. 'Blanked_Examples' 字段: 所有单词字母替换为下划线
        blanked_sentence = pattern_for_blanking.sub(replace_alnum_with_underscores, sentence_text)
        escaped_blanked = html.escape(blanked_sentence)

        # 来源信息
        book = s.get("bookName") or ""
        meta = f" — 《{html.escape(book)}》" if book else ""

        examples_parts.append(f"<div class='example'><div class='example-text'>{highlighted}</div><div class='example-meta'>{meta}</div></div>")
        blanked_examples_parts.append(f"<div class='example'><div class='example-text'>{escaped_blanked}</div><div class='example-meta'>{meta}</div></div>")

    return {
        "POS_Definitions": "\n".join(pos_html_parts),
        "Pronunciation": "\n".join(pronunciation_parts),
        "Definition": "\n".join(definition_parts),
        "Examples": "\n".join(examples_parts),
        "Blanked_Examples": "\n".join(blanked_examples_parts)
    }

def create_anki_model(model_name: str):
    """创建或更新 Anki 的 Note Type (模型)"""
    css = """
    .card { font-family: Arial, "Helvetica Neue", Helvetica, sans-serif; font-size: 16px; text-align: left; color: #111; background: white; line-height: 1.5; padding: 12px; }
    .word-header { font-size: 34px; text-align: center; margin: 8px 0 12px 0; font-weight: 600; }
    .pos-block, .definition-block { margin-bottom: 12px; font-size: 16px; }
    .pos-title { font-size: 18px; font-weight: 600; margin-bottom: 4px; }
    .definition-en { font-size: 15px; }
    .definition-ch { color: #555; font-size: 14px; }
    .example { margin-top: 10px; padding: 8px 12px; border-radius: 8px; background: #f7f7f7; line-height: 1.5; border: 1px solid #eee; }
    .example-text { font-size: 16px; margin-bottom: 6px; }
    .example-meta { color: #666; font-size: 13px; text-align: right; }
    .example-text strong { font-weight: 700; color: #0066cc; }
    hr { margin: 15px 0; }
    
    /* 输入框样式 (用于 type card) */
    input[type=text] { font-family: inherit; font-size: 20px; text-align: center; border: 1px solid #ccc; border-radius: 5px; padding: 8px; margin-top: 20px; width: 90%; display: block; margin-left: auto; margin-right: auto; }
    
    /* 暗色模式 (Night Mode) 适配 */
    .nightMode .card { color: #f0f0f0; background: #272828; }
    .nightMode .definition-ch, .nightMode .example-meta { color: #aaa; }
    .nightMode .example-text strong { color: #5db0ff; }
    .nightMode .example { background: #3a3a3a; border: 1px solid #4f4f4f; }
    .nightMode input[type=text] { background-color: #333; color: #eee; border-color: #555; }
    """
    
    fields = ["Word", "Pronunciation", "Definition", "POS_Definitions", "Examples", "Blanked_Examples", "Tags"]
    
    # 卡片模板定义
    card_templates = [
        {
            "Name": "Basic",
            "Front": "{{Word}}<hr>{{#Examples}}{{Examples}}{{/Examples}}",
            "Back": """
                {{FrontSide}}
                <hr>
                <div class='word-header'>{{Word}}</div>
                <div class='definition-block'>{{Definition}}</div>
                <div class='pos-block'>{{Pronunciation}}</div>
                <div style='margin-top:20px;'><b>Examples:</b>{{Examples}}</div>
            """
        },
        {
            "Name": "Type",
            "Front": "{{Definition}}<div style='margin-top:20px;'>{{Blanked_Examples}}</div>{{type:Word}}",
            "Back": """
                <div class='word-header'>{{Word}}</div>
                <hr>
                <div class='definition-block'>{{Definition}}</div>
                <div class='pos-block'>{{Pronunciation}}</div>
                <div style='margin-top:20px;'><b>Examples:</b>{{Examples}}</div>
            """
        }
    ]

    print(f"正在创建模型: {model_name} ...")
    invoke(
        "createModel",
        modelName=model_name,
        inOrderFields=fields,
        css=css,
        cardTemplates=card_templates
    )

def ensure_model_and_deck(deck_name: str, model_name: str):
    """确保牌组和模型存在，不存在则创建"""
    invoke("createDeck", deck=deck_name)
    model_names = invoke("modelNames").get("result", [])
    if model_name not in model_names:
        create_anki_model(model_name)
        print(f"模型 {model_name} 创建请求已发送。")
    else:
        print(f"模型 {model_name} 已存在。")

def add_word_to_anki(deck_name: str, word: str, word_info: Dict[str, Any]):
    """将一个单词作为新笔记添加到 Anki"""
    fields = build_html_from_word_info(word_info)
    word_prototype = word_info.get("partOfSpeech")[0].get("wordPrototype", "")
    if " " in word_prototype:
        tags = "phrase"
    else:
        tags = "word"
    
    note = {
        "deckName": deck_name,
        "modelName": MODEL_NAME,
        "fields": {
            "Word": word,
            "Pronunciation": fields.get("Pronunciation", ""),
            "Definition": fields.get("Definition", ""),
            "POS_Definitions": fields.get("POS_Definitions", ""),
            "Examples": fields.get("Examples", ""),
            "Blanked_Examples": fields.get("Blanked_Examples", ""),
            "Tags": tags
        },
        "options": {"allowDuplicate": True},
        "tags": None
    }
    
    print(f"正在添加笔记: '{word}'...")
    res = invoke("addNote", note=note)
    if res and not res.get("error") and res.get("result"):
        print(f"  [成功] 笔记 '{word}' 添加成功, Note ID: {res.get('result')}")
    else:
        print(f"  [失败] 添加笔记 '{word}' 失败。可能是笔记重复或发生其他错误。")


def update_missing_fields_for_word(deck_name: str, word: str):
    """
    查找指定单词的笔记，并为其填充空的 Pronunciation, Definition, 和 Blanked_Examples 字段。
    """
    print(f"\n===== 开始更新单词: '{word}' =====")
    
    # 步骤 1: 获取单词信息
    word_info = get_word_info(word) 
    if not word_info:
        print(f"[错误] 无法获取 '{word}' 的信息，更新中止。")
        return

    # 步骤 2: 查找笔记
    query = f'deck:"{deck_name}" "Word:{word}"'
    note_ids = invoke("findNotes", query=query).get("result", [])
    if not note_ids:
        print(f"在牌组 '{deck_name}' 中未找到单词 '{word}' 的笔记。")
        return
    print(f"找到 {len(note_ids)} 个相关笔记。")

    # 步骤 3: 生成新内容
    generated_fields = build_html_from_word_info(word_info)

    # 步骤 4: 获取笔记详情并更新
    notes_info = invoke("notesInfo", notes=note_ids).get("result", [])
    for note in notes_info:
        note_id = note["noteId"]
        current_fields = note["fields"]
        fields_to_update = {}

        # 检查需要填充的字段
        fields_to_check = ["Pronunciation", "Definition", "Blanked_Examples"]
        for field_name in fields_to_check:
            if field_name in current_fields and not current_fields[field_name]["value"].strip():
                fields_to_update[field_name] = generated_fields.get(field_name, "")
        
        if fields_to_update:
            print(f"  - 准备更新笔记 ID: {note_id} (字段: {', '.join(fields_to_update.keys())})")
            update_payload = {"id": note_id, "fields": fields_to_update}
            res = invoke("updateNoteFields", note=update_payload)
            if not res.get("error"):
                print(f"    [成功] 笔记已更新。")
        else:
            print(f"  - 笔记 ID: {note_id} 无需更新。")


# ----------------- 主流程示例 -----------------
if __name__ == "__main__":
    DECK = "test" # 定义你的目标牌组
    
    # 确保牌组和模型都存在
    ensure_model_and_deck(DECK, MODEL_NAME)
    
    print("\n" + "="*40)
    print("模式1: 添加一个全新的单词笔记")
    print("="*40)
    word_to_add = "juvenile prison"
    word_info_to_add = get_word_info(word_to_add)
    if word_info_to_add:
        # 检查单词是否已存在，避免重复添加
        if not invoke("findNotes", query=f'deck:"{DECK}" "Word:{word_to_add}"').get("result"):
             add_word_to_anki(DECK, word_to_add, word_info_to_add)
        else:
             print(f"单词 '{word_to_add}' 已存在于牌组中，跳过添加。")

    
    print("\n" + "="*40)
    print("模式2: 更新一个已存在单词的空字段")
    print("="*40)
    word_to_update = "juvenile prison" 
    update_missing_fields_for_word(DECK, word_to_update)
    
    print("\n脚本执行完毕。")