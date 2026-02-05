# -*- coding: utf-8 -*-
"""
将Tenet电影单词导入Anki
- 使用图片替代例句（点击图片播放音频）
- 爬虫Cambridge Dictionary获取中英文翻译
- 使用NLP获取单词原型和词性
- 如果单词已存在，则在同一个界面添加例句
"""
import os
import base64
import sys
import html
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# 导入必要的模块
sys.path.insert(0, str(Path(__file__).parent.parent))
from anki.anki import invoke, MODEL_NAME, MODEL_CSS, ensure_pronunciation_audio, build_html_from_word_info, ensure_model_and_deck
from dictionary.dict import get_word_info_by_word
from NLP.NLP import nlp

# ==================== 配置项 ====================
DECK_NAME = "Media"  # 牌组名称
REQUEST_TIMEOUT = 2.0
# ================================================


def parse_words_file(file_path: str) -> List[Tuple[str, str]]:
    """
    解析单词文件，返回(单词, 例句)列表
    """
    words_sentences = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line:  # 非空行
            word = line
            # 下一行应该是例句
            if i + 1 < len(lines):
                sentence = lines[i + 1].strip()
                if sentence:
                    words_sentences.append((word, sentence))
                    i += 2
                else:
                    i += 1
            else:
                i += 1
        else:
            i += 1
    
    return words_sentences


def detect_file_encoding(file_path: str) -> str:
    """
    检测文件编码
    
    Args:
        file_path: 文件路径
        
    Returns:
        编码名称
    """
    encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 
                 'utf-16-le', 'utf-16-be', 'latin-1', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                f.read()
            return encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    # 如果都失败，返回utf-8（让调用者处理错误）
    return 'utf-8'


def parse_ass_file(file_path: str) -> dict:
    """
    解析ASS或SRT字幕文件，返回英文到中文的映射
    """
    from pathlib import Path
    file_ext = Path(file_path).suffix.lower()
    
    dialogues_map = {}
    
    if file_ext == '.srt':
        # 解析SRT文件
        encoding = detect_file_encoding(file_path)
        with open(file_path, 'r', encoding=encoding) as f:
            content = f.read()
        
        # SRT格式解析
        pattern = r'(\d+)\s*\n(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n(.*?)(?=\n\d+\s*\n|\Z)'
        matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            text = match.group(4).strip()
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            chinese_text = ""
            english_text = ""
            
            for line in lines:
                # 去除HTML标签
                line = re.sub(r'<[^>]+>', '', line)
                if any('\u4e00' <= char <= '\u9fff' for char in line):
                    if chinese_text:
                        chinese_text += " " + line
                    else:
                        chinese_text = line
                else:
                    if english_text:
                        english_text += " " + line
                    else:
                        english_text = line
            
            if english_text:
                english_clean = re.sub(r'[^\w\s]', '', english_text.lower())
                dialogues_map[english_clean] = (chinese_text, english_text)
    
    elif file_ext == '.ass':
        # 解析ASS文件
        encoding = detect_file_encoding(file_path)
        with open(file_path, 'r', encoding=encoding) as f:
            lines = f.readlines()
        
        for line in lines:
            if line.startswith('Dialogue:'):
                parts = line.split(',', 9)
                if len(parts) >= 10:
                    text = parts[9].strip()
                    
                    chinese_text = ""
                    english_text = ""
                    
                    if '\\N' in text:
                        parts_text = text.split('\\N', 1)
                        chinese_text = parts_text[0].strip()
                        if len(parts_text) > 1:
                            english_text = parts_text[1]
                    else:
                        english_text = text
                    
                    # 去除ASS样式标签
                    chinese_text = re.sub(r'\{[^}]*\}', '', chinese_text).strip()
                    english_text = re.sub(r'\{[^}]*\}', '', english_text).strip()
                    
                    if english_text:
                        # 清理英文文本用于匹配
                        english_clean = re.sub(r'[^\w\s]', '', english_text.lower())
                        dialogues_map[english_clean] = (chinese_text, english_text)
    
    return dialogues_map


def find_chinese_for_sentence(sentence: str, dialogues_map: dict) -> str:
    """在字幕映射中查找对应的中文"""
    sentence_clean = re.sub(r'[^\w\s]', '', sentence.lower())
    
    # 精确匹配
    if sentence_clean in dialogues_map:
        return dialogues_map[sentence_clean][0]
    
    # 模糊匹配
    for key, (chinese, english) in dialogues_map.items():
        if sentence_clean in key or key in sentence_clean:
            return chinese
    
    return ""


