import sys
import os
import json
from datetime import datetime
from pathlib import Path

# 把上级目录加到 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tqdm import tqdm

from anki import anki
from dictionary import dict as dict_
from vcs import vcs
from save import save
from info import info
from NLP import NLP

# ---------- 配置 ----------
deck = "Word"
anki.ensure_model_and_deck(deck, model_name="WordType")

CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "cache"))
CACHE_FILE = os.path.join(CACHE_DIR, "empty_cache.json")
Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)

# ---------- 辅助函数 ----------

def load_cache():
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def save_cache(cache):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def is_wordinfo_empty(word_info):
    pos = word_info.get("partOfSpeech", [])
    if isinstance(pos, list):
        for p in pos:
            if isinstance(p, dict) and p.get("wordPrototype", None) == "":
                return True
    return False


# ---------- step1: 遍历../../data/source中所有csv，转化为list[dict] ----------
word_dict_list = vcs.get_csv_info(vcs.get_csv_path(dir_path="../../data/source"))

# ---------- step2: 加载旧的dict list & 合并去重 ----------
old_word_dict_list = save.load_latest_dict_list(folder="../../data/backup/notes")
full_word_dict_list = save.merge_and_deduplicate(old_list=old_word_dict_list, new_list=word_dict_list)
new_word_dict_list = save.diff_new_vs_old(old_word_dict_list, word_dict_list)

# 去掉text两边的空格
for new_word_dict in new_word_dict_list:
    if isinstance(new_word_dict.get('text'), str):
        new_word_dict['text'] = new_word_dict['text'].strip()
    if isinstance(new_word_dict.get('notes'), str):
        new_word_dict['notes'] = new_word_dict['notes'].strip()

# ---------- step3: 查询单词信息，构建 new_word_info_list ----------
old_word_info_list = save.load_latest_dict_list(folder="../../data/backup/info")

new_word_info_list = []
for new_word_dict in tqdm(new_word_dict_list, desc="处理单词", unit="词"):
    new_word = new_word_dict.get('text')
    sentence = new_word_dict.get('notes')
    print("\n"+sentence)
    # NLP 尝试分析出原型
    new_word_ori = NLP.analyze_word(sentence, new_word)
    if new_word_ori is not None:
        word_info = dict_.get_word_info(new_word_ori)
    else:
        word_info = dict_.get_word_info(new_word)
    word_info['sentences'] = []
    word_info['sentences'].append(new_word_dict)
    new_word_info_list.append(word_info)

# ---------- 新增功能1：对非 empty 的 word_info 先自动更新到 Anki，并保存相应的 notes/info json（在交互前） ----------
cache = load_cache()
auto_saved_notes = []
auto_saved_info = []

# 将未空的先处理掉（自动导入 Anki 并加入待保存列表）
for wi in list(new_word_info_list):
    if not is_wordinfo_empty(wi):
        # 更新 Anki
        try:
            out = anki.update_anki_full(deck, wi)
        except Exception as e:
            out = f"anki update failed: {e}"
        # 收集要保存的 notes（从 sentences 中取出原始 note）
        notes_from_sentences = [s for s in wi.get('sentences', []) if isinstance(s, dict)]
        auto_saved_notes.append(notes_from_sentences[0])
        # 收集 info（避免重复）
        prototype = None
        pos = wi.get('partOfSpeech', [])
        if isinstance(pos, list) and len(pos) > 0 and isinstance(pos[0], dict):
            prototype = pos[0].get('wordPrototype', None)
        if prototype is None:
            # 尝试从 word_info 顶级字段获取
            prototype = wi.get('wordPrototype')
        if prototype is not None:
            if not any((existing.get('partOfSpeech') and isinstance(existing.get('partOfSpeech'), list)
                        and existing.get('partOfSpeech')[0].get('wordPrototype') == prototype)
                    for existing in old_word_info_list + auto_saved_info):
                        auto_saved_info.append(wi)
        # 从 new_word_info_list 中移除（因为已经处理）
        new_word_info_list.remove(wi)

# 立刻保存自动处理的 notes 和 info 到 backup（追加到旧列表并保存）
if auto_saved_notes:
    notes_to_save = old_word_dict_list + auto_saved_notes
    save.save_dict_list(notes_to_save, folder="../../data/backup/notes")

