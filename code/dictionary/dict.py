# %% [markdown]
# 以下函数通过爬虫cambridge，获得单词信息，转化为dict保存。

# %%
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Set, Tuple
import time
import re

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/100.0.4896.127 Safari/537.36"
}

default_part_of_speech = {
    "type": "",
    "wordPrototype": "",
    "pronunciationUK": {"phonetic": "", "pronUrl": ""},
    "pronunciationUS": {"phonetic": "", "pronUrl": ""},
    "definitions": [],
    "phrases": [],
    "phraseDefinitions": []
}

SPELLING_OF_PATTERN = re.compile(
    r"\b(?:mainly\s+)?(?:US|UK|British|American|Australian|Canadian)?\s*spelling of\s+([A-Za-z][A-Za-z\- '\u2019]{0,80})",
    re.IGNORECASE
)


def fetch_html(url: str, headers: Optional[Dict] = None, timeout: int = 10) -> Optional[str]:
    headers = headers or DEFAULT_HEADERS
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        # 可以根据需要打印或记录日志
        # print(f"fetch_html error for {url}: {e}")
        return None


def _abs_audio_url(src: Optional[str]) -> str:
    if not src:
        return ""
    if src.startswith("http://") or src.startswith("https://"):
        return src
    # 一般页面的 src 以 / 为开头
    return "https://dictionary.cambridge.org" + src


def _text_or_empty(elem) -> str:
    """
    从 bs4 元素安全提取文本：
    - 在不同子节点之间使用单个空格分隔（避免 'word1' + 'word2' 被连成 'word1word2'）
    - 去除首尾空白，折叠连续空白（包括不间断空格 \xa0）
    """
    if not elem:
        return ""
    # 在子节点之间插入空格，strip=True 去除首尾空白
    text = elem.get_text(separator=' ', strip=True)
    # 折叠任意连续空白（空格、制表、换行、\xa0等）为单个普通空格
    text = ' '.join(text.split())
    return text

def parse_idiom_block(entry) -> Dict:
    """
    解析 idiom-block（或类似结构），返回包含 wordPrototype/type/definitions/examples 的字典。
    definitions: List[{"enMeaning": str, "chMeaning": str}]
    examples: List[{"en": str, "ch": str}]
    """
    pos: Dict = {
        "type": "",
        "wordPrototype": "",
        "pronunciationUK": {"phonetic": "", "pronUrl": ""},
        "pronunciationUS": {"phonetic": "", "pronUrl": ""},
        "definitions": [],   # 每项: {"enMeaning": "...", "chMeaning": "..."}
        "phrases": [],
        "phraseDefinitions": []
    }

    # 词头（原型）—— snippet 中 headword 在 h2.headword ... <b>on track</b>
    headword = entry.select_one(".headword.dhw, .headword")
    # 有时词头被包在 <b> 内
    if headword:
        b = headword.select_one("b")
        pos["wordPrototype"] = _text_or_empty(b) if b else _text_or_empty(headword)
    else:
        pos["wordPrototype"] = ""

    # 词性（type），在 snippet 中是 <span class="pos dpos">
    pos_tag = entry.select_one(".pos.dpos, .pos")
    pos["type"] = _text_or_empty(pos_tag)

    # 解析 definitions（排除短语块中的定义）
    for ddef in entry.select("div.def-block.ddef_block, div.def-block.ddef_block "):
        # 如果这个 ddef 在 phrase-block 内则跳过
        if ddef.find_parent(class_="phrase-block"):
            continue

        en_def_el = ddef.select_one(".def.ddef_d.db, .def.ddef_d")
        en_def = _text_or_empty(en_def_el)

        # 找中文释义，优先选 .trans.dtrans.dtrans-se 且不属于 .hdb
        ch_text = ""
        ch_candidates = ddef.select(".trans.dtrans.dtrans-se, .trans.dtrans")
        if ch_candidates:
            for ch in ch_candidates:
                # 跳过属于 .hdb 的（通常是隐藏类或次要翻译）
                if ch.find_parent(class_="hdb"):
                    continue
                # 跳过空的
                txt = _text_or_empty(ch)
                if txt:
                    ch_text = txt
                    break
            # 如果都被跳过，取第一个非空的备选
            if not ch_text:
                for ch in ch_candidates:
                    txt = _text_or_empty(ch)
                    if txt:
                        ch_text = txt
                        break
        pos["definitions"].append({"enMeaning": en_def, "chMeaning": ch_text})

    return pos