def store_media_file(file_path: str, filename: str) -> bool:
    """将文件存储到Anki媒体库"""
    try:
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        encoded = base64.b64encode(file_data).decode('utf-8')
        result = invoke("storeMediaFile", filename=filename, data=encoded)
        
        if result.get("error"):
            print(f"  [错误] 存储媒体文件失败: {result['error']}")
            return False
        return True
    except Exception as e:
        print(f"  [错误] 读取文件失败 {file_path}: {e}")
        return False


def find_media_files(word: str, sentence: str, audio_dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
    """查找对应的图片和音频文件（仅新格式：数字_单词.jpg）"""
    safe_word = re.sub(r'[^\w\s-]', '', word).strip().replace(' ', '_')
    word_variants = [word, word.capitalize(), word.title(), safe_word]
    
    for variant in word_variants:
        # 检查新格式：数字_单词.jpg
        pattern_new = f"*_{variant}.jpg"
        matches = list(audio_dir.glob(pattern_new))
        
        if matches:
            image_file = matches[0]
            audio_file = audio_dir / image_file.name.replace('.jpg', '.mp3')
            if audio_file.exists():
                return image_file, audio_file
    
    return None, None


def format_timestamp(time_str: str) -> str:
    """
    将ASS时间格式转换为显示格式
    输入: 0:03:16.55 (小时:分钟:秒.百分秒)
    输出: 0:03:16:55 (小时:分钟:秒:百分秒)
    """
    if not time_str:
        return ""
    
    parts = time_str.split(':')
    if len(parts) == 3:
        hours = parts[0]
        minutes = parts[1]
        seconds_parts = parts[2].split('.')
        seconds = seconds_parts[0]
        centiseconds = seconds_parts[1] if len(seconds_parts) > 1 else "00"
        # 只保留前两位
        if len(centiseconds) > 2:
            centiseconds = centiseconds[:2]
        elif len(centiseconds) == 1:
            centiseconds = centiseconds + "0"
        return f"{hours}:{minutes}:{seconds}:{centiseconds}"
    return time_str


def build_example_with_image(image_filename: str, audio_filename: str, 
                            sentence: str, chinese: str, book_name: str = "Tenet",
                            timestamp: str = "") -> str:
    """构建包含图片的例句HTML"""
    escaped_sentence = html.escape(sentence)
    escaped_chinese = html.escape(chinese) if chinese else ""
    
    # 格式化时间戳
    formatted_timestamp = format_timestamp(timestamp) if timestamp else ""
    meta_text = f" — 《{html.escape(book_name)}》"
    if formatted_timestamp:
        meta_text += f" {formatted_timestamp}"
    
    example_html = f"""
    <div class='example'>
        <div style="text-align: center; margin: 15px 0;">
            <a href="javascript:void(0);" onclick="
                (function() {{
                    var audioId = 'audio-' + '{image_filename}'.replace(/[^a-zA-Z0-9]/g, '');
                    var audioEl = document.getElementById(audioId);
                    if (!audioEl) {{
                        audioEl = document.createElement('audio');
                        audioEl.id = audioId;
                        audioEl.src = '{audio_filename}';
                        document.body.appendChild(audioEl);
                    }}
                    audioEl.play();
                }})();
                return false;
            ">
                <img src="{image_filename}" style="max-width: 100%; cursor: pointer; border: 2px solid #ddd; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />
            </a>
        </div>
        <div class='example-text' style="text-align: center; margin-top: 10px;">
            {escaped_sentence}
        </div>
        {f'<div class="definition-ch" style="text-align: center; margin-top: 5px;">{escaped_chinese}</div>' if escaped_chinese else ''}
        <div class='example-meta'>{meta_text}</div>
    </div>
    """
    return example_html


def build_blanked_example(sentence: str, target_word: str) -> str:
    """构建Blanked_Examples字段"""
    from anki.anki import replace_alnum_with_underscores
    
    escaped_sentence = html.escape(sentence)
    escaped_target = html.escape(target_word.strip())
    
    if " " in target_word:
        pattern = re.compile(re.escape(escaped_target), re.IGNORECASE)
    else:
        pattern = re.compile(r'\b' + re.escape(escaped_target) + r'\b', re.IGNORECASE)
    
    blanked_sentence = pattern.sub(replace_alnum_with_underscores, sentence)
    escaped_blanked = html.escape(blanked_sentence)
    
    return f"<div class='example'><div class='example-text'>{escaped_blanked}</div></div>"


def get_word_prototype_and_pos(sentence: str, target_word: str) -> Tuple[str, str]:
    """
    使用NLP获取单词的原型和词性
    返回: (prototype, pos)
    """
    try:
        doc = nlp(sentence)
        for token in doc:
            if token.text.lower() == target_word.lower():
                pos = token.pos_
                if pos == "VERB":
                    prototype = token.lemma_
                else:
                    prototype = token.text
                return prototype, pos
    except Exception as e:
        print(f"  [警告] NLP分析失败: {e}")
    
    # 回退：直接使用目标词
    return target_word, ""


def check_if_example_exists(deck_name: str, word_prototype: str, image_filename: str, sentence: str) -> bool:
    """
    检查单词和例句是否已存在
    返回: True表示已存在，False表示不存在
    """
    query = f'deck:"{deck_name}" "Word:{word_prototype}"'
    note_ids = invoke("findNotes", query=query).get("result", [])
    
    if not note_ids:
        return False  # 单词不存在
    
    # 单词存在，检查例句
    note_info = invoke("notesInfo", notes=note_ids).get("result", [])
    if note_info:
        existing_examples_field = note_info[0].get("fields", {}).get("Examples", {}).get("value", "")
        
        # 检查图片文件名是否已存在
        if image_filename and image_filename in existing_examples_field:
            return True
        
        # 检查句子文本是否已存在
        if sentence and sentence in existing_examples_field:
            return True
    
    return False  # 例句不存在


def add_or_update_word_to_anki(deck_name: str, word_info: Dict[str, Any], 
                               image_html: str, blanked_html: str, audio_filename: str,
                               sentence: str = None, book_name: str = "Movie"):
    """
    添加或更新单词到Anki
    如果单词已存在，则添加例句；否则创建新笔记
    """
    # 获取单词原型
    pos_list = word_info.get("partOfSpeech") or []
    primary_pos = pos_list[0] if pos_list else {}
    word_prototype = (primary_pos.get("wordPrototype") or word_info.get("word") or "").strip()
    
    # 构建字段
    fields = build_html_from_word_info(word_info)
    audio_markup = ensure_pronunciation_audio(word_info)
    
    if audio_markup:
        pronunciation_field = fields.get("Pronunciation", "")
        fields["Pronunciation"] = f"{audio_markup}\n{pronunciation_field}" if pronunciation_field else audio_markup
        pos_def_field = fields.get("POS_Definitions", "")
        fields["POS_Definitions"] = f"{audio_markup}\n{pos_def_field}" if pos_def_field else audio_markup
    
    # 添加图片例句到Examples字段
    existing_examples = fields.get("Examples", "")
    if existing_examples:
        fields["Examples"] = existing_examples + image_html
    else:
        fields["Examples"] = image_html
    
    # 添加Blanked_Examples
    existing_blanked = fields.get("Blanked_Examples", "")
    if existing_blanked:
        fields["Blanked_Examples"] = existing_blanked + blanked_html
    else:
        fields["Blanked_Examples"] = blanked_html
    
    # 检查单词是否已存在
    query = f'deck:"{deck_name}" "Word:{word_prototype}"'
    note_ids = invoke("findNotes", query=query).get("result", [])
    
    if note_ids:
        # 单词已存在，直接添加新例句（不检测重复）
        print(f"  [更新] 单词 '{word_prototype}' 已存在，添加新例句...")
        note_info = invoke("notesInfo", notes=note_ids).get("result", [])
        if note_info:
            existing_examples_field = note_info[0].get("fields", {}).get("Examples", {}).get("value", "")
            existing_blanked = note_info[0].get("fields", {}).get("Blanked_Examples", {}).get("value", "")
            
            # 直接添加新例句
            new_examples = existing_examples_field + image_html
            new_blanked = existing_blanked + blanked_html
            
            result = invoke("updateNoteFields", 
                          note={"id": note_ids[0], 
                               "fields": {"Examples": new_examples, "Blanked_Examples": new_blanked}})
            if result and not result.get("error"):
                print(f"  [成功] 已添加例句到 '{word_prototype}'")
            else:
                print(f"  [失败] 更新失败: {result.get('error', '未知错误')}")
    else:
        # 单词不存在，创建新笔记
        if " " in word_prototype:
            tags = "phrase"
        else:
            tags = "word"
        
        note = {
            "deckName": deck_name,
            "modelName": MODEL_NAME,
            "fields": {
                "Word": word_prototype,
                "Pronunciation": fields.get("Pronunciation", ""),
                "Definition": fields.get("Definition", ""),
                "POS_Definitions": fields.get("POS_Definitions", ""),
                "Examples": fields.get("Examples", ""),
                "Blanked_Examples": fields.get("Blanked_Examples", ""),
                "Tags": tags
            },
            "options": {"allowDuplicate": False},
            "tags": [book_name.lower()]
        }
        
        result = invoke("addNote", note=note)
        if result and not result.get("error") and result.get("result"):
            print(f"  [成功] 添加笔记 '{word_prototype}', Note ID: {result.get('result')}")
        else:
            error_msg = result.get("error", "未知错误") if result else "无响应"
            print(f"  [失败] 添加笔记 '{word_prototype}' 失败: {error_msg}")


def main():
    # 文件路径
    base_dir = Path(__file__).parent.parent.parent
    words_file = base_dir / 'data' / 'source' / 'Tenet' / 'Tenet.txt'
    ass_file = base_dir / 'data' / 'source' / 'Tenet' / 'Tenet.2020.IMAX.1080p.BluRay.x264.DTS-HD.MA.5.1-FGT.简体&英文.ass'
    audio_dir = base_dir / 'data' / 'source' / 'Tenet' / 'audio'
    
    # 解析文件
    print("正在解析单词文件...")
    words_sentences = parse_words_file(str(words_file))
    print(f"找到 {len(words_sentences)} 个单词")
    
    print("正在解析字幕文件...")
    dialogues_map = parse_ass_file(str(ass_file))
    print(f"找到 {len(dialogues_map)} 条字幕")
    
    # 确保牌组和模型存在
    if not ensure_model_and_deck(DECK_NAME, MODEL_NAME):
        print("错误: 无法继续，请先创建模型")
        return
    
    # 处理每个单词
    print(f"\n开始导入单词到Anki牌组 '{DECK_NAME}'...")
    success_count = 0
    fail_count = 0
    
    for i, (word, sentence) in enumerate(words_sentences, 1):
        print(f"\n[{i}/{len(words_sentences)}] 处理单词: {word}")
        print(f"  例句: {sentence}")
        
        try:
            # 1. 使用NLP获取单词原型和词性
            prototype, pos = get_word_prototype_and_pos(sentence, word)
            print(f"  原型: {prototype}, 词性: {pos}")
            
            # 2. 查找媒体文件（需要先找到文件名才能检查重复）
            image_file, audio_file = find_media_files(word, sentence, audio_dir)
            if not image_file or not audio_file:
                print(f"  [跳过] 未找到对应的图片或音频文件")
                fail_count += 1
                continue
            
            image_filename = image_file.name
            audio_filename = audio_file.name
            
            # 3. 不再检查重复性，直接处理所有内容
            
            # 4. 从Cambridge Dictionary获取单词信息（只有在需要时才爬虫）
            print(f"  正在从Cambridge Dictionary获取信息...")
            word_info = get_word_info_by_word(prototype, sleep=0.5)
            
            if not word_info or not word_info.get("partOfSpeech"):
                print(f"  [警告] 未获取到单词信息，使用基本信息")
                word_info = {
                    "word": prototype,
                    "wordUrl": "",
                    "partOfSpeech": [{
                        "type": pos,
                        "wordPrototype": prototype,
                        "pronunciationUK": {"phonetic": "", "pronUrl": ""},
                        "pronunciationUS": {"phonetic": "", "pronUrl": ""},
                        "definitions": [],
                        "phrases": [],
                        "phraseDefinitions": []
                    }]
                }
            
            # 5. 从ASS文件获取中文翻译
            chinese_text = find_chinese_for_sentence(sentence, dialogues_map)
            
            # 6. 存储媒体文件到Anki
            print(f"  图片: {image_filename}")
            print(f"  音频: {audio_filename}")
            
            if not store_media_file(str(image_file), image_filename):
                print(f"  [失败] 存储图片失败")
                fail_count += 1
                continue
            
            if not store_media_file(str(audio_file), audio_filename):
                print(f"  [失败] 存储音频失败")
                fail_count += 1
                continue
            
            # 7. 构建图片例句HTML和Blanked_Examples
            image_html = build_example_with_image(image_filename, audio_filename, sentence, chinese_text)
            blanked_html = build_blanked_example(sentence, word)
            
            # 8. 添加或更新到Anki
            add_or_update_word_to_anki(DECK_NAME, word_info, image_html, blanked_html, audio_filename, sentence)
            success_count += 1
            
        except Exception as e:
            print(f"  [错误] 处理失败: {e}")
            import traceback
            traceback.print_exc()
            fail_count += 1
    
    print(f"\n{'='*50}")
    print(f"导入完成!")
    print(f"成功: {success_count} 个")
    print(f"失败: {fail_count} 个")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
