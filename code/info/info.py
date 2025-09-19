import copy

def _normalize_proto(p):
    if p is None:
        return None
    try:
        return str(p).strip().lower()
    except Exception:
        return None

def get_prototype(item):
    # 优先取 partOfSpeech[0].wordPrototype（如果存在且非空）
    pos = item.get("partOfSpeech", [])
    if isinstance(pos, list) and len(pos) > 0:
        first = pos[0]
        if isinstance(first, dict):
            wp = first.get("wordPrototype", None)
            if wp not in (None, ""):
                return _normalize_proto(wp)
    # 回退取 sentences[0].text
    sents = item.get("sentences", [])
    if isinstance(sents, list) and len(sents) > 0:
        for s in sents:
            if isinstance(s, dict):
                t = s.get("text")
                if t not in (None, ""):
                    return _normalize_proto(t)
    return None

def merge_word_lists(base_list, new_list):
    """
    base_list: 旧条目列表（将被更新并返回）
    new_list: 要合并进来的新条目列表
    """
    merged = copy.deepcopy(base_list)  # 保留原始备份
    proto_map = {}  # prototype -> index in merged

    # 建索引
    for idx, item in enumerate(merged):
        proto = get_prototype(item)
        if proto:
            proto_map[proto] = idx

    for new in new_list:
        proto_new = get_prototype(new)
        if proto_new and proto_new in proto_map:
            old = merged[proto_map[proto_new]]

            # 合并 sentences（去重 by text）
            old_sents = old.setdefault("sentences", [])
            existing_texts = {s.get("text") for s in old_sents if isinstance(s, dict) and s.get("text")}

            for s in new.get("sentences", []):
                if not isinstance(s, dict):
                    continue
                t = s.get("text")
                if t not in existing_texts:
                    old_sents.append(s)
                    existing_texts.add(t)

            # 合并 partOfSpeech：用 new 中非空的 wordPrototype 去替换 old 中空的 slot，
            # 或者把 new 的 partOfSpeech 添加到 old 中（避免重复）
            new_pos = new.get("partOfSpeech", [])
            old_pos = old.get("partOfSpeech", [])
            if isinstance(new_pos, list) and len(new_pos) > 0:
                if not isinstance(old_pos, list) or len(old_pos) == 0:
                    # old 没有，直接赋值
                    old["partOfSpeech"] = copy.deepcopy(new_pos)
                else:
                    # 尝试替换 old 中 wordPrototype 为空的项
                    for newp in new_pos:
                        if not isinstance(newp, dict):
                            continue
                        new_wp = newp.get("wordPrototype", "")
                        replaced = False
                        for i, oldp in enumerate(old["partOfSpeech"]):
                            if isinstance(oldp, dict) and oldp.get("wordPrototype", "") == "":
                                old["partOfSpeech"][i] = newp
                                replaced = True
                                break
                        # 如果没有可替换的 slot，则把 newp 添加入 old（避免直接重复添加：根据整个 dict 判断）
                        if not replaced and newp not in old["partOfSpeech"]:
                            old["partOfSpeech"].append(newp)
            # 你可以在这里再合并 definitions、tags 等其它字段（按需扩展）

        else:
            # 没找到相同的 prototype，则直接追加整个 new 条目
            merged.append(copy.deepcopy(new))
            # 若 new 有 proto，则更新索引，避免后面的 new 再次添加重复
            if proto_new:
                proto_map[proto_new] = len(merged) - 1

    return merged

# # 使用示例（假设 old_word_info_list 已经存在并且 word_info_list 是新生成的）
# merged_word_info_list = merge_word_lists(old_word_info_list, word_info_list)

# # 输出合并结果统计
# print(f"old count: {len(old_word_info_list)}, new count: {len(word_info_list)}, merged count: {len(merged_word_info_list)}")

# （可选）如果你想把合并后的结果覆盖原来的 old_word_info_list：
# old_word_info_list = merged_word_info_list

# （可选）保存合并结果
# save.save_dict_list(folder="...", dict_list=merged_word_info_list)
