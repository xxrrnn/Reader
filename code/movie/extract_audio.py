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
    encoding = detect_file_encoding(file_path)
    with open(file_path, 'r', encoding=encoding) as f:
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
    encoding = detect_file_encoding(file_path)
    with open(file_path, 'r', encoding=encoding) as f:
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


def time_to_seconds(time_str: str, is_srt: bool = False) -> float:
    """
    将时间格式转换为秒数
    ASS格式: 0:03:16.55 -> 196.55
    SRT格式: 00:03:16,550 -> 196.55
    
    Args:
        time_str: 时间字符串
        is_srt: 是否为SRT格式（默认False，ASS格式）
        
    Returns:
        秒数
    """
    if is_srt:
        # SRT格式: HH:MM:SS,mmm
        time_str = time_str.replace(',', '.')
    
    parts = time_str.split(':')
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    return 0.0


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


def parse_srt_file_for_timing(file_path: str) -> List[Tuple[str, str, str, str]]:
    """
    解析SRT字幕文件，提取时间信息和文本
    
    Args:
        file_path: SRT文件路径
        
    Returns:
        List of (start_time, end_time, chinese_text, english_text) tuples
        时间格式为ASS格式（用于兼容）
    """
    dialogues = []
    # 自动检测编码
    encoding = detect_file_encoding(file_path)
    with open(file_path, 'r', encoding=encoding) as f:
        content = f.read()
    
    # SRT格式：序号、时间码、文本、空行
    # 使用正则表达式匹配
    pattern = r'(\d+)\s*\n(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n(.*?)(?=\n\d+\s*\n|\Z)'
    matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
    
    for match in matches:
        start_time_srt = match.group(2)
        end_time_srt = match.group(3)
        text = match.group(4).strip()
        
        # 转换SRT时间格式为ASS格式（用于兼容）
        # SRT: 00:01:04,410 -> ASS: 0:01:04.41
        start_time_ass = convert_srt_to_ass_time(start_time_srt)
        end_time_ass = convert_srt_to_ass_time(end_time_srt)
        
        # 解析文本（可能包含中文和英文，多行）
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        chinese_text = ""
        english_text = ""
        
        # 简单判断：包含中文字符的为中文，否则为英文
        for line in lines:
            # 去除HTML标签（如果有）
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
        
        if english_text or chinese_text:
            dialogues.append((start_time_ass, end_time_ass, chinese_text, english_text))
    
    return dialogues


def convert_srt_to_ass_time(srt_time: str) -> str:
    """
    将SRT时间格式转换为ASS时间格式
    SRT: 00:01:04,410 -> ASS: 0:01:04.41
    
    Args:
        srt_time: SRT时间字符串 (HH:MM:SS,mmm)
        
    Returns:
        ASS时间字符串 (H:MM:SS.cc)
    """
    # 替换逗号为点
    time_str = srt_time.replace(',', '.')
    parts = time_str.split(':')
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = parts[1]
        seconds = parts[2]
        # 只保留两位小数
        if '.' in seconds:
            sec_parts = seconds.split('.')
            sec_int = sec_parts[0]
            msec = sec_parts[1][:2] if len(sec_parts[1]) >= 2 else sec_parts[1].ljust(2, '0')
            seconds = f"{sec_int}.{msec}"
        return f"{hours}:{minutes}:{seconds}"
    return srt_time


def parse_subtitle_file_for_timing(file_path: str) -> List[Tuple[str, str, str, str]]:
    """
    自动检测字幕文件类型并解析（支持ASS和SRT）
    
    Args:
        file_path: 字幕文件路径
        
    Returns:
        List of (start_time, end_time, chinese_text, english_text) tuples
    """
    file_ext = Path(file_path).suffix.lower()
    if file_ext == '.srt':
        return parse_srt_file_for_timing(file_path)
    elif file_ext == '.ass':
        return parse_ass_file_for_timing(file_path)
    else:
        raise ValueError(f"不支持的字幕格式: {file_ext}，仅支持.ass和.srt")


def parse_subtitle_file(file_path: str) -> List[Tuple[str, str, str, str]]:
    """
    自动检测字幕文件类型并解析（支持ASS和SRT）
    用于获取完整字幕信息（与parse_ass_file功能相同）
    
    Args:
        file_path: 字幕文件路径
        
    Returns:
        List of (start_time, end_time, chinese_text, english_text) tuples
    """
    file_ext = Path(file_path).suffix.lower()
    if file_ext == '.srt':
        return parse_srt_file_for_timing(file_path)
    elif file_ext == '.ass':
        return parse_ass_file(file_path)
    else:
        raise ValueError(f"不支持的字幕格式: {file_ext}，仅支持.ass和.srt")


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
                # 对单词也进行相同的清理，移除连字符等标点符号
                word_clean = re.sub(r'[^\w\s]', '', word.lower().strip())
                if word_clean in english_clean:
                    return (start_time, end_time, chinese_text, english_text)
            else:
                return (start_time, end_time, chinese_text, english_text)
    
    return None