if auto_saved_info:
    info_to_save = old_word_info_list + auto_saved_info
    save.save_dict_list(info_to_save, folder="../../data/backup/info")

# ---------- 新增功能2：为 empty words 增加交互前的 cache 检查/自动复用/保存 cache 功能 ----------

# 排序 & 收集空 wordPrototype 的 text（保持原逻辑，但此时 new_word_info_list 不包含之前自动处理的项）
empty_word_texts = []

def word_prototype_empty_first(item):
    pos = item.get("partOfSpeech", [])
    if isinstance(pos, list):
        for p in pos:
            if isinstance(p, dict) and p.get("wordPrototype") == "":
                texts = [s.get("text") for s in item.get("sentences", []) if isinstance(s, dict)]
                empty_word_texts.extend(texts)
                return 0
    return 1

new_word_info_list = sorted(new_word_info_list, key=word_prototype_empty_first)

# 交互式处理剩下的空单词
for index, word_info in enumerate(new_word_info_list):
    # 如果不是 empty，跳过（大部分应该是 empty）
    if not is_wordinfo_empty(word_info):
        continue

    texts = [s.get("text") for s in word_info.get("sentences", []) if isinstance(s, dict)]
    text_str = " ".join(t for t in texts if isinstance(t, str))
    sentence = word_info.get("sentences")[0]["notes"]

    # 先查询 cache
    cached = cache.get(text_str)
    if cached:
        # 询问是否使用 cache
        print(f"发现缓存（{CACHE_FILE}）中的候选：")
        import pprint
        pprint.pprint(cached)
        use_cache = input("是否使用缓存中的词条？输入 y 使用 / n 继续手动输入（默认 y）：").strip().lower()
        if use_cache != 'n':
            # 将缓存内容合并到 word_info
            # 缓存应该保存的是与 partOfSpeech/wordPrototype/definitions 等兼容的结构
            cached_info = cached
            # 替换或填充 partOfSpeech
            word_info['partOfSpeech'] = cached_info.get('partOfSpeech', [cached_info]) if isinstance(cached_info, dict) else word_info.get('partOfSpeech')
            # 记录 wordUrl 如果有
            if isinstance(cached_info, dict) and cached_info.get('wordUrl'):
                word_info['wordUrl'] = cached_info.get('wordUrl')
            # 标记为非空，自动更新 Anki 并加入待保存列表
            try:
                out = anki.update_anki_full(deck, word_info)
            except Exception as e:
                out = f"anki update failed: {e}"
            # 保存到已处理的 notes/info
            for n in word_info.get('sentences', []):
                if not any(existing.get('text') == n.get('text') for existing in full_word_dict_list):
                    full_word_dict_list.append(n)
            if not any((existing.get('partOfSpeech') and isinstance(existing.get('partOfSpeech'), list)
                        and existing.get('partOfSpeech')[0].get('wordPrototype') == word_info['partOfSpeech'][0].get('wordPrototype'))
                       for existing in old_word_info_list + auto_saved_info):
                auto_saved_info.append(word_info)
            # 保存 auto lists 到 disk（追加保存）
            if auto_saved_notes:
                save.save_dict_list(old_word_dict_list + auto_saved_notes, folder="../../data/backup/notes")
            if auto_saved_info:
                save.save_dict_list(old_word_info_list + auto_saved_info, folder="../../data/backup/info")
            # 跳至下一个
            continue

    # 进入选择-执行-确认循环（原交互逻辑）
    while True:
        choose = input(
            f"{index}/{len(empty_word_texts)}:{sentence}\n"
            f"您选择通过以下哪种方式写入单词{texts}的信息：\n"
            "    [1] 爬虫获取\n"
            "    [2] 自己编写原型和释义\n"
            "请输入 1 或 2 （或输入 q 跳过此单词）："
        ).strip()

        if choose == "q":
            print("跳过此单词。")
            break

        if choose == "1" or choose == "":
            url = input("请输入单词的网站（或输入 r 返回重选）\n > ").strip()
            if url.lower() == "r":
                continue
            new_word_info = dict_.get_word_info_from_url(url=url)
            preview = new_word_info
        elif choose == "2":
            word_prototype = input("单词原型（直接回车表示使用句子文本作为原型，或输入 r 返回重选）\n > ").strip()
            if word_prototype.lower() == "r":
                continue
            word_meaning = input("单词释义（或输入 r 返回重选）\n > ").strip()
            if word_meaning.lower() == "r":
                continue

            new_word_info = {
                "type": "phrase" if " " in text_str else "word",
                "wordPrototype": word_prototype if word_prototype != "" else text_str,
                "definitions": [
                    {
                        "enMeaning": "",
                        "chMeaning": word_meaning
                    }
                ],
            }
            preview = new_word_info
        else:
            print("输入无效，请输入 1、2 或 q。")
            continue

        print("\n=== 预览 ===")
        import pprint
        pprint.pprint(preview)
        print("============\n")

        confirm = input("确认保存？输入 [y] 保存 / [r] 重新选择 / [s] 跳过此单词：").strip().lower()
        if confirm == "y" or confirm == "":
            # 将 new_word_info 写入 word_info 的 partOfSpeech
            if isinstance(word_info.get("partOfSpeech"), list) and len(word_info["partOfSpeech"]) > 0:
                if choose == "1" or choose == "":
                    # 爬虫返回的结构我们期望为包含 partOfSpeech 列表和 wordUrl
                    word_info["partOfSpeech"] = new_word_info.get("partOfSpeech", [new_word_info])
                    if new_word_info.get("wordUrl"):
                        word_info["wordUrl"] = new_word_info.get("wordUrl")
                else:
                    word_info["partOfSpeech"][0] = new_word_info
            else:
                word_info["partOfSpeech"] = [new_word_info]

            # 把此条写入 cache，便于下次复用
            cache[text_str] = new_word_info
            save_cache(cache)

            # 更新 Anki
            try:
                out = anki.update_anki_full(deck, word_info)
            except Exception as e:
                out = f"anki update failed: {e}"
            print("已保存。")

            # 添加到 full_word_dict_list（notes）和 auto_saved_info（info）以便后续统一保存
            for n in word_info.get('sentences', []):
                if not any(existing.get('text') == n.get('text') for existing in full_word_dict_list):
                    full_word_dict_list.append(n)
            if not any((existing.get('partOfSpeech') and isinstance(existing.get('partOfSpeech'), list)
                        and existing.get('partOfSpeech')[0].get('wordPrototype') == word_info['partOfSpeech'][0].get('wordPrototype'))
                       for existing in old_word_info_list + auto_saved_info):
                auto_saved_info.append(word_info)

            # 退出当前单词处理
            break
        elif confirm == "r":
            print("返回重新选择。")
            continue
        elif confirm == "s":
            print("跳过此单词（不保存）。")
            break
        else:
            print("输入无效，返回重新选择。")
            continue