def _new_part_of_speech() -> Dict:
    """创建一个空的 part-of-speech 结构。"""
    return {
        "type": "",
        "wordPrototype": "",
        "pronunciationUK": {"phonetic": "", "pronUrl": ""},
        "pronunciationUS": {"phonetic": "", "pronUrl": ""},
        "definitions": [],
        "phrases": [],
        "phraseDefinitions": []
    }


def _is_non_empty_pos(pos: Dict) -> bool:
    """判断词性结构是否包含有效内容。"""
    return bool(pos.get("wordPrototype") or pos.get("definitions") or pos.get("phrases"))


def _clean_spelling_target(raw: str) -> str:
    """清洗 'spelling of xxx' 中提取到的目标词。"""
    if not raw:
        return ""
    target = " ".join(raw.split())
    # 去掉尾部的地区标签（如 UK/US/British）
    target = re.sub(r"\b(?:UK|US|British|American|Australian|Canadian)\b\s*$", "", target, flags=re.IGNORECASE).strip()
    # 仅保留常见单词字符，避免把解释文本一并抓进来
    target = re.sub(r"[^A-Za-z\- '\u2019]", "", target).strip(" -")
    return target


def _extract_spelling_targets(part_of_speech: List[Dict], source_word: str) -> List[str]:
    """
    从释义中提取 'US/UK spelling of xxx' 的目标词。
    保留顺序并去重。
    """
    source_l = (source_word or "").strip().lower()
    targets: List[str] = []
    seen: Set[str] = set()

    for pos in part_of_speech or []:
        for ddef in pos.get("definitions", []) or []:
            en = (ddef.get("enMeaning") or ddef.get("en") or "").strip()
            if not en:
                continue
            normalized = " ".join(en.split())
            match = SPELLING_OF_PATTERN.search(normalized)
            if not match:
                continue
            target = _clean_spelling_target(match.group(1))
            if not target:
                continue
            key = target.lower()
            if key == source_l or key in seen:
                continue
            seen.add(key)
            targets.append(target)

    return targets


def _pos_signature(pos: Dict) -> Tuple:
    """用于判断两个 part-of-speech 是否相同的签名。"""
    defs = tuple(
        sorted(
            (
                (d.get("enMeaning") or d.get("en") or "").strip(),
                (d.get("chMeaning") or d.get("ch") or "").strip()
            )
            for d in (pos.get("definitions") or [])
        )
    )
    phrase_defs = tuple(
        sorted(
            (
                (d.get("enMeaning") or d.get("en") or "").strip(),
                (d.get("chMeaning") or d.get("ch") or "").strip()
            )
            for d in (pos.get("phraseDefinitions") or [])
        )
    )
    phrases = tuple(sorted(((p or "").strip() for p in (pos.get("phrases") or []))))
    return (
        (pos.get("type") or "").strip(),
        (pos.get("wordPrototype") or "").strip(),
        defs,
        phrases,
        phrase_defs,
    )


def _merge_part_of_speech(base_parts: List[Dict], extra_parts: List[Dict]) -> None:
    """将 extra_parts 合并到 base_parts，避免重复项。"""
    seen = {_pos_signature(p) for p in base_parts if _is_non_empty_pos(p)}
    for p in extra_parts or []:
        if not _is_non_empty_pos(p):
            continue
        sig = _pos_signature(p)
        if sig in seen:
            continue
        seen.add(sig)
        base_parts.append(dict(p))


def _nearest_pos_body(node):
    """
    返回节点最近的 .pos-body 祖先（如果存在）。
    用于避免外层 pos-body 误抓到内层 pos-body 的 definition。
    """
    if not node:
        return None
    return node.find_parent(
        lambda tag: tag.name == "div" and "pos-body" in (tag.get("class") or [])
    )


