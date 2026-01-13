# 音频提取工具

从视频文件中提取单词例句的音频片段。

## 功能

- 解析单词和例句文件（Tenet.txt）
- 在ASS字幕文件中查找匹配的句子和时间
- 使用ffmpeg从视频中提取对应的音频片段

## 使用方法

1. 确保已安装ffmpeg并添加到PATH环境变量
   - 下载地址: https://ffmpeg.org/download.html
   - Windows: 下载后解压，将bin目录添加到PATH

2. 修改代码中的视频文件路径（如果需要）

3. 运行脚本：
```bash
python code/movie/extract_audio.py
```

## 输出

提取的音频文件将保存到：`data/source/Tenet/audio/`

文件命名格式：`{单词}_{序号}.mp3`

例如：
- `twilight_01.mp3`
- `encapsulation_02.mp3`
- `transcend_03.mp3`

## 当前匹配结果

前3个单词的匹配结果：

1. **twilight**
   - 例句: We live in a twilight world
   - 时间: 0:03:16.55 -> 0:03:18.17 (1.62秒)

2. **encapsulation**
   - 例句: I've never seen encapsulation like this
   - 时间: 0:05:16.61 -> 0:05:18.27 (1.66秒)

3. **transcend**
   - 例句: Your duty transcends national interests.
   - 时间: 0:10:05.50 -> 0:10:08.32 (2.82秒)


