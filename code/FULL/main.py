import sys
import os

# 把上级目录加到 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from tqdm import tqdm

from anki import anki
from dictionary import dict as dict_
from vcs import vcs
from save import save
from info import info
from NLP import NLP

deck = "CambridgeDeck"

anki.ensure_model_and_deck(deck)


'''
step1: 遍历../../data/source中所有csv，转化为list[dict]
'''

word_dict_list = vcs.get_csv_info(vcs.get_csv_path(dir_path="../../data/source"))

'''
step2: 
遍历../../data/source中所有csv，转化为list[dict]
和backup中和今天日期最接近的进行比较去重，保存最新的为今天的日期.json，和新的notes
'''
### 加载旧的dict list
old_word_dict_list = save.load_latest_dict_list(folder="../../data/backup/notes")

### 和新的dict list进行合并，然后保存为新的json
full_word_dict_list = save.merge_and_deduplicate(old_list=old_word_dict_list, new_list=word_dict_list)

### 找到和old相比新的notes，用于此后的查词和导入anki
new_word_dict_list = save.diff_new_vs_old(old_word_dict_list, word_dict_list)
## 去掉text两边的空格
for new_word_dict in new_word_dict_list:
    new_word_dict['text'] = new_word_dict['text'].strip()
    new_word_dict['notes'] = new_word_dict['notes'].strip()
'''
step3:
使用get_word_info，查询单词释义信息。
和已有的dict中的wordPrototype比较，wordPrototype一样的进行sentences合并。
新单词创建新的词条信息。
'''
old_word_info_list = save.load_latest_dict_list(folder="../../data/backup/info")



new_word_info_list = []
for new_word_dict in tqdm(new_word_dict_list, desc="处理单词", unit="词"):
    new_word = new_word_dict.get('text')
    sentence = new_word_dict.get('notes')
    print(sentence)
    new_word_ori = NLP.analyze_word(sentence, new_word)
    if new_word_ori is not None:
        word_info = dict_.get_word_info(new_word_ori)
    else:
        word_info = dict_.get_word_info(new_word)
    word_info['sentences'] = []
    word_info['sentences'].append(new_word_dict)
    new_word_info_list.append(word_info)

# 排序 & 收集空 wordPrototype 的 text
empty_word_texts = []

def word_prototype_empty_first(item):
    pos = item.get("partOfSpeech", [])
    if isinstance(pos, list):
        for p in pos:
            if isinstance(p, dict) and p.get("wordPrototype") == "":
                # 收集 sentences 里的 text
                texts = [s.get("text") for s in item.get("sentences", []) if isinstance(s, dict)]
                empty_word_texts.extend(texts)
                return 0  # 排前面
    return 1  # 排后面

new_word_info_list = sorted(new_word_info_list, key=word_prototype_empty_first)

if len(empty_word_texts) != 0:
    for word_info in new_word_info_list:
        empty = False
        pos = word_info.get("partOfSpeech", [])
        if isinstance(pos, list):
            for p in pos:
                if isinstance(p, dict) and p.get("wordPrototype") == "":
                    empty = True

        if not empty:
            continue

        texts = [s.get("text") for s in word_info.get("sentences", []) if isinstance(s, dict)]
        text_str = " ".join(t for t in texts if isinstance(t, str))  # 安全拼接
        sentence = word_info.get("sentences")[0]["notes"]
        # 进入选择-执行-确认循环
        while True:
            choose = input(
                f"{sentence}\n"
                f"您选择通过以下哪种方式写入单词{texts}的信息：\n"
                "    [1] 爬虫获取\n"
                "    [2] 自己编写原型和释义\n"
                "请输入 1 或 2 （或输入 q 跳过此单词）："
            ).strip()

            if choose == "q":
                print("跳过此单词。")
                break  # 跳过当前 word_info，继续下一个

            if choose == "1" or choose == "":
                url = input("请输入单词的网站（或输入 r 返回重选）\n > ").strip()
                if url.lower() == "r":
                    # 用户选择返回重选
                    continue
                # 调用爬虫获取，如果失败请考虑捕获异常或返回 None
                new_word_info = dict_.get_word_info_from_url(url=url)
                preview = new_word_info  # 预览
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
                continue  # 回到选择

            # 显示预览并让用户确认或重选
            print("\n=== 预览 ===")
            import pprint
            pprint.pprint(preview)
            print("============\n")

            confirm = input("确认保存？输入 [y] 保存 / [r] 重新选择 / [s] 跳过此单词：").strip().lower()
            if confirm == "y" or confirm == "":
                # 若 partOfSpeech 存在且是列表，更新第一个或合适的位置
                if isinstance(word_info.get("partOfSpeech"), list) and len(word_info["partOfSpeech"]) > 0:
                    # 根据你的需求选择 update 还是替换：
                    # 这里我们替换第 0 个元素为 new_word_info（也可以用 update 保留其他字段）
                    if choose == "1" or choose == "":
                        word_info["partOfSpeech"] = new_word_info["partOfSpeech"]
                        word_info["wordUrl"] = new_word_info["wordUrl"]
                    else:
                        word_info["partOfSpeech"][0] = new_word_info
                else:
                    # 没有 partOfSpeech 时直接设置
                    word_info["partOfSpeech"] = [new_word_info]
                print("已保存。")
                break  # 完成该单词，跳出 while，进入下一个 word_info
            elif confirm == "r":
                print("返回重新选择。")
                continue  # 重新选择 1/2
            elif confirm == "s":
                print("跳过此单词（不保存）。")
                break  # 跳过该单词
            else:
                print("输入无效，返回重新选择。")
                # 回到选择循环（也可以回到确认循环，这里直接回到选择以简化流程）
                continue

# save.save_dict_list(new_word_info_list, folder="../../data/backup/info")



### 开始更新word_info_list，根据wordPrototype进行合并
merged_word_info_list = info.merge_word_lists(old_word_info_list, new_word_info_list)



# 输出合并结果统计
print(f"old count: {len(old_word_info_list)}, new count: {len(new_word_info_list)}, merged count: {len(merged_word_info_list)}")


for new_word_info in new_word_info_list:
    out = anki.upsert_sentences_into_deck("CambridgeDeck", new_word_info, update_all=True, dedupe=True, limit=None)
    print(new_word_info["partOfSpeech"][0]["wordPrototype"], out)



'''
final:
保存最新的notes和info在本地
'''
save.save_dict_list(full_word_dict_list, folder="../../data/backup/notes")
save.save_dict_list(merged_word_info_list, folder="../../data/backup/info")

