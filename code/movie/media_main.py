# -*- coding: utf-8 -*-
"""
媒体单词处理主程序
- 读取txt文件
- 检查哪些单词还没有audio和image
- 从视频中提取audio和image
- 导入到Anki中
"""
import os
import re
import sys
from pathlib import Path

# 导入函数模块
sys.path.insert(0, str(Path(__file__).parent.parent))
from movie.extract_audio import (
    parse_words_file, parse_ass_file_for_timing, time_to_seconds,
    find_matching_dialogue, check_ffmpeg, extract_audio_segment,
    extract_screenshot, add_subtitle_to_image
)
from movie.import_to_anki import (
    parse_ass_file, find_chinese_for_sentence, store_media_file,
    build_example_with_image, build_blanked_example,
    get_word_prototype_and_pos, add_or_update_word_to_anki
)
from dictionary.dict import get_word_info_by_word
from anki.anki import MODEL_NAME, ensure_model_and_deck

# ==================== 配置项 ====================
DECK_NAME = "Media"
VIDEO_PATH = r"G:\BYR\Tenet.2020.IMAX.1080p.Bluray.DTS-HD.MA.5.1.X264-EVO\Tenet.2020.IMAX.1080p.Bluray.DTS-HD.MA.5.1.X264-EVO.mkv"
CHINESE_FONT_SIZE = 60  # 中文字体大小
ENGLISH_FONT_SIZE = 50  # 英文字体大小
# ================================================


