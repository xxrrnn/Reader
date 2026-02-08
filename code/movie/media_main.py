# -*- coding: utf-8 -*-
"""
媒体单词处理主程序
- 读取txt文件
- 检查哪些单词还没有audio和image
- 从视频中提取audio和image
- 导入到Anki中
"""
import os
import json
import re
import sys
from pathlib import Path

# 导入函数模块
sys.path.insert(0, str(Path(__file__).parent.parent))
from movie.extract_audio import (
    parse_words_file, parse_subtitle_file_for_timing, time_to_seconds,
    find_matching_dialogue, check_ffmpeg, extract_audio_segment,
    extract_screenshot, add_subtitle_to_image, get_audio_lufs
)
from movie.import_to_anki import (
    parse_ass_file, find_chinese_for_sentence, store_media_file,
    build_example_with_image, build_blanked_example,
    get_word_prototype_and_pos, add_or_update_word_to_anki
)
from dictionary.dict import get_word_info_by_word
from anki.anki import MODEL_NAME, ensure_model_and_deck


def load_config(config_path: Path = None) -> dict:
    """加载配置文件"""
    if config_path is None:
        config_path = Path(__file__).parent / 'config.json'
    
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    return config


def find_files_in_dir(directory: Path, extensions: list) -> list:
    """在目录中查找指定扩展名的文件"""
    files = []
    for ext in extensions:
        files.extend(list(directory.glob(f'*{ext}')))
    return files


def get_project_config(config: dict) -> dict:
    """获取项目配置并自动查找文件"""
    projects = config.get('projects', {})
    if projects:
        # 使用 projects 中第一个项目（Python 3.7+ 字典保持插入顺序）
        project_name = next(iter(projects))
    else:
        # 如果 projects 为空，回退到 default_project
        project_name = config.get('default_project', 'Tenet')
    projects = config.get('projects', {})
    if project_name not in projects:
        raise ValueError(f"项目 '{project_name}' 不存在于配置文件中")
    
    project_config = projects[project_name].copy()
    base_dir = Path(__file__).parent.parent.parent
    
    # 解析project_dir
    project_dir = project_config.get('project_dir', '')
    if not os.path.isabs(project_dir):
        project_dir = base_dir / project_dir
    else:
        project_dir = Path(project_dir)
    
    if not project_dir.exists():
        raise FileNotFoundError(f"项目目录不存在: {project_dir}")
    
    project_config['project_dir'] = project_dir
    project_config['book_name'] = project_dir.name  # 使用最后一级文件夹名
    
    # 自动查找txt和字幕文件（支持ass和srt）
    txt_files = find_files_in_dir(project_dir, ['.txt'])
    subtitle_files = find_files_in_dir(project_dir, ['.ass', '.srt'])
    
    if not txt_files:
        raise FileNotFoundError(f"在 {project_dir} 中未找到txt文件")
    if not subtitle_files:
        raise FileNotFoundError(f"在 {project_dir} 中未找到字幕文件（.ass或.srt）")
    
    project_config['words_file'] = txt_files[0]
    project_config['subtitle_file'] = subtitle_files[0]  # 重命名为更通用的名称
    project_config['ass_file'] = subtitle_files[0]  # 保持兼容性
    
    # 音频目录在字幕文件所在目录创建（与字幕文件同级）
    subtitle_file = project_config.get('subtitle_file', project_config.get('ass_file'))
    project_config['audio_dir'] = subtitle_file.parent / 'audio'
    
    return project_config


