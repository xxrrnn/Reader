# %% [markdown]
# 测试和获取从koodo reader导出的csv 文件，将单词内容总结为一个字典，输出给后续处理模块。
# csv的位置为：../data/source/xxx/xxx.csv
# 

# %%
import csv, json
import pandas
from pathlib import Path

# %%
def get_csv_path(dir_path:str = "../../data/source") -> list[str]:
    '''
    遍历该文件夹内部所有csv文件，返回一个tuple

    Args:
        dir_path: 顶层文件夹路径

    Returns：
        list[str]: list[csv相对地址]

    Examples:
        >>> get_csv_path()
        [WindowsPath('../../data/source/Musk/KoodoReader-Note-2025-09-17.csv')]
    '''
    src_dir = Path(dir_path)
    if not src_dir.exists():
        raise FileNotFoundError(f"Directory not found: {dir_path}")
    csv_paths = list(src_dir.rglob("*.csv"))
    return csv_paths


# %% [markdown]
# ### dict中需要关注的key
# text: 单词
# 
# notes：所在句子
# 
# date：添加时间
# 
# chapter: 章节
# 
# bookName：书名
# 
# bookAuthor：作者

# %%
def get_csv_info(csv_paths:list) -> list[dict]:
    '''
    输入一个csv的地址列表，读取csv，获得csv中的信息。将单词信息构成dict，组成为列表

    Args:
        csv_paths: csv文件的地址列表

    Returns：
        list[dict]: 单词的信息组成为字典形式

    Examples:
    
    '''
    all_words = []
    for csv_path in csv_paths:
        df = pandas.read_csv(csv_path)
        words = df.to_dict(orient='records')
        all_words.extend(words)
    return all_words

# 移除模块级别的函数调用，避免导入时执行
# get_csv_info(get_csv_path())