def _parse_pos_block(meta_scope, content_scope, fallback_headword: str = "") -> Dict:
    """
    解析一个词性区块。
    - meta_scope: 词头/词性/发音优先来源（通常是 .pos-header）
    - content_scope: 释义/短语来源（通常是 .pos-body）
    """
    pos: Dict = _new_part_of_speech()
    meta_scope = meta_scope or content_scope

    # word prototype & type
    headword = meta_scope.select_one(".headword.dhw, .headword") if meta_scope else None
    if not headword and content_scope is not meta_scope:
        headword = content_scope.select_one(".headword.dhw, .headword")
    pos["wordPrototype"] = _text_or_empty(headword) or fallback_headword
    posgram = meta_scope.select_one(".posgram.dpos-g.hdib.lmr-5, .posgram.dpos-g, .posgram") if meta_scope else None
    if not posgram and content_scope is not meta_scope:
        posgram = content_scope.select_one(".posgram.dpos-g.hdib.lmr-5, .posgram.dpos-g, .posgram")
    pos["type"] = _text_or_empty(posgram)

    # UK pronunciation
    uk = meta_scope.select_one(".uk.dpron-i") if meta_scope else None
    if not uk and content_scope is not meta_scope:
        uk = content_scope.select_one(".uk.dpron-i")
    if uk:
        phon = uk.select_one(".pron.dpron")
        pos["pronunciationUK"]["phonetic"] = _text_or_empty(phon)
        src = None
        src_tag = uk.select_one('audio source[type="audio/mpeg"]')
        if src_tag:
            src = src_tag.get("src")
        pos["pronunciationUK"]["pronUrl"] = _abs_audio_url(src)

    # US pronunciation
    us = meta_scope.select_one(".us.dpron-i") if meta_scope else None
    if not us and content_scope is not meta_scope:
        us = content_scope.select_one(".us.dpron-i")
    if us:
        phon = us.select_one(".pron.dpron")
        pos["pronunciationUS"]["phonetic"] = _text_or_empty(phon)
        src = None
        src_tag = us.select_one('audio source[type="audio/mpeg"]')
        if src_tag:
            src = src_tag.get("src")
        pos["pronunciationUS"]["pronUrl"] = _abs_audio_url(src)

    # definitions (exclude those inside phrase-block)
    for ddef in content_scope.select("div.def-block.ddef_block"):
        # 仅处理“最近 pos-body 就是当前 content_scope”的 definition，
        # 避免把嵌套词性块（如 Verb）混进当前词性（如 Noun）。
        if _nearest_pos_body(ddef) is not content_scope:
            continue
        # 判断是否在短语块中
        if ddef.find_parent(class_="phrase-block"):
            continue
        en_def = _text_or_empty(ddef.select_one(".def.ddef_d.db"))
        # 中文释义选择器尽量模仿原选择器： .trans.dtrans.dtrans-se 且不属于 .hdb
        ch_candidates = ddef.select(".trans.dtrans.dtrans-se")
        ch_text = ""
        if ch_candidates:
            # 取第一个不在 .hdb 中的
            for ch in ch_candidates:
                if ch.find_parent(class_="hdb"):
                    continue
                ch_text = _text_or_empty(ch)
                if ch_text:
                    break
        else:
            # 退而求其次：找任意 .trans.dtrans
            ch = ddef.select_one(".trans.dtrans")
            ch_text = _text_or_empty(ch) if ch else ""
        pos["definitions"].append({"enMeaning": en_def, "chMeaning": ch_text})

    # phrases and phrase definitions
    for phrase_block in content_scope.select(".phrase-block.dphrase-block, .phrase-block"):
        # 同样限制在当前 pos-body 归属范围内，避免跨词性污染。
        if _nearest_pos_body(phrase_block) is not content_scope:
            continue
        # phrase title
        phrase_title = _text_or_empty(phrase_block.select_one(".phrase-head.dphrase_h .phrase-title"))
        if phrase_title:
            pos["phrases"].append(phrase_title)

        # phrase defs
        for phrase_def_block in phrase_block.select(".def-block.ddef_block"):
            en_phrase_def = _text_or_empty(phrase_def_block.select_one(".def.ddef_d.db"))
            # 中文释义：排除包含 example 的部分（原 JS .not('.examp')）
            ch_candidates = phrase_def_block.select(".trans.dtrans")
            ch_text = ""
            if ch_candidates:
                for ch in ch_candidates:
                    # 如果包含 examp 类或包含示例标记则跳过
                    if "examp" in (ch.get("class") or []):
                        continue
                    ch_text = _text_or_empty(ch)
                    if ch_text:
                        break
            pos["phraseDefinitions"].append({"enMeaning": en_phrase_def, "chMeaning": ch_text})

    return pos