def main():
    # 加载配置
    try:
        config = load_config()
    except Exception as e:
        print(f"错误: 加载配置文件失败: {e}")
        return
    
    # 获取项目配置
    try:
        project_config = get_project_config(config)
    except Exception as e:
        print(f"错误: {e}")
        return
    
    # 从配置中获取参数
    project_dir = project_config['project_dir']
    words_file = project_config['words_file']
    subtitle_file = project_config.get('subtitle_file', project_config.get('ass_file'))
    audio_dir = project_config['audio_dir']
    video_path = project_config.get('video_path', '')
    book_name = project_config.get('book_name', 'Movie')
    deck_name = config.get('deck_name', 'Media')
    chinese_font_size = config.get('chinese_font_size', 60)
    english_font_size = config.get('english_font_size', 50)
    
    # 音频配置
    audio_config = config.get('audio', {})
    normalize_volume = audio_config.get('normalize_volume', True)
    reference_audio = audio_config.get('reference_audio', '')
    
    # 获取参考音频的LUFS值
    target_lufs = -23.0  # 默认值
    if normalize_volume and reference_audio:
        base_dir = Path(__file__).parent.parent.parent
        if not os.path.isabs(reference_audio):
            reference_audio_path = base_dir / reference_audio
        else:
            reference_audio_path = Path(reference_audio)
        
        if reference_audio_path.exists():
            print(f"正在分析参考音频: {reference_audio_path}")
            ref_lufs = get_audio_lufs(str(reference_audio_path))
            if ref_lufs is not None:
                target_lufs = ref_lufs
                print(f"参考音频LUFS值: {target_lufs:.2f}")
            else:
                print(f"警告: 无法获取参考音频LUFS值，使用默认值: {target_lufs}")
        else:
            print(f"警告: 参考音频文件不存在: {reference_audio_path}，使用默认值: {target_lufs}")
    
    # 创建输出目录
    audio_dir.mkdir(parents=True, exist_ok=True)
    
    # 检查ffmpeg
    has_ffmpeg = check_ffmpeg()
    if not has_ffmpeg:
        print("错误: 未找到ffmpeg，请安装ffmpeg并添加到PATH")
        return
    
    # 检查视频文件
    if not os.path.exists(video_path):
        print(f"错误: 视频文件不存在: {video_path}")
        return
    
    # 解析文件
    print("="*60)
    print("步骤1: 解析文件")
    print("="*60)
    print(f"项目目录: {project_dir}")
    print(f"书籍名称: {book_name}")
    print(f"视频文件: {video_path}")
    print(f"单词文件: {words_file.name}")
    print(f"字幕文件: {subtitle_file.name}")
    print("正在解析单词文件...")
    words_sentences = parse_words_file(str(words_file))
    print(f"找到 {len(words_sentences)} 个单词")
    
    print("正在解析字幕文件...")
    from movie.import_to_anki import parse_ass_file
    dialogues_map = parse_ass_file(str(subtitle_file))
    dialogues_timing = parse_subtitle_file_for_timing(str(subtitle_file))
    print(f"找到 {len(dialogues_map)} 条字幕")
    
    # 确保牌组和模型存在
    ensure_model_and_deck(deck_name, MODEL_NAME)
    
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
    
    # 步骤3: 逐单词处理（提取媒体文件并导入到Anki）
    print("\n" + "="*60)
    print("步骤3: 逐单词处理（提取媒体文件并导入到Anki）")
    if normalize_volume:
        print(f"音量标准化: 启用 (目标LUFS: {target_lufs:.2f})")
    print("="*60)
    
    success_count = 0
    fail_count = 0
    
    for i, (word, sentence, safe_word, file_num) in enumerate(new_words, 1):
        print(f"\n[{i}/{len(new_words)}] 处理单词: {word}")
        print(f"  例句: {sentence}")
        
        try:
            # ========== 第一部分: 提取媒体文件 ==========
            print(f"  --- 提取媒体文件 ---")
            
            # 查找匹配的字幕
            match = find_matching_dialogue(sentence, dialogues_timing, word)
            
            if not match:
                print(f"  [跳过] 未找到匹配的字幕")
                fail_count += 1
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
            if not extract_audio_segment(video_path, start_seconds, end_seconds, str(audio_output_path),
                                       normalize_volume=normalize_volume, target_lufs=target_lufs):
                print(f"  [失败] 音频提取失败")
                fail_count += 1
                continue
            print(f"  [成功] 音频: {audio_output_path.name}")
            
            # 提取截图
            screenshot_time = start_seconds + 0.5
            if screenshot_time > end_seconds:
                screenshot_time = start_seconds
            
            print(f"  正在提取截图...")
            if not extract_screenshot(video_path, screenshot_time, str(screenshot_output_path)):
                print(f"  [失败] 截图提取失败")
                fail_count += 1
                continue
            print(f"  [成功] 截图: {screenshot_output_path.name}")
            
            # 添加字幕
            if not add_subtitle_to_image(str(screenshot_output_path), chinese_text, english_text,
                                      chinese_font_size, english_font_size):
                print(f"  [警告] 添加字幕失败，继续处理")
            
            # ========== 第二部分: 导入到Anki ==========
            print(f"  --- 导入到Anki ---")
            
            image_filename = screenshot_output_path.name
            audio_filename = audio_output_path.name
            
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
            chinese_text_for_anki = find_chinese_for_sentence(sentence, dialogues_map)
            
            # 4. 存储媒体文件到Anki
            print(f"  图片: {image_filename}")
            print(f"  音频: {audio_filename}")
            
            if not store_media_file(str(screenshot_output_path), image_filename):
                print(f"  [失败] 存储图片失败")
                fail_count += 1
                continue
            
            if not store_media_file(str(audio_output_path), audio_filename):
                print(f"  [失败] 存储音频失败")
                fail_count += 1
                continue
            
            # 5. 获取时间戳（从ASS文件中查找）
            timestamp = start_time_str
            
            # 6. 构建图片例句HTML和Blanked_Examples
            image_html = build_example_with_image(image_filename, audio_filename, sentence, chinese_text_for_anki, 
                                                 book_name=book_name, timestamp=timestamp)
            blanked_html = build_blanked_example(sentence, word)
            
            # 7. 添加或更新到Anki
            add_or_update_word_to_anki(deck_name, word_info, image_html, blanked_html, audio_filename, sentence, book_name=book_name)
            print(f"  [成功] 单词已导入到Anki")
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
