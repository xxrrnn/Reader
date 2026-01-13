"""
从视频文件中提取单词例句的音频片段
根据ASS字幕文件中的时间信息，从视频中提取对应的音频
"""
import os
import re
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def parse_words_file(file_path: str) -> List[Tuple[str, str]]:
    """
    解析单词文件，返回(单词, 例句)列表
    
    Args:
        file_path: 单词文件路径
        
    Returns:
        List of (word, sentence) tuples
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


def parse_ass_file_for_timing(file_path: str) -> List[Tuple[str, str, str, str]]:
    """
    解析ASS字幕文件，提取时间信息和英文文本
    
    Args:
        file_path: ASS文件路径
        
    Returns:
        List of (start_time, end_time, chinese_text, english_text) tuples
    """
    dialogues = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line in lines:
        if line.startswith('Dialogue:'):
            parts = line.split(',', 9)
            if len(parts) >= 10:
                start_time = parts[1].strip()
                end_time = parts[2].strip()
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
                
                chinese_text = re.sub(r'\{[^}]*\}', '', chinese_text).strip()
                english_text = re.sub(r'\{[^}]*\}', '', english_text).strip()
                
                if english_text:
                    dialogues.append((start_time, end_time, chinese_text, english_text))
    
    return dialogues


def parse_ass_file(file_path: str) -> List[Tuple[str, str, str, str]]:
    """
    解析ASS字幕文件，提取时间信息、中文和英文文本
    
    Args:
        file_path: ASS文件路径
        
    Returns:
        List of (start_time, end_time, chinese_text, english_text) tuples
    """
    dialogues = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line in lines:
        if line.startswith('Dialogue:'):
            # 解析Dialogue行
            # 格式: Dialogue: 0,0:03:16.55,0:03:18.17,Default,NTP,0,0,0,,我们活在暮光之界\N{\fn微软雅黑}{\b0}{\fs14}{\3c&H202020&}{\shad1}We live in a twilight world.
            parts = line.split(',', 9)  # 分割成10部分
            if len(parts) >= 10:
                start_time = parts[1].strip()
                end_time = parts[2].strip()
                text = parts[9].strip()
                
                # 提取中文和英文文本
                chinese_text = ""
                english_text = ""
                
                if '\\N' in text:
                    parts_text = text.split('\\N', 1)
                    chinese_text = parts_text[0].strip()
                    if len(parts_text) > 1:
                        english_text = parts_text[1]
                else:
                    # 如果没有\N，尝试判断是中文还是英文
                    english_text = text
                
                # 去除ASS样式标签
                chinese_text = re.sub(r'\{[^}]*\}', '', chinese_text).strip()
                english_text = re.sub(r'\{[^}]*\}', '', english_text).strip()
                
                if english_text or chinese_text:
                    dialogues.append((start_time, end_time, chinese_text, english_text))
    
    return dialogues


def time_to_seconds(time_str: str) -> float:
    """
    将ASS时间格式转换为秒数
    格式: 0:03:16.55 -> 196.55
    
    Args:
        time_str: ASS时间字符串
        
    Returns:
        秒数
    """
    parts = time_str.split(':')
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    return 0.0


def find_matching_dialogue(sentence: str, dialogues: List[Tuple[str, str, str, str]], 
                          word: str = None) -> Optional[Tuple[str, str, str, str]]:
    """
    在字幕中找到匹配的句子
    
    Args:
        sentence: 要匹配的例句
        dialogues: 字幕对话列表
        word: 单词（用于更精确匹配）
        
    Returns:
        匹配的(start_time, end_time, chinese_text, english_text)或None
    """
    # 清理句子，去除标点，转为小写
    sentence_clean = re.sub(r'[^\w\s]', '', sentence.lower())
    
    for start_time, end_time, chinese_text, english_text in dialogues:
        # 清理字幕文本
        english_clean = re.sub(r'[^\w\s]', '', english_text.lower())
        
        # 检查是否包含目标句子
        if sentence_clean in english_clean or english_clean in sentence_clean:
            # 如果提供了单词，检查单词是否在文本中
            if word:
                word_clean = word.lower().strip()
                if word_clean in english_clean:
                    return (start_time, end_time, chinese_text, english_text)
            else:
                return (start_time, end_time, chinese_text, english_text)
    
    return None


def extract_audio_segment(video_path: str, start_time: float, end_time: float, 
                          output_path: str) -> bool:
    """
    使用ffmpeg从视频中提取音频片段
    
    Args:
        video_path: 视频文件路径
        start_time: 开始时间（秒）
        end_time: 结束时间（秒）
        output_path: 输出音频文件路径
        
    Returns:
        是否成功
    """
    duration = end_time - start_time
    
    # 构建ffmpeg命令
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-ss', str(start_time),
        '-t', str(duration),
        '-vn',  # 不包含视频
        '-acodec', 'libmp3lame',  # 使用MP3编码
        '-ab', '192k',  # 音频比特率
        '-ar', '44100',  # 采样率
        '-y',  # 覆盖输出文件
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg错误: {e}")
        print(f"错误输出: {e.stderr}")
        return False
    except FileNotFoundError:
        print("错误: 未找到ffmpeg，请确保已安装ffmpeg并添加到PATH")
        return False


def add_subtitle_to_image(image_path: str, chinese_text: str, english_text: str, 
                          chinese_font_size: int = 60, english_font_size: int = 50) -> bool:
    """
    在截图上添加中英文字幕
    
    Args:
        image_path: 图片文件路径
        chinese_text: 中文字幕
        english_text: 英文字幕
        chinese_font_size: 中文字体大小（默认60）
        english_font_size: 英文字体大小（默认50）
        
    Returns:
        是否成功
    """
    if not HAS_PIL:
        print("警告: 未安装Pillow库，无法在截图上添加字幕")
        print("请运行: pip install Pillow")
        return False
    
    try:
        # 打开图片
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)
        
        # 获取图片尺寸
        width, height = img.size
        
        # 根据图片尺寸调整字体大小（如果图片很大，可以适当放大）
        scale_factor = min(width / 1920, height / 1080, 1.5)  # 最大放大1.5倍
        chinese_font_size = int(chinese_font_size * scale_factor)
        english_font_size = int(english_font_size * scale_factor)
        
        # 尝试加载字体（如果系统有的话）
        try:
            # Windows系统字体
            chinese_font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", chinese_font_size)
            english_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", english_font_size)
        except:
            try:
                # 备用字体
                chinese_font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", chinese_font_size)
                english_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", english_font_size)
            except:
                # 使用默认字体
                chinese_font = ImageFont.load_default()
                english_font = ImageFont.load_default()
        
        # 计算文字位置（底部居中）
        # padding和line_spacing根据字体大小动态调整
        padding = max(30, int(chinese_font_size * 0.5))
        line_spacing = max(15, int(chinese_font_size * 0.25))
        
        # 计算文字尺寸
        if chinese_text:
            chinese_bbox = draw.textbbox((0, 0), chinese_text, font=chinese_font)
            chinese_width = chinese_bbox[2] - chinese_bbox[0]
        else:
            chinese_width = 0
            
        english_bbox = draw.textbbox((0, 0), english_text, font=english_font)
        english_width = english_bbox[2] - english_bbox[0]
        
        max_text_width = max(chinese_width, english_width)
        
        # 计算起始X坐标（居中）
        start_x = (width - max_text_width) // 2
        
        # 计算Y坐标（从底部向上）
        y_positions = []
        if chinese_text:
            chinese_height = chinese_bbox[3] - chinese_bbox[1]
            english_height = english_bbox[3] - english_bbox[1]
            # 中文在上，英文在下
            y_positions.append((height - padding - english_height - line_spacing - chinese_height, 
                              chinese_text, chinese_font))
            y_positions.append((height - padding - english_height, english_text, english_font))
        else:
            english_height = english_bbox[3] - english_bbox[1]
            y_positions.append((height - padding - english_height, english_text, english_font))
        
        # 绘制半透明背景
        bg_height = sum([draw.textbbox((0, 0), text, font=font)[3] - 
                         draw.textbbox((0, 0), text, font=font)[1] 
                         for _, text, font in y_positions]) + line_spacing * (len(y_positions) - 1) + padding * 2
        bg_y = height - bg_height
        bg_rect = [start_x - padding, bg_y, start_x + max_text_width + padding, height]
        
        # 创建半透明背景
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle(bg_rect, fill=(0, 0, 0, 180))  # 半透明黑色背景
        img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
        draw = ImageDraw.Draw(img)
        
        # 绘制文字
        for y_pos, text, font in y_positions:
            # 计算文字居中位置
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_x = (width - text_width) // 2
            
            # 绘制文字（白色，带阴影效果）
            # 先绘制阴影（RGB模式下使用黑色）
            draw.text((text_x + 2, y_pos + 2), text, font=font, fill=(0, 0, 0))
            # 再绘制主文字（白色）
            draw.text((text_x, y_pos), text, font=font, fill=(255, 255, 255))
        
        # 保存图片
        img.save(image_path, quality=95)
        return True
        
    except Exception as e:
        print(f"添加字幕到图片时出错: {e}")
        return False


def extract_screenshot(video_path: str, timestamp: float, output_path: str) -> bool:
    """
    使用ffmpeg从视频中提取截图
    
    Args:
        video_path: 视频文件路径
        timestamp: 时间戳（秒）
        output_path: 输出图片文件路径
        
    Returns:
        是否成功
    """
    # 构建ffmpeg命令
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-ss', str(timestamp),
        '-vframes', '1',  # 只提取1帧
        '-q:v', '2',  # 高质量JPEG (2是高质量，范围1-31，数字越小质量越高)
        '-y',  # 覆盖输出文件
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg截图错误: {e}")
        print(f"错误输出: {e.stderr}")
        return False
    except FileNotFoundError:
        print("错误: 未找到ffmpeg，请确保已安装ffmpeg并添加到PATH")
        return False


def check_ffmpeg() -> bool:
    """检查ffmpeg是否可用"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def check_if_media_exists(word: str, audio_dir: Path) -> bool:
    """检查媒体文件是否已存在"""
    word_variants = [word, word.capitalize(), word.title()]
    for variant in word_variants:
        pattern = f"{variant}_*.jpg"
        if list(audio_dir.glob(pattern)):
            return True
    return False


