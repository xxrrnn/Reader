# %%
import json
import os
import json
from datetime import date, datetime

def load_latest_dict_list(folder="./saved"):
    """读取文件夹中日期最接近今天的 json 文件"""
    if not os.path.exists(folder):
        return []

    # 找出所有文件名形如 YYYY-MM-DD.json
    files = [
        f for f in os.listdir(folder)
        if f.endswith(".json") and len(f) == len("2025-09-18.json")
    ]

    if not files:
        return []

    # 解析文件名中的日期，找到距离今天最近的
    today = date.today()
    closest_file = None
    closest_diff = None

    for f in files:
        try:
            file_date = datetime.strptime(f[:-5], "%Y-%m-%d").date()
        except ValueError:
            continue
        diff = abs((today - file_date).days)
        if closest_diff is None or diff < closest_diff:
            closest_diff = diff
            closest_file = f

    if closest_file is None:
        return []

    filepath = os.path.join(folder, closest_file)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_dict_list(data, folder="./saved"):
    """保存 dict list 到本地，文件名是今天的日期"""
    os.makedirs(folder, exist_ok=True)
    filename = os.path.join(folder, f"{date.today().isoformat()}.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return filename


# %%

def load_dict_list(folder="./saved"):
    """读取文件夹中日期最接近今天的 json 文件"""
    if not os.path.exists(folder):
        return []

    # 找出所有文件名形如 YYYY-MM-DD.json
    files = [
        f for f in os.listdir(folder)
        if f.endswith(".json") and len(f) == len("2025-09-18.json")
    ]

    if not files:
        return []

    # 解析文件名中的日期，找到距离今天最近的
    today = date.today()
    closest_file = None
    closest_diff = None

    for f in files:
        try:
            file_date = datetime.strptime(f[:-5], "%Y-%m-%d").date()
        except ValueError:
            continue
        diff = abs((today - file_date).days)
        if closest_diff is None or diff < closest_diff:
            closest_diff = diff
            closest_file = f

    if closest_file is None:
        return []

    filepath = os.path.join(folder, closest_file)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)



# %%
def merge_and_deduplicate(old_list, new_list, key="key"):
    """合并两个 list[dict] 并去重"""
    seen = set()
    merged = []
    for item in old_list + new_list:
        try:
            k = item.get(key)
        except:
            import code; code.interact(local=locals())
        if k not in seen:
            seen.add(k)
            merged.append(item)
    return merged

def diff_new_vs_old(old_list, new_list, key="key"):
    """
    比较新旧数据，返回新的中与旧的不一样的部分。
    key: 用于比较的字段，默认用 "word"
    """
    old_keys = {item.get(key) for item in old_list}
    diff = [item for item in new_list if item.get(key) not in old_keys]
    return diff