def main():
    # 文件路径
    base_dir = Path(__file__).parent.parent.parent
    words_file = base_dir / 'data' / 'source' / 'Tenet' / 'Tenet.txt'
    ass_file = base_dir / 'data' / 'source' / 'Tenet' / 'Tenet.2020.IMAX.1080p.BluRay.x264.DTS-HD.MA.5.1-FGT.简体&英文.ass'
    audio_dir = base_dir / 'data' / 'source' / 'Tenet' / 'audio'
    
    # 创建输出目录
    audio_dir.mkdir(parents=True, exist_ok=True)
    
    # 检查ffmpeg
    has_ffmpeg = check_ffmpeg()
    if not has_ffmpeg:
        print("错误: 未找到ffmpeg，请安装ffmpeg并添加到PATH")
        return
    
    # 检查视频文件
    if not os.path.exists(VIDEO_PATH):
        print(f"错误: 视频文件不存在: {VIDEO_PATH}")
        return
    
    # 解析文件
    print("="*60)
    print("步骤1: 解析文件")
    print("="*60)
    print("正在解析单词文件...")
    words_sentences = parse_words_file(str(words_file))
    print(f"找到 {len(words_sentences)} 个单词")
    
    print("正在解析字幕文件...")
    dialogues_map = parse_ass_file(str(ass_file))
    dialogues_timing = parse_ass_file_for_timing(str(ass_file))
    print(f"找到 {len(dialogues_map)} 条字幕")
    
    # 确保牌组和模型存在
    ensure_model_and_deck(DECK_NAME, MODEL_NAME)
    
    # 步骤2: 检查哪些单词还没有mp3文件（新单词）
    print("\n" + "="*60)
    print("步骤2: 检查新单词（没有mp3文件的）")
    print("="*60)
    new_words = []  # 新单词列表：(word, sentence, safe_word, index)
    
    # 创建单词到序号的映射（按照txt文件中的顺序）
    word_to_index = {}
    for idx, (w, _) in enumerate(words_sentences, 1):
        safe_w = re.sub(r'[^\w\s-]', '', w).strip().replace(' ', '_')
        if safe_w not in word_to_index:
            word_to_index[safe_w] = idx
    
    for idx, (word, sentence) in enumerate(words_sentences, 1):
        safe_word = re.sub(r'[^\w\s-]', '', word).strip().replace(' ', '_')
        file_num = word_to_index.get(safe_word, idx)
        
        # 检查mp3文件是否存在（仅新格式：数字_单词.mp3）
        word_variants = [word, word.capitalize(), word.title(), safe_word]
        found_mp3 = False
        
        for variant in word_variants:
            # 检查新格式：数字_单词.mp3
            pattern_new = f"*_{variant}.mp3"
            matches_new = list(audio_dir.glob(pattern_new))
            if matches_new:
                found_mp3 = True
                break
        
        if not found_mp3:
            new_words.append((word, sentence, safe_word, file_num))
            print(f"  [新单词] {word} (序号: {file_num})")
    
    if not new_words:
        print("所有单词的媒体文件都已存在！")
        return
    
    print(f"\n找到 {len(new_words)} 个新单词需要处理")
    
    # 步骤3: 提取新单词的媒体文件
    print("\n" + "="*60)
    print("步骤3: 提取新单词的媒体文件")
    print("="*60)
    
    extracted_words = []  # 成功提取媒体文件的单词列表
    
    for i, (word, sentence, safe_word, file_num) in enumerate(new_words, 1):
        print(f"\n[{i}/{len(new_words)}] 提取: {word}")
        print(f"  例句: {sentence}")
        
        # 查找匹配的字幕
        match = find_matching_dialogue(sentence, dialogues_timing, word)
        
        if not match:
            print(f"  [跳过] 未找到匹配的字幕")
            continue
        
        start_time_str, end_time_str, chinese_text, english_text = match
        start_seconds = time_to_seconds(start_time_str)
        end_seconds = time_to_seconds(end_time_str)
        
        print(f"  找到匹配字幕:")
        print(f"    时间: {start_time_str} -> {end_time_str}")
        if chinese_text:
            print(f"    中文: {chinese_text}")
        print(f"    英文: {english_text}")
        
        # 生成输出文件名（数字在前，按照txt顺序）
        audio_output_path = audio_dir / f"{file_num:02d}_{safe_word}.mp3"
        screenshot_output_path = audio_dir / f"{file_num:02d}_{safe_word}.jpg"
        
        # 提取音频
        print(f"  正在提取音频...")
        if not extract_audio_segment(VIDEO_PATH, start_seconds, end_seconds, str(audio_output_path)):
            print(f"  [失败] 音频提取失败")
            continue
        print(f"  [成功] 音频: {audio_output_path.name}")
        
        # 提取截图
        screenshot_time = start_seconds + 0.5
        if screenshot_time > end_seconds:
            screenshot_time = start_seconds
        
        print(f"  正在提取截图...")
        if not extract_screenshot(VIDEO_PATH, screenshot_time, str(screenshot_output_path)):
            print(f"  [失败] 截图提取失败")
            continue
        print(f"  [成功] 截图: {screenshot_output_path.name}")
        
        # 添加字幕
        if not add_subtitle_to_image(str(screenshot_output_path), chinese_text, english_text,
                                  CHINESE_FONT_SIZE, ENGLISH_FONT_SIZE):
            print(f"  [警告] 添加字幕失败，继续处理")
        
        # 记录成功提取的单词
        extracted_words.append((word, sentence, safe_word, file_num, audio_output_path, screenshot_output_path))
    
    if not extracted_words:
        print("\n没有成功提取媒体文件的单词，无法导入到Anki")
        return
    
    print(f"\n成功提取 {len(extracted_words)} 个单词的媒体文件")
    
    # 步骤4: 导入新单词到Anki
    print("\n" + "="*60)
    print("步骤4: 导入新单词到Anki")
    print("="*60)
    
    success_count = 0
    fail_count = 0
    
    for i, (word, sentence, safe_word, file_num, audio_file, image_file) in enumerate(extracted_words, 1):
        print(f"\n[{i}/{len(extracted_words)}] 导入单词: {word}")
        print(f"  例句: {sentence}")
        
        try:
            image_filename = image_file.name
            audio_filename = audio_file.name
            
            # 1. 使用NLP获取单词原型和词性
            prototype, pos = get_word_prototype_and_pos(sentence, word)
            print(f"  原型: {prototype}, 词性: {pos}")
            
            # 2. 从Cambridge Dictionary获取单词信息
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
            
            # 3. 从ASS文件获取中文翻译
            chinese_text = find_chinese_for_sentence(sentence, dialogues_map)
            
            # 4. 存储媒体文件到Anki
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
            
            # 5. 获取时间戳（从ASS文件中查找）
            match = find_matching_dialogue(sentence, dialogues_timing, word)
            timestamp = ""
            if match:
                start_time_str, _, _, _ = match
                timestamp = start_time_str
            
            # 6. 构建图片例句HTML和Blanked_Examples
            image_html = build_example_with_image(image_filename, audio_filename, sentence, chinese_text, 
                                                 book_name="Tenet", timestamp=timestamp)
            blanked_html = build_blanked_example(sentence, word)
            
            # 7. 添加或更新到Anki
            add_or_update_word_to_anki(DECK_NAME, word_info, image_html, blanked_html, audio_filename, sentence)
            success_count += 1
            
        except Exception as e:
            print(f"  [错误] 处理失败: {e}")
            import traceback
            traceback.print_exc()
            fail_count += 1
    
    print(f"\n{'='*60}")
    print("处理完成!")
    print(f"成功: {success_count} 个")
    print(f"失败: {fail_count} 个")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
