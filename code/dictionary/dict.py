# %% [markdown]
# 以下函数通过爬虫cambridge，获得单词信息，转化为dict保存。

# %%
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import time

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
        "definitions": [],   # 每项: {"enMeaning": "...", "chMeaning": "..."}
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




def parse_entry_body(entry) -> Dict:
    """解析单个 .entry-body__el，返回 PartOfSpeech 的字典表示"""
    pos: Dict = {
        "type": "",
        "wordPrototype": "",
        "pronunciationUK": {"phonetic": "", "pronUrl": ""},
        "pronunciationUS": {"phonetic": "", "pronUrl": ""},
        "definitions": [],
        "phrases": [],
        "phraseDefinitions": []
    }

    # word prototype & type
    headword = entry.select_one(".headword.dhw")
    pos["wordPrototype"] = _text_or_empty(headword)
    posgram = entry.select_one(".posgram.dpos-g.hdib.lmr-5")
    pos["type"] = _text_or_empty(posgram)

    # UK pronunciation
    uk = entry.select_one(".uk.dpron-i")
    if uk:
        phon = uk.select_one(".pron.dpron")
        pos["pronunciationUK"]["phonetic"] = _text_or_empty(phon)
        src = None
        src_tag = uk.select_one('audio source[type="audio/mpeg"]')
        if src_tag:
            src = src_tag.get("src")
        pos["pronunciationUK"]["pronUrl"] = _abs_audio_url(src)

    # US pronunciation
    us = entry.select_one(".us.dpron-i")
    if us:
        phon = us.select_one(".pron.dpron")
        pos["pronunciationUS"]["phonetic"] = _text_or_empty(phon)
        src = None
        src_tag = us.select_one('audio source[type="audio/mpeg"]')
        if src_tag:
            src = src_tag.get("src")
        pos["pronunciationUS"]["pronUrl"] = _abs_audio_url(src)

    # definitions (exclude those inside phrase-block)
    for ddef in entry.select("div.def-block.ddef_block"):
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
    for phrase_block in entry.select(".phrase-block.dphrase-block"):
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
            pos_dict = parse_entry_body(entry_el)
            # 仅当至少有 headword 或 definitions 时认为有效
            if pos_dict["wordPrototype"] or pos_dict["definitions"] or pos_dict["phrases"]:
                # push a shallow copy to avoid引用
                result["partOfSpeech"].append(dict(pos_dict))
    di_elems = soup.select(".di-body")
    if len(di_elems):
        for entry_idiom in di_elems:
            pos_dict = parse_idiom_block(entry_idiom)
            if pos_dict["wordPrototype"] or pos_dict["definitions"] or pos_dict["phrases"]:
                # push a shallow copy to avoid引用
                result["partOfSpeech"].append(dict(pos_dict))
    return result


def get_word_info_by_word(word: str, sleep: float = 0.0) -> Dict:
    """
    用单词尝试两个可能的 Cambridge Dictionary 路径，返回第一个包含有效内容的 page results。
    """
    url_list = [
        f"https://dictionary.cambridge.org/dictionary/english-chinese-simplified/{word}",
        f"https://dictionary.cambridge.org/dictionary/english/{word}"
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



