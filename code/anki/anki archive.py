# -*- coding: utf-8 -*-
"""
Anki 导入脚本：将 word_info 转为 Anki note，包含词性/发音/释义/短语，并把例句（sentences）写入 Examples 字段。
要求：
- 例句在正面就显示（在显示答案之前），同时在背面答案之后也要显示；
- 例句中目标词（来自 sentence 的 text 字段）**只匹配整词**并用 <strong> 加粗（不使用背景高亮）；
- 例句来源如 "--《Elon Musk》" 靠右显示。
需要 AnkiConnect（http://localhost:8765）和已打开 Anki。
"""

import requests
import sys
import time
import html
import re
import json
from typing import Dict, List, Any

# ====== 请替换为你实际的 get_word_info 导入或定义 ======
# from my_crawler_module import get_word_info
# ======================================================

ANKI_CONNECT_URL = "http://localhost:8765"
MODEL_NAME = "WordWithExamples"
REQUEST_TIMEOUT = 10.0

def invoke(action: str, **params):
    try:
        r = requests.post(
            ANKI_CONNECT_URL,
            json={"action": action, "version": 6, "params": params},
            timeout=REQUEST_TIMEOUT
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print(f"[错误] 无法连接 AnkiConnect（{ANKI_CONNECT_URL}）：{e}")
        sys.exit(1)

def model_exists(model_name: str) -> bool:
    res = invoke("modelNames")
    if res.get("error"):
        print("[错误] 调用 modelNames 出错：", res)
        return False
    return model_name in (res.get("result") or [])

def create_word_with_examples_model(model_name: str):
    """
    创建 Note Type：简化字段：Word, POS_Definitions, Examples, Tags
    front: 显示 Word 与 Examples（使例句在答案前显示）
    back: 显示 Word, POS_Definitions（答案），然后再次显示 Examples（答案后也有例句）
    """
    css = """
.card {
  font-family: Arial, "Helvetica Neue", Helvetica, sans-serif;
  font-size: 16px;
  text-align: left;
  color: #111;
  background: white;
  line-height: 1.5;
  padding: 8px;
}
.word-header {
  font-size: 34px;
  text-align: center;
  margin: 8px 0 6px 0;
  font-weight: 600;
}
.pos-block {
  margin-bottom: 12px;
  font-size: 16px;
}
.pos-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 4px;
}
.definition-en {
  font-size: 15px;
}
.definition-ch {
  color: #666;
  font-size: 14px;
}
.phrase {
  font-style: italic;
}
.audio-row {
  margin: 4px 0;
  font-size: 14px;
}

/* 例句样式与来源靠右 */
.example {
  margin-top: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  background: #fbfbfb;
  line-height: 1.4;
}
.example-text {
  font-size: 15px;
  margin-bottom: 6px;
}
.example-meta {
  color: #666;
  font-size: 13px;
  text-align: right;  /* 来源靠右 */
}

/* 如果需要让加粗看起来更明显，可调整 strong 的样式 */
.example-text strong {
  font-weight: 700;
}
"""

    # front: Word + Examples (示例在答案前显示)
    front = r"""<div class="word-header">{{Word}}</div>
<hr>
{{#Examples}}
<div class="pos-block">{{Examples}}</div>
{{/Examples}}"""

    # back: Word + POS_Definitions（答案） + Examples（答案后再次显示）
    back = r"""<div class="word-header">{{Word}}</div>
<hr>
{{#POS_Definitions}}
<div class="pos-block">{{POS_Definitions}}</div>
{{/POS_Definitions}}

{{#Examples}}
<div style="margin-top:8px;">
  <b>Examples</b>
  <div>{{Examples}}</div>
</div>
{{/Examples}}

{{#Tags}}
<div style="margin-top:8px; color:gray; font-size:12px;">Tags: {{Tags}}</div>
{{/Tags}}"""

    fields = ["Word", "POS_Definitions", "Examples", "Tags"]
    card_templates = [
        {
            "Name": "Card 1",
            "Front": front,
            "Back": back
        }
    ]

    print(f"正在创建模型: {model_name} ...")
    res = invoke(
        "createModel",
        modelName=model_name,
        inOrderFields=fields,
        css=css,
        cardTemplates=card_templates
    )
    if res.get("error"):
        print("[错误] createModel 返回错误：", res)
    else:
        print(f"模型 {model_name} 创建请求发送成功（Anki 端可能需要短暂时间应用）。")

def build_html_from_word_info(word_info: Dict[str, Any]) -> Dict[str, str]:
    """
    将 get_word_info 的结构转换为写入字段的 HTML 字符串，
    发音（audio）放在每个词性下面（不会在顶部重复显示）。
    处理 sentences 数组：
      - 将例句写入 Examples 字段；
      - 在例句中将 target word（来自 sentence 的 text）**只匹配整词**并用 <strong> 包裹（加粗）。
    """
    pos_html_parts: List[str] = []
    examples_parts: List[str] = []

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

    # 处理例句数组（如果存在）
    for s in word_info.get("sentences", []):
        # 首选 notes，其次 sentence，其次尝试解析 cfi 中的 text，最后 fallback 到 text 字段
        sentence_text = None
        if s.get("notes"):
            sentence_text = s.get("notes")
        elif s.get("sentence"):
            sentence_text = s.get("sentence")
        else:
            cfi_raw = s.get("cfi")
            if isinstance(cfi_raw, str):
                try:
                    cfi_obj = json.loads(cfi_raw)
                    sentence_text = cfi_obj.get("text")
                except Exception:
                    sentence_text = None

        if not sentence_text:
            sentence_text = s.get("text") or ""

        if not isinstance(sentence_text, str):
            continue
        sentence_text = sentence_text.strip()
        if not sentence_text:
            continue

        # 要加粗的目标词（来自 sentence 的 text 字段）
        target = s.get("text") or ""
        escaped_sentence = html.escape(sentence_text)

        highlighted = escaped_sentence
        if target and isinstance(target, str) and target.strip():
            try:
                tgt = target.strip()
                escaped_target = html.escape(tgt)
                # 使用整词匹配；对 escaped_sentence 与 escaped_target 使用单词边界
                pattern_escaped = re.compile(r'\b' + re.escape(escaped_target) + r'\b', flags=re.IGNORECASE | re.UNICODE)
                highlighted = pattern_escaped.sub(lambda m: f"<strong>{m.group(0)}</strong>", escaped_sentence)
            except re.error:
                # 回退：不使用边界，简单替换（忽略大小写）
                escaped_target = html.escape(target.strip())
                highlighted = re.sub(re.escape(escaped_target), lambda m: f"<strong>{m.group(0)}</strong>", escaped_sentence, flags=re.IGNORECASE)

        # 来源信息（书名与章节，来源靠右显示）
        book = s.get("bookName") or s.get("book") or ""
        chapter = s.get("chapter") or s.get("chapterTitle") or ""
        meta_parts: List[str] = []
        if book:
            meta_parts.append(f"《{html.escape(book)}》")
        if chapter:
            meta_parts.append(html.escape(str(chapter)))
        meta = ""
        if meta_parts:
            meta = " — " + " ".join(meta_parts)

        examples_parts.append(
            "<div class='example'>"
            f"<div class='example-text'>{highlighted}</div>"
            f"<div class='example-meta'>{meta}</div>"
            "</div>"
        )

    pos_html = "\n".join(pos_html_parts)
    examples_html = "\n".join(examples_parts)

    return {
        "POS_Definitions": pos_html,
        "Examples": examples_html
    }

def add_word_to_anki(deck_name: str, word: str, word_info: Dict[str, Any]):
    fields = build_html_from_word_info(word_info)
    tags_field = word_info.get("tags", [])
    if isinstance(tags_field, list):
        tags_str = ", ".join(tags_field)
    else:
        tags_str = str(tags_field) if tags_field else ""
    note = {
        "deckName": deck_name,
        "modelName": MODEL_NAME,
        "fields": {
            "Word": word,
            "POS_Definitions": fields.get("POS_Definitions", ""),
            "Examples": fields.get("Examples", ""),
            "Tags": tags_str
        },
        "options": {"allowDuplicate": True},
        "tags": word_info.get("tags", []) or ["cambridge"]
    }

    res = invoke("addNote", note=note)
    # 若模型尚未被 Anki 识别，重试一次
    if res.get("error") and "model was not found" in str(res.get("error")):
        print("[警告] addNote 返回 model was not found，尝试等待并重试...")
        time.sleep(1.0)
        if not model_exists(MODEL_NAME):
            print("[错误] 模型仍然不存在，添加失败：", res)
            return res
        res = invoke("addNote", note=note)
    return res

def ensure_model_and_deck(deck_name: str):
    invoke("createDeck", deck=deck_name)
    if not model_exists(MODEL_NAME):
        create_word_with_examples_model(MODEL_NAME)
        # 等待模型被 Anki 端应用
        for i in range(10):
            time.sleep(0.4)
            if model_exists(MODEL_NAME):
                print(f"模型 {MODEL_NAME} 已创建并可用。")
                break
        else:
            print(f"[错误] 等待模型创建超时，请检查 Anki 端是否有错误提示。")
    else:
        print(f"模型 {MODEL_NAME} 已存在，跳过创建。")

import html
import re
import json
from typing import Dict, Any, List, Tuple

def _format_sentence_html_and_plain(s: Dict[str, Any]) -> Tuple[str, str]:
    """
    将单个 sentence 对象格式化为 Examples 字段中对应的 HTML 块，
    并返回 (html_block, plain_sentence_text) 其中 plain_sentence_text 用于去重比较。
    采用与之前相同的规则优先使用 notes -> sentence -> cfi.text -> text。
    句子中目标词（s['text']）用 <strong> 包裹，匹配整词（\b）。
    """
    # 获取整句文本（优先级 notes > sentence > cfi.text > text）
    sentence_text = None
    if s.get("notes"):
        sentence_text = s.get("notes")
    elif s.get("sentence"):
        sentence_text = s.get("sentence")
    else:
        cfi_raw = s.get("cfi")
        if isinstance(cfi_raw, str):
            try:
                cfi_obj = json.loads(cfi_raw)
                sentence_text = cfi_obj.get("text")
            except Exception:
                sentence_text = None
    if not sentence_text:
        sentence_text = s.get("text") or ""
    if not isinstance(sentence_text, str):
        sentence_text = str(sentence_text)

    sentence_text = sentence_text.strip()
    if not sentence_text:
        return ("", "")

    # target word
    target = s.get("text") or ""
    escaped_sentence = html.escape(sentence_text)

    highlighted = escaped_sentence
    if target and isinstance(target, str) and target.strip():
        try:
            tgt = target.strip()
            escaped_target = html.escape(tgt)
            # 使用整词边界匹配已 escape 的目标（对 escaped_sentence 进行替换）
            pattern_escaped = re.compile(r'\b' + re.escape(escaped_target) + r'\b', flags=re.IGNORECASE | re.UNICODE)
            highlighted = pattern_escaped.sub(lambda m: f"<strong>{m.group(0)}</strong>", escaped_sentence)
        except re.error:
            escaped_target = html.escape(target.strip())
            highlighted = re.sub(re.escape(escaped_target), lambda m: f"<strong>{m.group(0)}</strong>", escaped_sentence, flags=re.IGNORECASE)

    # 来源信息
    book = s.get("bookName") or s.get("book") or ""
    chapter = s.get("chapter") or s.get("chapterTitle") or ""
    meta_parts: List[str] = []
    if book:
        meta_parts.append(f"《{html.escape(book)}》")
    if chapter:
        meta_parts.append(html.escape(str(chapter)))
    meta = ""
    if meta_parts:
        meta = " — " + " ".join(meta_parts)

    html_block = (
        "<div class='example'>"
        f"<div class='example-text'>{highlighted}</div>"
        f"<div class='example-meta'>{meta}</div>"
        "</div>"
    )
    # plain text 用于去重（不含 HTML，原始句子）
    plain = sentence_text
    return (html_block, plain)


def _extract_existing_example_plaintexts(existing_examples_html: str) -> List[str]:
    """
    从已有 Examples 字段的 HTML 中提取所有 <div class='example-text'>...</div> 的纯文本（去标签、unescape）。
    返回文本列表（顺序与出现顺序一致）。
    """
    if not existing_examples_html:
        return []
    # 找到所有 example-text 段落
    matches = re.findall(r"<div\s+class=['\"]example-text['\"]\s*>(.*?)</div>", existing_examples_html, flags=re.S | re.I)
    plain_texts = []
    for m in matches:
        # 去掉 HTML 标签（如 <strong> 等）
        no_tags = re.sub(r"<[^>]+>", "", m)
        unescaped = html.unescape(no_tags).strip()
        if unescaped:
            plain_texts.append(unescaped)
    # 备用：如果没有找到匹配，作为降级处理尝试从整段 HTML 提取纯文本并按行分割
    if not plain_texts:
        all_text = re.sub(r"<[^>]+>", "", existing_examples_html)
        all_text = html.unescape(all_text).strip()
        if all_text:
            # 用换行或句点粗略分割
            parts = [p.strip() for p in re.split(r'\n+|(?<=\.)\s+', all_text) if p.strip()]
            plain_texts.extend(parts)
    return plain_texts


def upsert_sentences_into_deck(deck_name: str,
                              word_info: Dict[str, Any],
                              update_all: bool = True,
                              dedupe: bool = True,
                              limit: int = None) -> Dict[str, Any]:
    """
    主函数：
    - deck_name: 目标牌组名称
    - word_info: 你的词条结构（包含 Word 或 可从 partOfSpeech 中推断的词）
    - update_all: 如果在牌组中找到多条 note，是否更新所有（True）或只更新第一条（False）
    - dedupe: 是否按纯句子文本去重（默认 True）
    - limit: 如果希望最多添加的句子数，设置为 int；None 表示不限制
    返回：字典，包含 created/updated/skipped/errors 等信息
    """
    result = {"created": False, "created_note_result": None, "updated": [], "skipped": [], "errors": []}

    # 确定单词（优先使用 word_info 中的明确字段）
    word = word_info.get("word") or word_info.get("Word") or ""
    if not word:
        # 退回到 partOfSpeech[0].wordPrototype
        pos_list = word_info.get("partOfSpeech") or []
        if pos_list and isinstance(pos_list, list) and pos_list[0].get("wordPrototype"):
            word = pos_list[0].get("wordPrototype")
    if not word:
        result["errors"].append("无法从 word_info 中推断单词（缺少 'word' 或 partOfSpeech[0].wordPrototype）。")
        return result

    # 查找 note ids
    query = f'deck:"{deck_name}" "Word:{word}"'
    try:
        find_res = invoke("findNotes", query=query)
    except Exception as e:
        result["errors"].append(f"findNotes 调用异常: {e}")
        return result

    if find_res.get("error"):
        result["errors"].append(f"findNotes 返回错误: {find_res}")
        return result

    note_ids = find_res.get("result", []) or []

    # 如果没找到 note -> 创建新的 note（完整添加）
    if not note_ids:
        try:
            add_res = add_word_to_anki(deck_name, word, word_info)
            result["created"] = True
            result["created_note_result"] = add_res
        except Exception as e:
            result["errors"].append(f"add_word_to_anki 异常: {e}")
        return result

    # 如果找到了 note，准备把 sentences 转为 HTML 块列表
    sentences = word_info.get("sentences") or []
    formatted: List[Tuple[str, str]] = []
    for s in sentences:
        html_block, plain = _format_sentence_html_and_plain(s)
        if html_block and plain:
            formatted.append((html_block, plain))
    if not formatted:
        result["skipped"].append("word_info 中没有有效的 sentences 可添加。")
        return result

    # 如果 limit 存在，截断 formatted
    if limit is not None:
        formatted = formatted[:limit]

    # 更新匹配到的 notes（全部或仅第一条）
    target_note_ids = note_ids if update_all else note_ids[:1]
    for nid in target_note_ids:
        try:
            info_res = invoke("notesInfo", notes=[nid])
        except Exception as e:
            result["errors"].append(f"notesInfo({nid}) 调用异常: {e}")
            continue
        if info_res.get("error"):
            result["errors"].append(f"notesInfo 错误 for {nid}: {info_res}")
            continue
        info_list = info_res.get("result") or []
        if not info_list:
            result["errors"].append(f"notesInfo 返回空结果 for {nid}")
            continue
        info = info_list[0]
        # 取得现有 Examples 字段（如果存在）
        existing_examples_html = ""
        try:
            existing_examples_html = info.get("fields", {}).get("Examples", {}).get("value", "") or ""
        except Exception:
            existing_examples_html = ""

        existing_plain_texts = _extract_existing_example_plaintexts(existing_examples_html) if existing_examples_html else []

        # 构造新的 Examples 内容（在末尾追加未去重的 items）
        new_adds_html = []
        added_count = 0
        for html_block, plain in formatted:
            if dedupe and any(plain == ex for ex in existing_plain_texts):
                result["skipped"].append({"note_id": nid, "sentence": plain})
                continue
            # 还需防止同一 run 中重复添加多个相同句子：也和 new_adds_html 的 plain 比较
            if dedupe and any(plain == re.sub(r'<[^>]+>', '', html.unescape(re.sub(r"^.*?>(.*)$", r"\1", nb))) for nb, _ in new_adds_html):
                # 这里为保险措施（实际上 new_adds_html 存放 html，需要提取 plain；为简洁我们直接用 plain comparisons below）
                pass
            new_adds_html.append((html_block, plain))
            existing_plain_texts.append(plain)  # 防止同 run 重复
            added_count += 1
            if limit is not None and added_count >= limit:
                break

        if not new_adds_html:
            # 没有要添加的句子
            result["updated"].append({"note_id": nid, "added": 0})
            continue

        # 将新块拼接到现有 Examples 字段（直接字符串连接）
        appended_html = "".join([nb for nb, _ in new_adds_html])
        new_examples_field = (existing_examples_html or "") + appended_html

        # 执行 updateNoteFields
        try:
            upd = invoke("updateNoteFields", note={"id": nid, "fields": {"Examples": new_examples_field}})
            # 记录结果
            result["updated"].append({"note_id": nid, "added": len(new_adds_html), "update_result": upd})
        except Exception as e:
            result["errors"].append(f"updateNoteFields({nid}) 异常: {e}")

    return result




# ----------------- 主流程示例 -----------------
if __name__ == "__main__":
    deck = "CambridgeDeck"
    ensure_model_and_deck(deck)

    # 尝试调用 get_word_info；如果不存在则使用示例数据进行演示
    try:
        word = "recount"
        word_info = get_word_info(word)  # 请确保 get_word_info 在当前作用域可用
    except NameError:
        print("[提示] 未找到 get_word_info 函数，使用内置示例数据进行演示。")
        word = "juvenile prison"
        word_info = {
    "wordUrl": "",
    "partOfSpeech": [
      {
        "type": "",
        "wordPrototype": "juvenile prison",
        "pronunciationUK": {
          "phonetic": "",
          "pronUrl": ""
        },
        "pronunciationUS": {
          "phonetic": "",
          "pronUrl": ""
        },
        "definitions": [
          {
            "enMeaning": "",
            "chMeaning": "青少年监狱"
          }],
        "phrases": [],
        "phraseDefinitions": []
      }
    ],
    "sentences": [
      {
        "key": 1758084501416,
        "bookKey": 1738143464138,
        "date": "2025-09-17",
        "chapter": "Cover",
        "chapterIndex": 5,
        "text": "juvenile prison",
        "cfi": "{\"text\":\"When Elon finally came home from the hospital, his father berated him. “I had to stand for an hour as he yelled at me and called me an idiot and told me that I was just worthless,” Elon recalls. Kimbal, who had to watch the tirade, says it was the worst memory of his life. “My father just lost it, went ballistic, as he often did. He had zero compassion.”\",\"chapterTitle\":\"\",\"chapterDocIndex\":\"5\",\"chapterHref\":\"\",\"count\":\"10\",\"percentage\":\"0.02512562814070352\",\"page\":\"\"}",
        "range": "{\"characterRange\":{\"start\":4574,\"end\":4589},\"backward\":false}",
        "notes": "Both Elon and Kimbal, who no longer speak to their father, say his claim that Elon provoked the attack is unhinged and that the perpetrator ended up being sent to juvenile prison for it.",
        "percentage": 0.0,
        "color": "#FBF1D1",
        "tag": "",
        "highlightType": "background",
        "bookName": "Elon Musk",
        "bookAuthor": "Walter Isaacson"
      }
    ]
  }
    print(f"导入单词 {word} ...")
    result = add_word_to_anki(deck, word, word_info)
    print("AnkiConnect 返回：", result)

    # word_info["sentences"][0]["notes"] += "NEW"
    # out = upsert_sentences_into_deck("CambridgeDeck", word_info, update_all=True, dedupe=True, limit=None)
    # print(out)