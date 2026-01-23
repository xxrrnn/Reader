# -*- coding: utf-8 -*-
"""测试GPU加速是否可用"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from movie.extract_audio import detect_gpu_acceleration, check_ffmpeg

if __name__ == '__main__':
    print("=" * 60)
    print("FFmpeg GPU加速检测")
    print("=" * 60)
    
    # 检查ffmpeg是否可用
    if not check_ffmpeg():
        print("[错误] FFmpeg未安装或不在PATH中")
        sys.exit(1)
    
    print("[信息] FFmpeg已安装")
    
    # 检测GPU加速器
    print("\n正在检测GPU加速器...")
    result = detect_gpu_acceleration(force_recheck=True)
    
    if result:
        print(f"\n[成功] 检测到可用的GPU加速器: {result}")
        print(f"将使用 {result} 进行GPU加速")
    else:
        print("\n[警告] 未检测到可用的GPU加速器")
        print("将使用CPU进行处理（速度较慢）")
    
    print("=" * 60)