def parse_entry_body(entry) -> List[Dict]:
    """
    解析单个 .entry-body__el，返回 PartOfSpeech 列表。
    重点：按每个 pos-body 分段，避免把不同词性的 definition 混在一起。
    """
    pos_list: List[Dict] = []
    fallback_headword = _text_or_empty(entry.select_one(".headword.dhw, .headword"))

    # Cambridge 的一个 entry 可能包含多个 pos-body（如同词包含 noun + verb）。
    pos_bodies = entry.select(".pos-body")
    if pos_bodies:
        for body in pos_bodies:
            header = body.find_previous_sibling(
                lambda tag: tag.name == "div" and "pos-header" in (tag.get("class") or [])
            )
            pos_dict = _parse_pos_block(header if header else entry, body, fallback_headword)
            if _is_non_empty_pos(pos_dict):
                pos_list.append(pos_dict)
        if pos_list:
            return pos_list

    # 兼容旧结构：没有显式 pos-body 时，回退到整块解析。
    fallback_pos = _parse_pos_block(entry, entry, fallback_headword)
    if _is_non_empty_pos(fallback_pos):
        pos_list.append(fallback_pos)
    return pos_list

def _merge_pronunciations_from_english(ch_res: Dict, en_res: Dict) -> Dict:
    """
    将英文页面的 pronunciation 覆盖到中文页面抓取结果上。
    匹配策略：先按 wordPrototype 精确匹配；匹配不到则按索引对齐。
    返回修改后的 ch_res（不产生新参照）。
    """
    if not ch_res or not en_res:
        return ch_res

    ch_parts = ch_res.get("partOfSpeech", [])
    en_parts = en_res.get("partOfSpeech", [])
    if not ch_parts or not en_parts:
        return ch_res

    # 建 index by wordPrototype for english parts
    en_by_proto = {}
    for idx, p in enumerate(en_parts):
        proto = p.get("wordPrototype", "")
        if proto:
            # 若重复 proto 则保留第一个
            if proto not in en_by_proto:
                en_by_proto[proto] = p

    # 尝试按 prototype 覆盖
    used_en_indices = set()
    for i, ch_p in enumerate(ch_parts):
        proto = ch_p.get("wordPrototype", "")
        matched = None
        if proto and proto in en_by_proto:
            matched = en_by_proto[proto]
        else:
            # fallback: try to use same-index english part
            if i < len(en_parts):
                matched = en_parts[i]
        if matched:
            # 如果英文页有非空 pronunciation 字段则覆盖
            uk = matched.get("pronunciationUK", {}) or {}
            us = matched.get("pronunciationUS", {}) or {}
            # 只有当英文页面提供了 phonetic 才覆盖（避免用空覆盖）
            if uk.get("phonetic"):
                ch_p["pronunciationUK"]["phonetic"] = uk.get("phonetic", "")
            if uk.get("pronUrl"):
                ch_p["pronunciationUK"]["pronUrl"] = uk.get("pronUrl", "")
            if us.get("phonetic"):
                ch_p["pronunciationUS"]["phonetic"] = us.get("phonetic", "")
            if us.get("pronUrl"):
                ch_p["pronunciationUS"]["pronUrl"] = us.get("pronUrl", "")

    return ch_res