def main():
    # ========== 可配置参数 ==========
    # 字体大小配置（可根据需要调整）
    CHINESE_FONT_SIZE = 60  # 中文字体大小
    ENGLISH_FONT_SIZE = 50  # 英文字体大小
    # ================================
    
    # 文件路径
    base_dir = Path(__file__).parent.parent.parent
    words_file = base_dir / 'data' / 'source' / 'Tenet' / 'Tenet.txt'
    ass_file = base_dir / 'data' / 'source' / 'Tenet' / 'Tenet.2020.IMAX.1080p.BluRay.x264.DTS-HD.MA.5.1-FGT.简体&英文.ass'
    video_path = r"C:\Users\xrn\BYR\Tenet.2020.IMAX.1080p.Bluray.DTS-HD.MA.5.1.X264-EVO\Tenet.2020.IMAX.1080p.Bluray.DTS-HD.MA.5.1.X264-EVO.mkv"
    output_dir = base_dir / 'data' / 'source' / 'Tenet' / 'audio'
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 检查ffmpeg
    has_ffmpeg = check_ffmpeg()
    if not has_ffmpeg:
        print("警告: 未找到ffmpeg，将只显示匹配结果，不会提取音频")
        print("请安装ffmpeg并添加到PATH环境变量中")
        print("下载地址: https://ffmpeg.org/download.html")
        print()
    
    # 检查视频文件是否存在
    if not os.path.exists(video_path):
        print(f"错误: 视频文件不存在: {video_path}")
        return
    
    # 解析文件
    print("正在解析单词文件...")
    words_sentences = parse_words_file(str(words_file))
    print(f"找到 {len(words_sentences)} 个单词")
    
    print("正在解析字幕文件...")
    dialogues = parse_ass_file(str(ass_file))
    print(f"找到 {len(dialogues)} 条字幕")
    
    # 处理所有单词
    print(f"\n开始提取所有 {len(words_sentences)} 个单词的音频...")
    for i, (word, sentence) in enumerate(words_sentences, 1):
        print(f"\n[{i}/{len(words_sentences)}] 处理单词: {word}")
        print(f"例句: {sentence}")
        
        # 查找匹配的字幕
        match = find_matching_dialogue(sentence, dialogues, word)
        
        if match:
            start_time_str, end_time_str, chinese_text, english_text = match
            start_seconds = time_to_seconds(start_time_str)
            end_seconds = time_to_seconds(end_time_str)
            
            print(f"找到匹配字幕:")
            print(f"  时间: {start_time_str} -> {end_time_str}")
            if chinese_text:
                print(f"  中文: {chinese_text}")
            print(f"  英文: {english_text}")
            print(f"  时长: {end_seconds - start_seconds:.2f}秒")
            
            # 生成输出文件名
            safe_word = re.sub(r'[^\w\s-]', '', word).strip().replace(' ', '_')
            audio_output_path = output_dir / f"{safe_word}_{i:02d}.mp3"
            screenshot_output_path = output_dir / f"{safe_word}_{i:02d}.jpg"
            
            if has_ffmpeg:
                # 提取音频
                print(f"正在提取音频到: {audio_output_path}")
                audio_success = extract_audio_segment(
                    video_path, 
                    start_seconds, 
                    end_seconds, 
                    str(audio_output_path)
                )
                
                if audio_success:
                    print(f"[成功] 成功提取音频: {audio_output_path}")
                else:
                    print(f"[失败] 提取音频失败")
                
                # 提取截图（在字幕开始后0.5秒，确保字幕已显示）
                screenshot_time = start_seconds + 0.5
                if screenshot_time > end_seconds:
                    screenshot_time = start_seconds  # 如果时间太短，使用开始时间
                
                print(f"正在提取截图到: {screenshot_output_path}")
                screenshot_success = extract_screenshot(
                    video_path,
                    screenshot_time,
                    str(screenshot_output_path)
                )
                
                if screenshot_success:
                    print(f"[成功] 成功提取截图: {screenshot_output_path}")
                    # 在截图上添加字幕
                    print(f"正在添加字幕到截图...")
                    subtitle_success = add_subtitle_to_image(
                        str(screenshot_output_path),
                        chinese_text,
                        english_text,
                        chinese_font_size=CHINESE_FONT_SIZE,
                        english_font_size=ENGLISH_FONT_SIZE
                    )
                    if subtitle_success:
                        print(f"[成功] 成功添加字幕到截图")
                    else:
                        print(f"[失败] 添加字幕失败")
                else:
                    print(f"[失败] 提取截图失败")
            else:
                print(f"[跳过] 未安装ffmpeg，跳过音频和截图提取")
                print(f"      如果已安装ffmpeg，输出文件将保存到:")
                print(f"        音频: {audio_output_path}")
                print(f"        截图: {screenshot_output_path}")
        else:
            print(f"[失败] 未找到匹配的字幕")


if __name__ == '__main__':
    main()