# ---------- 合并并保存最终结果（与原流程保持一致） ----------
merged_word_info_list = info.merge_word_lists(old_word_info_list, auto_saved_info + new_word_info_list)

# 输出合并结果统计
print(f"old count: {len(old_word_info_list)}, new count: {len(new_word_info_list)}, merged count: {len(merged_word_info_list)}")

# 将所有剩余的 new_word_info_list（理论上都是已经处理完或用户跳过的）更新到 Anki（为了与原逻辑一致）
# for new_word_info in new_word_info_list:
#     if not is_wordinfo_empty(new_word_info):
#         try:
#             out = anki.update_anki_full(deck, new_word_info)
#         except Exception as e:
#             out = f"anki update failed: {e}"
#         print(new_word_info.get("partOfSpeech", [{}])[0].get("wordPrototype", "<no prototype>"), out)

# 最终保存 notes/info（合并过的）
# full_word_dict_list 已经包含自动保存与交互保存的 note 条目（如果有）
save.save_dict_list(full_word_dict_list, folder="../../data/backup/notes")
save.save_dict_list(merged_word_info_list, folder="../../data/backup/info")

print("处理完成。自动保存的 note/info 已写入 backup，交互中的空词条也会保存到 cache（数据目录下的 empty_cache.json）。")