def get_word_info_from_url(url: str, sleep: float = 0.0) -> Dict:
    """
    解析指定 Cambridge Dictionary 页面（完整 URL），返回嵌套 dict 结构。
    """
    html = fetch_html(url)
    if sleep:
        time.sleep(sleep)
    if not html:
        return {"wordUrl": url, "partOfSpeech": [default_part_of_speech.copy()]}

    soup = BeautifulSoup(html, "lxml")
    result = {"wordUrl": url, "partOfSpeech": []}

    # 遍历每个 entry-body__el
    entry_elems = soup.select(".entry-body__el")
    if len(entry_elems):
        for entry_el in entry_elems:
            pos_list = parse_entry_body(entry_el)
            for pos_dict in pos_list:
                if _is_non_empty_pos(pos_dict):
                    # push a shallow copy to avoid引用
                    result["partOfSpeech"].append(dict(pos_dict))
    # 仅解析真正的 idiom block，避免把整个 .di-body（二次包含所有词性）重复抓取。
    idiom_elems = soup.select(".idiom-block.didiom-block, .didiom-block, .idiom-block")
    if len(idiom_elems):
        for entry_idiom in idiom_elems:
            pos_dict = parse_idiom_block(entry_idiom)
            if pos_dict.get("wordPrototype") or pos_dict.get("definitions") or pos_dict.get("phrases"):
                # push a shallow copy to avoid引用
                result["partOfSpeech"].append(dict(pos_dict))
    return result


def get_word_info_by_word(
    word: str,
    sleep: float = 0.0,
    _visited: Optional[Set[str]] = None,
    _depth: int = 0,
    _max_spelling_expand_depth: int = 1
) -> Dict:
    """
    用单词尝试两个可能的 Cambridge Dictionary 路径，返回第一个包含有效内容的 page results。
    """
    query_word = (word or "").strip()
    if not query_word:
        return {"wordUrl": "", "partOfSpeech": [default_part_of_speech.copy()]}

    if _visited is None:
        _visited = set()
    lower_word = query_word.lower()
    if lower_word in _visited:
        return {"wordUrl": "", "partOfSpeech": [default_part_of_speech.copy()]}
    _visited.add(lower_word)

    url_list = [
        f"https://dictionary.cambridge.org/dictionary/english-chinese-simplified/{query_word}",
        f"https://dictionary.cambridge.org/dictionary/english/{query_word}"
    ]
    for url in url_list:
        res = get_word_info_from_url(url, sleep=sleep)
        # 判断是否抓取到有用内容：至少有一个非空的 partOfSpeech
        if res.get("partOfSpeech"):
            # 确认不是仅包含 default placeholder
            non_empty = any(
                (p.get("wordPrototype") or p.get("definitions") or p.get("phrases"))
                for p in res["partOfSpeech"]
            )
            if non_empty:
                # 处理类似“US spelling of litre”的词条：
                # 保留原结果，并补抓指向词（如 litre）的完整释义。
                if _depth < _max_spelling_expand_depth:
                    targets = _extract_spelling_targets(res.get("partOfSpeech", []), query_word)
                    for target in targets:
                        extra = get_word_info_by_word(
                            target,
                            sleep=sleep,
                            _visited=_visited,
                            _depth=_depth + 1,
                            _max_spelling_expand_depth=_max_spelling_expand_depth
                        )
                        _merge_part_of_speech(
                            res["partOfSpeech"],
                            extra.get("partOfSpeech", [])
                        )
                return res
    # 都没有抓到有效信息，返回占位
    return {"wordUrl": "", "partOfSpeech": [default_part_of_speech.copy()]}


def get_word_info(word_or_url: str, sleep: float = 1.0) -> Dict:
    """
    通用入口：如果输入包含 'http' 则按 URL 解析，否则按单词尝试多个 URL。
    返回值结构示例：
    {
        "wordUrl": "...",
        "partOfSpeech": [
            {
                "type": "...",
                "wordPrototype": "...",
                "pronunciationUK": {"phonetic": "...", "pronUrl": "..."},
                "pronunciationUS": {"phonetic": "...", "pronUrl": "..."},
                "definitions": [{"enMeaning": "...", "chMeaning": "..."}, ...],
                "phrases": ["..."],
                "phraseDefinitions": [{"enMeaning": "...", "chMeaning": "..."}]
            }, ...
        ]
    }
    """
    if word_or_url.startswith("http://") or word_or_url.startswith("https://"):
        return get_word_info_from_url(word_or_url, sleep=sleep)
    else:
        return get_word_info_by_word(word_or_url, sleep=sleep)


# Example usage:
if __name__ == "__main__":
    # 单词形式
    res1 = get_word_info("methane")
    print("By word:", res1)

    # 或直接用 URL
    # res2 = get_word_info("https://dictionary.cambridge.org/dictionary/english/methane")
    # print("By URL:", res2)