def get_audio_lufs(audio_path: str) -> Optional[float]:
    """
    获取音频文件的LUFS值（使用ffmpeg的loudnorm filter分析）
    
    Args:
        audio_path: 音频文件路径
        
    Returns:
        LUFS值，如果失败则返回None
    """
    if not os.path.exists(audio_path):
        return None
    
    # 使用loudnorm filter分析音频，获取LUFS值
    # 第一次pass：分析音频
    cmd = [
        'ffmpeg',
        '-i', audio_path,
        '-af', 'loudnorm=I=-23.0:TP=-1.5:LRA=11:print_format=json',
        '-f', 'null',
        '-'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        # loudnorm会在stderr中输出JSON格式的分析结果
        output = result.stderr
        
        # 查找JSON部分（可能在多个位置）
        json_start = output.find('{')
        json_end = output.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            import json
            json_str = output[json_start:json_end]
            try:
                data = json.loads(json_str)
                # 获取输入音频的LUFS值（input_i）
                input_i = data.get('input_i', None)
                if input_i is not None:
                    return float(input_i)
            except (json.JSONDecodeError, ValueError):
                # 如果JSON解析失败，尝试从文本中提取
                # loudnorm输出格式: "input_i": "-XX.XX"
                import re
                match = re.search(r'"input_i"\s*:\s*"([-]?\d+\.?\d*)"', output)
                if match:
                    return float(match.group(1))
        return None
    except Exception as e:
        print(f"获取音频LUFS值失败: {e}")
        return None


def normalize_audio_volume(input_path: str, output_path: str, target_lufs: float = -23.0) -> bool:
    """
    使用ffmpeg的loudnorm filter标准化音频音量
    
    Args:
        input_path: 输入音频文件路径
        output_path: 输出音频文件路径
        target_lufs: 目标LUFS值（默认-23.0，广播标准）
        
    Returns:
        是否成功
    """
    # 使用loudnorm filter标准化音量
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-af', f'loudnorm=I={target_lufs}:TP=-1.5:LRA=11',
        '-acodec', 'libmp3lame',
        '-ab', '192k',
        '-ar', '44100',
        '-f', 'mp3',  # 明确指定输出格式
        '-y',
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"音频音量标准化错误: {e}")
        print(f"错误输出: {e.stderr}")
        return False
    except FileNotFoundError:
        print("错误: 未找到ffmpeg，请确保已安装ffmpeg并添加到PATH")
        return False


def extract_audio_segment(video_path: str, start_time: float, end_time: float, 
                          output_path: str, use_gpu: bool = True, hwaccel: Optional[str] = None,
                          normalize_volume: bool = False, target_lufs: float = -23.0， end_padding=0.5) -> bool:
    """
    使用ffmpeg从视频中提取音频片段（支持GPU加速和音量标准化）
    
    Args:
        video_path: 视频文件路径
        start_time: 开始时间（秒）
        end_time: 结束时间（秒）
        output_path: 输出音频文件路径
        use_gpu: 是否使用GPU加速（默认True）
        hwaccel: 硬件加速器名称（cuda/d3d11va/qsv），如果为None则自动检测
        normalize_volume: 是否标准化音量（默认False）
        target_lufs: 目标LUFS值（默认-23.0，用于音量标准化）
        
    Returns:
        是否成功
    """
    duration = end_time - start_time + end_padding
    
    # 如果不需要标准化音量，直接提取
    if not normalize_volume:
        # 构建ffmpeg命令
        cmd = ['ffmpeg']
        
        # 添加GPU硬件加速（加速视频解码）
        if use_gpu:
            if hwaccel is None:
                hwaccel = detect_gpu_acceleration()
            if hwaccel:
                cmd.extend(['-hwaccel', hwaccel])
        
        cmd.extend([
            '-i', video_path,
            '-ss', str(start_time),
            '-t', str(duration),
            '-vn',  # 不包含视频
            '-acodec', 'libmp3lame',  # 使用MP3编码
            '-ab', '192k',  # 音频比特率
            '-ar', '44100',  # 采样率
            '-f', 'mp3',  # 明确指定输出格式
            '-y',  # 覆盖输出文件
            output_path
        ])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg错误: {e}")
            print(f"错误输出: {e.stderr}")
            # 如果GPU加速失败，尝试不使用GPU
            if use_gpu and hwaccel:
                print(f"GPU加速失败，尝试使用CPU...")
                return extract_audio_segment(video_path, start_time, end_time, output_path, 
                                           use_gpu=False, normalize_volume=normalize_volume, 
                                           target_lufs=target_lufs)
            return False
        except FileNotFoundError:
            print("错误: 未找到ffmpeg，请确保已安装ffmpeg并添加到PATH")
            return False
    else:
        # 需要标准化音量：先提取到临时文件，然后标准化
        temp_file = output_path + '.tmp'
        
        # 先提取音频
        success = extract_audio_segment(video_path, start_time, end_time, temp_file, 
                                       use_gpu=use_gpu, hwaccel=hwaccel, normalize_volume=False)
        if not success:
            return False
        
        # 标准化音量
        print(f"  正在标准化音频音量...")
        success = normalize_audio_volume(temp_file, output_path, target_lufs)
        
        # 删除临时文件
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except:
            pass
        
        return success


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


