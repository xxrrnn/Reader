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
    extract_screenshot, add_subtitle_to_image, check_if_media_exists
)
from movie.import_to_anki import (
    parse_ass_file, find_chinese_for_sentence, store_media_file,
    format_timestamp, build_example_with_image, build_blanked_example,
    check_if_example_exists, get_word_prototype_and_pos,
    add_or_update_word_to_anki
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
    
    # 步骤2: 检查哪些单词还没有媒体文件
    print("\n" + "="*60)
    print("步骤2: 检查缺失的媒体文件")
    print("="*60)
    missing_words = []
    for word, sentence in words_sentences:
        if not check_if_media_exists(word, audio_dir):
            missing_words.append((word, sentence))
            print(f"  [缺失] {word}: {sentence}")
    
    if not missing_words:
        print("所有单词的媒体文件都已存在！")
    else:
        print(f"\n找到 {len(missing_words)} 个缺失媒体文件的单词")
    
    # 步骤3: 提取缺失的媒体文件
    if missing_words:
        print("\n" + "="*60)
        print("步骤3: 提取媒体文件")
        print("="*60)
        
        for i, (word, sentence) in enumerate(missing_words, 1):
            print(f"\n[{i}/{len(missing_words)}] 处理: {word}")
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
            
            # 生成输出文件名
            safe_word = re.sub(r'[^\w\s-]', '', word).strip().replace(' ', '_')
            # 找到下一个可用的序号
            existing_files = list(audio_dir.glob(f"{safe_word}_*.jpg"))
            if existing_files:
                max_num = max([int(f.stem.split('_')[-1]) for f in existing_files if f.stem.split('_')[-1].isdigit()] or [0])
                file_num = max_num + 1
            else:
                file_num = 1
            
            audio_output_path = audio_dir / f"{safe_word}_{file_num:02d}.mp3"
            screenshot_output_path = audio_dir / f"{safe_word}_{file_num:02d}.jpg"
            
            # 提取音频
            print(f"  正在提取音频...")
            if extract_audio_segment(VIDEO_PATH, start_seconds, end_seconds, str(audio_output_path)):
                print(f"  [成功] 音频: {audio_output_path.name}")
            else:
                print(f"  [失败] 音频提取失败")
                continue
            
            # 提取截图
            screenshot_time = start_seconds + 0.5
            if screenshot_time > end_seconds:
                screenshot_time = start_seconds
            
            print(f"  正在提取截图...")
            if extract_screenshot(VIDEO_PATH, screenshot_time, str(screenshot_output_path)):
                print(f"  [成功] 截图: {screenshot_output_path.name}")
                # 添加字幕
                if add_subtitle_to_image(str(screenshot_output_path), chinese_text, english_text,
                                      CHINESE_FONT_SIZE, ENGLISH_FONT_SIZE):
                    print(f"  [成功] 已添加字幕到截图")
            else:
                print(f"  [失败] 截图提取失败")
                continue
    
    # 步骤4: 导入到Anki
    print("\n" + "="*60)
    print("步骤4: 导入到Anki")
    print("="*60)
    
    success_count = 0
    fail_count = 0
    
    for i, (word, sentence) in enumerate(words_sentences, 1):
        print(f"\n[{i}/{len(words_sentences)}] 处理单词: {word}")
        print(f"  例句: {sentence}")
        
        try:
            # 1. 使用NLP获取单词原型和词性
            prototype, pos = get_word_prototype_and_pos(sentence, word)
            print(f"  原型: {prototype}, 词性: {pos}")
            
            # 2. 查找媒体文件
            word_variants = [word, word.capitalize(), word.title()]
            image_file = None
            audio_file = None
            
            for variant in word_variants:
                pattern = f"{variant}_*.jpg"
                matches = list(audio_dir.glob(pattern))
                if matches:
                    image_file = matches[0]
                    audio_file = audio_dir / image_file.name.replace('.jpg', '.mp3')
                    if audio_file.exists():
                        break
            
            if not image_file or not audio_file or not audio_file.exists():
                print(f"  [跳过] 未找到对应的图片或音频文件")
                fail_count += 1
                continue
            
            image_filename = image_file.name
            audio_filename = audio_file.name
            
            # 3. 检查重复性（在爬虫之前）
            if check_if_example_exists(DECK_NAME, prototype, image_filename, sentence):
                print(f"  [跳过] 单词和例句已存在，跳过处理")
                continue
            
            # 4. 从Cambridge Dictionary获取单词信息
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
            
            # 7. 获取时间戳（从ASS文件中查找）
            match = find_matching_dialogue(sentence, dialogues_timing, word)
            timestamp = ""
            if match:
                start_time_str, _, _, _ = match
                timestamp = start_time_str
            
            # 8. 构建图片例句HTML和Blanked_Examples
            image_html = build_example_with_image(image_filename, audio_filename, sentence, chinese_text, 
                                                 book_name="Tenet", timestamp=timestamp)
            blanked_html = build_blanked_example(sentence, word)
            
            # 9. 添加或更新到Anki
            add_or_update_word_to_anki(DECK_NAME, word_info, image_html, blanked_html, audio_filename)
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