def extract_screenshot(video_path: str, timestamp: float, output_path: str, 
                       use_gpu: bool = True, hwaccel: Optional[str] = None) -> bool:
    """
    使用ffmpeg从视频中提取截图（支持GPU加速）
    
    Args:
        video_path: 视频文件路径
        timestamp: 时间戳（秒）
        output_path: 输出图片文件路径
        use_gpu: 是否使用GPU加速（默认True）
        hwaccel: 硬件加速器名称（cuda/d3d11va/qsv），如果为None则自动检测
        
    Returns:
        是否成功
    """
    # 构建ffmpeg命令
    cmd = ['ffmpeg']
    
    # 添加GPU硬件加速（加速视频解码）
    if use_gpu:
        if hwaccel is None:
            hwaccel = detect_gpu_acceleration()
        if hwaccel:
            cmd.extend(['-hwaccel', hwaccel])
    
    cmd.extend([
        '-i', video_path,
        '-ss', str(timestamp),
        '-vframes', '1',  # 只提取1帧
        '-q:v', '2',  # 高质量JPEG (2是高质量，范围1-31，数字越小质量越高)
        '-y',  # 覆盖输出文件
        output_path
    ])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg截图错误: {e}")
        print(f"错误输出: {e.stderr}")
        # 如果GPU加速失败，尝试不使用GPU
        if use_gpu and hwaccel:
            print(f"GPU加速失败，尝试使用CPU...")
            return extract_screenshot(video_path, timestamp, output_path, use_gpu=False)
        return False
    except FileNotFoundError:
        print("错误: 未找到ffmpeg，请确保已安装ffmpeg并添加到PATH")
        return False


def check_ffmpeg() -> bool:
    """检查ffmpeg是否可用"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, 
                              timeout=5,
                              text=True)
        # ffmpeg -version 返回 0 表示成功
        return result.returncode == 0
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


# 全局变量缓存GPU加速器检测结果
_cached_hwaccel = None

def detect_gpu_acceleration(force_recheck: bool = False) -> Optional[str]:
    """
    检测可用的GPU硬件加速器
    
    Args:
        force_recheck: 是否强制重新检测（默认False，使用缓存结果）
    
    Returns:
        可用的硬件加速器名称，如果不可用则返回None
        优先顺序: cuda > d3d11va > qsv
    """
    global _cached_hwaccel
    
    # 使用缓存结果（如果已检测过且不强制重新检测）
    if _cached_hwaccel is not None and not force_recheck:
        return _cached_hwaccel
    
    if not check_ffmpeg():
        _cached_hwaccel = None
        return None
    
    # 检测顺序：CUDA (NVIDIA) -> d3d11va (Windows通用) -> qsv (Intel)
    accelerators = ['cuda', 'd3d11va', 'qsv']
    
    for accel in accelerators:
        try:
            # 简单测试：检查ffmpeg是否支持该硬件加速器
            # 使用-hwaccels选项列出所有支持的硬件加速器
            cmd = ['ffmpeg', '-hide_banner', '-hwaccels']
            result = subprocess.run(cmd, capture_output=True, timeout=3, text=True)
            if result.returncode == 0 and accel in result.stdout:
                # 进一步测试：尝试使用该加速器（使用简单的测试）
                test_cmd = ['ffmpeg', '-hide_banner', '-hwaccel', accel, 
                           '-f', 'lavfi', '-i', 'testsrc=duration=0.1:size=64x64:rate=1',
                           '-frames:v', '1', '-f', 'null', '-']
                test_result = subprocess.run(test_cmd, capture_output=True, timeout=5, text=True)
                if test_result.returncode == 0:
                    print(f"[GPU] 检测到可用的GPU加速器: {accel}")
                    _cached_hwaccel = accel
                    return accel
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            continue
    
    print("[GPU] 未检测到可用的GPU加速器，将使用CPU")
    _cached_hwaccel = None
    return None


def check_if_media_exists(word: str, audio_dir: Path) -> bool:
    """检查媒体文件是否已存在（仅新格式：数字_单词.jpg）"""
    safe_word = re.sub(r'[^\w\s-]', '', word).strip().replace(' ', '_')
    word_variants = [word, word.capitalize(), word.title(), safe_word]
    for variant in word_variants:
        # 检查新格式：数字_单词.jpg
        pattern_new = f"*_{variant}.jpg"
        if list(audio_dir.glob(pattern_new)):
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

