import streamlit as st
import json
import base64
import vertexai
from vertexai.generative_models import GenerativeModel, Part, SafetySetting, Content
import yt_dlp
from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
import pandas as pd
import urllib.parse
from google.cloud import storage
import os
import shutil
import datetime

## Please use your own PROJECT_ID, REGION, and GCS_BUCKET
PROJECT_ID = "hxhdemo"
REGION = "us-central1"
gcs_path = "gs://hxhdemo"

current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

output_path = "/mnt/gcsfuse"



st.set_page_config(
    layout="wide",
    page_title="Gemini for Video",
    # page_icon="claude-ai-icon.png",
)

st.sidebar.header(("Choose a model"))
MODEL_ID = st.sidebar.selectbox(
    "Model",
    (
        "gemini-2.0-flash-001",
        "gemini-1.5-pro-002",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash-002",
        "gemini-1.5-pro-001",
        "gemini-1.5-flash-001",
    ),
    placeholder="gemini-1.5-pro-002",
)

temperature = st.sidebar.slider("Temperature:", 0.0, 1.0, 0.2, 0.1)


def gcs_to_http(gcs_path):
    """Converts a GCS path to an HTTP URL."""
    if not gcs_path.startswith("gs://"):
        raise ValueError("Invalid GCS path.  Must start with 'gs://'")

    path = gcs_path[5:]  # Remove the "gs://" prefix
    encoded_path = urllib.parse.quote(path)
    http_url = f"https://storage.googleapis.com/{encoded_path}"
    return http_url


########### Sidebar
st.sidebar.header(("Source Video"))

input_video = st.sidebar.text_input("Please input URL link (Youtube or GCS)")
st.sidebar.text("You can use this for a quick demo: https://www.youtube.com/watch?v=DyZpTaC8VMc")

# sample_input_video = "https://www.youtube.com/watch?v=DyZpTaC8VMc"
# gcs_path = "gs://netease-ie-videos/谷歌打标测试/单镜头理解/九大兵团_03吕布受降.mp4"

if input_video:
    if "http" in input_video:
        st.sidebar.video(input_video, format="video/mp4")
    if "gs://" in input_video:
        try:
            st.sidebar.video(gcs_to_http(input_video), format="video/mp4")
        except Exception as e:
            st.sidebar.write("无法直接展示视频")

def save_uploaded_video(uploaded_file):
    # 确保上传的文件是视频
    if uploaded_file is not None:
        # 获取文件扩展名
        file_extension = os.path.splitext(uploaded_file.name)[1]

        # 创建保存视频的目录(如果不存在)
        save_dir = output_path + "/uploaded_videos"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        # 保存文件路径
        save_path = os.path.join(save_dir, uploaded_file.name)

        # 将上传的文件保存到本地
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        return save_path
    return None

uploaded_file = st.sidebar.file_uploader("Or upload your video file", type=['mp4', 'mov', 'flv', 'wmv'])


if uploaded_file is not None:
    # 保存上传的视频
    video_path = save_uploaded_video(uploaded_file)

    if video_path:
        # 显示成功消息
        st.sidebar.success(f"Video uploaded {uploaded_file.name}")

        # 显示视频
        st.sidebar.video(video_path)
        input_video = video_path.replace(output_path, gcs_path)


usecase = st.sidebar.selectbox(
    "Please choose a use case",
    ("Video highlights", "Video shot analysis"), index=None)



general_highlight_prompt = """You are an expert gaming video analyst and social media content creator. I need you to analyze a gameplay video and identify 4-5 key highlight moments that would be engaging for social media sharing.

Please analyze the video with the following considerations:
1. Identify exciting moments based on the game genre:
  - For FPS games: kills, multi-kills, clutch plays, tactical moves
  - For MOBA games: team fights, objectives secured, outplays
  - For racing games: overtakes, near misses, perfect drifts
  - For sports games: goals, saves, skillful moves

2. For each highlight moment, detect:
- Precise timestamp (start and end)
- In-game audio/commentary transcription
- Why this moment is considered a highlight

3. Create viral-worthy social media content:
- Craft an attention-grabbing title using trending gaming phrases
- Write a compelling short description that hooks viewers
- The commentary should be short and exciting

Please provide the analysis in this JSON format:
{
    "title": "engaging social media title",
    "description": "compelling social share text",
    "highlights":
    [
        {
            "start_time": "MM:SS",
            "end_time": "MM:SS",
            "audio_transcribe": "relevant game audio/commentary",
            "highlight_reason": "explanation of why this is a highlight moment",
            "commentary":
            {
                "en": "Exciting commentary describing the highlight moment in English",
                "zh": "精彩的解说词描述高光时刻(中文)"
            }
        }
    ]
}

Please provide output in JSON format only. The response should:
 - Start directly with {
 - End with }
 - Contain no other text before or after the JSON
 - Be properly formatted JSON

Focus on moments that would generate high engagement on social media platforms like YouTube Shorts, TikTok, or Instagram Reels."""


x20_highlight_prompt = """You are an expert gaming content analyst specializing in Marvel Rivals and hero shooter games. Analyze the provided gameplay footage to identify 6-7 viral-worthy moments optimized for social media sharing, including match-defining victory sequences. Need to cover highlights from beginning until the end of the video to ensure comprehensive coverage.

Marvel Rivals will be a 6v6 player-versus-player, third-person hero shooter title. With the right combination of two or three characters, players can make use of "Dynamic Hero Synergy" which further maximize their playable character's combat efficiency. The game also features destructible environments, allowing players to alter the battlefield to their advantage.

Please analyze the video with the following considerations:

1. Identify exciting moments specific to Marvel Rivals:  
   * Dynamic Hero Synergy combinations and activations  
   * Environmental destruction plays and tactical advantages  
   * Team-based coordination and hero combinations  
   * Character-specific ultimate abilities and spectacular moves  
   * Game-changing team fights and objective control  
   * Clutch saves or match-turning moments  
   * Victory celebrations and match-winning plays  
   * Final blow sequences and victory screen reactions  
2. For each highlight moment, detect:  
   * Precise timestamp (start and end)  
   * In-game audio/commentary transcription  
   * Why this moment is considered a highlight  
   * Heroes involved and their synergy effects  
   * Environmental interaction impact  
   * Victory conditions and celebration details (if applicable)  
3. Create Marvel-themed viral content:  
   * Craft an attention-grabbing title using Marvel references and gaming terminology  
   * Write a compelling description incorporating Marvel Universe context  
   * Consider trending Marvel gaming hashtags and phrases  
   * Optimize for platform-specific requirements (TikTok, YouTube Shorts, Instagram Reels)  
   * Emphasize victory moments that resonate with Marvel's triumphant themes

Please provide the analysis in this JSON format: 
```JSON
{
    "title": {
        "en": "engaging social media title in English",
        "zh": "引人入胜的社交媒体标题(中文)"
    },
    "description": {
        "en": "compelling social share text in English",
        "zh": "引人注目的社交分享文案(中文)"
    },
    "highlights": [
        {
            "start_time": "MM:SS",
            "end_time": "MM:SS",
            "audio_transcribe": "relevant game audio/commentary",
            "highlight_reason": "explanation of why this is a highlight moment",
            "commentary": {
                "en": "Tiktok game streamer reaction commentary, Funny style (max 15-20 words)",
                "zh": "抖音游戏主播解说，搞笑风格 (最多15-20字)"
            }
        }
    ]
}
```

Additional requirements for commentary:

1. Commentary should be:
   * Energetic and engaging
   * Include relevant Marvel Universe references
   * Highlight specific gameplay mechanics
   * Use appropriate gaming terminology
   * Maintain consistent tone across languages
   * Capture the excitement of the moment
   * Be suitable for voice-over narration
   * Short and exciting
   * Use casual, conversational language

2. Commentary style guidelines:
   * Use present tense for immediacy
   * Include character names and abilities
   * Reference specific Marvel Rivals mechanics
   * Emphasize team play and synergies
   * Highlight environmental interactions
   * Build excitement towards victory moments
   * Match the energy level of the gameplay

Please provide output in JSON format only. The response should:

* Start directly with {  
* End with }  
* Contain no other text before or after the JSON  
* Be properly formatted JSON  
* Ensure highlights are distributed throughout the video duration  
* Include key moments from early, mid, and late game phases  
* Prioritize match-defining and victory moments in the final sequence

Focus on moments that showcase unique Marvel Rivals mechanics and would generate high engagement on social media platforms, especially emphasizing dramatic victory sequences."""



shot_prompt = """你是一位专业的视频分析专家和剧本编剧。现在需要你详细分析一段游戏视频的分镜内容，请按照以下要求输出分析结果：

1. 首先理解视频文件名，从中获取场景线索和上下文信息

2. 请将视频分解为独立的分镜头进行分析, 并以JSON格式输出以下信息: 
[{
    \"shot_id\": \"分镜头编号(从1开始)\", 
    \"time_range\": {
        \"start\": \"开始时间\",
        \"end\": \"结束时间\"
    },
    \"summary\": \"本段视频的简要概述, 例如出现了什么人物, 什么场景, 什么玩法等\",
    \"detailed_description\": \"镜头的详细场景描述\",
    \"dialogue\": \"该段中的对话或台词完整转录\",
    \"semantic_meaning\": \"该段视频传达的潜在语义和寓意, 用一句话概括\",
    \"tags\": [
        \"相关语义标签\",
        \"镜头运动方式\",
        \"摄影风格\",
        \"画面风格\",
        \"战斗类型标签\",
        \"主要人物\",
        \"画面视角\",
        \"特效类型\",
        \"中国古代战术\",
        \"场景对应一天的时间, 例如清晨, 夜晚等\",
        \"画面场景, 例如平原, 城市, 森林, 山间等\",
        等等,
    ],
    \"on_screen_text\": \"画面中出现的文字信息, 如果没有就输出None\",
    \"voiceover\": \"旁白内容, 如果没有就输出None\",
    \"subtitle\": \"字幕内容, 如果没有就输出None\",
    \"quality_score\": \"画面品质评分(1-10分)\",
    \"commentary\": \"以抖⾳解说的⻛格，对画⾯进⾏重新解说。要求幽默⻛趣，吸引年轻⼈。\"
}]

3. 要求：
- 所有内容使用中文输出
- 请确保输出格式为准确的JSON, 注意最后不要有多出的}, 且仅输出JSON, 前后不要额外添加文本
- 请输出所有的分镜头
- 确保每个分镜头的时间范围前后连贯
- 标签要包含内容语义标签和技术风格标签
- 每个分镜至少包含3-5个语义标签和2-3个技术风格标签
- 标签要简洁且具有代表性
- 语义分析要深入到位
- 品质评分要客观公正，需考虑画面构图、清晰度、色彩等因素

4. 所有视频均为网易发行的<率土之滨>游戏, 游戏以三国历史为背景, 玩家将扮演一方诸侯, 在一个真实还原的古代战争沙盘世界中发展势力, 与其他玩家实时对抗.

请基于以上规范，对视频进行专业、系统的分镜分析。"""


def generate(prompt, video, generation_config):
    vertexai.init(project=PROJECT_ID, location=REGION)
    model = GenerativeModel(
        MODEL_ID,
    )
    responses = model.generate_content(
        [prompt, video],
        generation_config=generation_config,
        safety_settings=safety_settings,
        # stream=True,
    )

    return responses.text


def generate_with_image(prompt, image_list, video, generation_config):
    vertexai.init(project=PROJECT_ID, location=REGION)    
    model = GenerativeModel(
        MODEL_ID,
    )
    image_prompt = """另外请仔细参考以下图片，准确识别视频中出现的人物，如果人物没有精确匹配，请忽略参考图片: """
    Content = [prompt, image_prompt]
    for image in image_list:
        Content.append(f"{image["text"]}:")
        image_url = Part.from_uri(
            mime_type="image/*",
            uri=image["url"],
            )
        Content.append(image_url)
        Content.append("\n")
    Content.append(video)
    # print(Content)
    responses = model.generate_content(
        contents = Content,
        generation_config=generation_config,
        safety_settings=safety_settings,
        # stream=True,
    )

    return responses.text

generation_config = {
    "max_output_tokens": 8192,
    "temperature": temperature,
    "top_p": 0.95,
    "response_mime_type": "application/json",
}

safety_settings = [
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=SafetySetting.HarmBlockThreshold.OFF,
    ),
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=SafetySetting.HarmBlockThreshold.OFF,
    ),
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=SafetySetting.HarmBlockThreshold.OFF,
    ),
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=SafetySetting.HarmBlockThreshold.OFF,
    ),
]

# sample_input_video = "https://www.youtube.com/watch?v=DyZpTaC8VMc"
video_url = Part.from_uri(
    mime_type="video/*",
    uri=input_video,
)


# Download video from Youtube
def download_youtube_and_get_filename(url):
    # 配置下载选项
    ydl_opts = {
        "format": "best",  # 最佳质量
        "quiet": False,  # 显示下载进度
        "outtmpl": "%(id)s.%(ext)s",
        # 'cookiesfrombrowser': ('chrome', ),
        'nocheckcertificate': True,
        'ignoreerrors': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 获取视频信息并下载
            info = ydl.extract_info(url, download=True)

            # 获取视频ID
            video_id = info["id"]

            # 获取视频标题
            title = info["title"]

            # 获取文件扩展名
            ext = info["ext"]

            # 完整文件名
            filename = f"{video_id}.{ext}"

            # print(f"\n视频ID: {video_id}")
            print(f"视频标题: {title}")
            print(f"视频文件: {filename}")

            filename = f"{video_id}.{info['ext']}"
            return filename

    except Exception as e:
        print(f"发生错误: {str(e)}")
        return None


# Download video from GCS
def download_blob(object_path):
    """Downloads a blob from the bucket."""
    # object_path = "gs://your-bucket-name/storage-object-name"
    # destination_file_name = "local/path/to/file"

    storage_client = storage.Client()

    bucket_name = object_path.split("/")[2]  # 提取 bucket name
    blob_name = "/".join(object_path.split("/")[3:])  # 提取 blob name

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    object_name = os.path.basename(blob_name)

    blob.download_to_filename(object_name)

    print(
        "Downloaded storage object {} from bucket {} to local file {}.".format(
            blob_name, bucket_name, object_name
        )
    )
    return object_name


def move_file(src_file, dst_dir):
    """将文件移动到指定目录。

    Args:
        src_file: 源文件路径。
        dst_dir: 目标目录路径。
    """
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)

    dst_path = os.path.join(dst_dir, os.path.basename(src_file))
    if os.path.exists(dst_path):
        os.remove(dst_path)  # 如果目标文件存在，先删除

    shutil.move(src_file, dst_dir)
    return dst_path


def cut_and_merge_video(input_video_path, time_stamps, output_video_path):
    """
    裁剪并拼接视频片段

    参数:
    input_video_path: 输入视频路径
    time_stamps: 时间戳列表，格式为 [("00:47", "00:54"), ("01:13", "01:21"), ...]
    output_video_path: 输出视频路径
    """
    print("input: " + input_video_path)
    print("output: " + output_video_path)
    # 加载视频文件
    video = VideoFileClip(input_video_path)

    # 存储裁剪后的视频片段
    video_clips = []

    # 处理每个时间戳对
    for start_time, end_time in time_stamps:
        # 将时间戳转换为秒
        start_seconds = sum(
            x * int(t) for x, t in zip([3600, 60, 1], start_time.split(":"))
        )
        end_seconds = sum(
            x * int(t) for x, t in zip([3600, 60, 1], end_time.split(":"))
        )

        # 裁剪视频片段
        clip = video.subclip(start_seconds, end_seconds)
        video_clips.append(clip)

    # 拼接所有视频片段
    final_clip = concatenate_videoclips(video_clips)

    # 导出最终视频
    final_clip.write_videofile(output_video_path)

    # 释放资源
    video.close()
    for clip in video_clips:
        clip.close()
    final_clip.close()
    return output_video_path


def time_to_seconds(time_str):
    minutes, seconds = map(int, time_str.split(':'))
    return minutes * 60 + seconds


def convert_to_subtitle_data(highlights_json):
    # 提取所有片段的时间
    clips = []
    new_time = 0
    subtitle_data = []

    # 遍历每个highlight，计算新的时间戳
    for highlight in highlights_json["highlights"]:
        start = time_to_seconds(highlight["start_time"])
        end = time_to_seconds(highlight["end_time"])
        duration = end - start

        # 将原始时间映射到新的时间线上
        new_start = new_time
        new_end = new_time + duration
        new_time = new_end  # 更新新的时间计数

        # 添加到subtitle_data
        subtitle_data.append((
            new_start,  # 新的开始时间
            new_end,    # 新的结束时间
            highlight["commentary"]["zh"],  # 中文注释
            highlight["commentary"]["en"]   # 英文注释
        ))

    return subtitle_data

def add_bilingual_subtitle(video_path, subtitle_data, output_path):
    # 加载视频
    video = VideoFileClip(video_path)
    # video_duration = video.duration  # 获取视频实际时长

    # 创建字幕clips列表
    subtitle_clips = []

    chinese_font = '/System/Library/Fonts/Supplemental/Songti.ttc'
    # subtitle_data格式: [(开始时间, 结束时间, "中文字幕", "英文字幕"), ...]
    for start_time, end_time, chinese_text, english_text in subtitle_data:
        # 创建中文字幕
        chinese_clip = TextClip(chinese_text, 
                              fontsize=15, 
                              color='white',
                              font='SongTi.ttf',  
                            #   stroke_color='white',
                            #   stroke_width=1
                              )

        # 创建英文字幕
        english_clip = TextClip(english_text,
                              fontsize=15, 
                              color='white',
                              font='SongTi.ttf',
                            #   stroke_color='white',
                            #   stroke_width=1
                            )

        # 使用lambda函数计算位置
        chinese_position = lambda t: ('center', video.h - 100)  # 距离底部100像素
        english_position = lambda t: ('center', video.h - 80)   # 距离底部80像素

        chinese_clip = chinese_clip.set_position(chinese_position)
        english_clip = english_clip.set_position(english_position)

        # 设置字幕显示时间
        chinese_clip = chinese_clip.set_start(start_time).set_end(end_time)
        english_clip = english_clip.set_start(start_time).set_end(end_time)

        subtitle_clips.extend([chinese_clip, english_clip])

    # 将所有字幕合成到视频上
    final_video = CompositeVideoClip([video] + subtitle_clips)

    # # 添加更多写入参数以确保质量
    # final_video.write_videofile(output_path, 
    #                           codec='libx264', 
    #                           audio_codec='aac',
    #                           fps=video.fps)  # 使用原视频的帧率
    
    # 导出最终视频
    final_video.write_videofile(output_path)
    return output_path




########### Main page
st.header(("Gemini for Video Analysis"))

if usecase is None:
    st.write("Please choose a use case")

elif "highlight" in usecase:
    st.subheader(("Video highlights"), divider=True)
    col1, col2 = st.columns([1, 3])

    with col1:
        option = st.selectbox(
            "Choose a Prompt template",
            ("General highlights generation", "Game specific (x20)"),
        )
        if "General" in option:
            prompt = st.text_area(
                "**:blue-background[Prompt]**",
                value=general_highlight_prompt,
                height=340,
                label_visibility="visible",
            )
        else: 
            prompt = st.text_area(
                "**:blue-background[Prompt]**",
                value=x20_highlight_prompt,
                height=340,
                label_visibility="visible",
            )

    clip_timestamps = []
    subtitle_data = []
    with col2:
        if st.button("Analyze video"):
            output_path = output_path + "/highlight-gen"
            # print(f"Highlights output path: {output_path}")
            with st.status("Analyzing..."):
                response = json.loads(generate(prompt, video_url, generation_config))
                st.write(response)

                clip_timestamps = [
                    ("00:" + h["start_time"], "00:" + h["end_time"])
                    for h in response["highlights"]
                ]
                # print(clip_timestamps)

            with st.status("Downloading video file..."):
                if "http" in input_video:
                    file_name = f"{input_video.split('=')[1]}.mp4"
                    if os.path.exists(f"{output_path}/{file_name}"):
                        st.write(file_name + " already exists")
                        src_video_file_path = f"{output_path}/{file_name}"
                    else:
                        input_video_file = download_youtube_and_get_filename(input_video)
                        src_video_file_path = move_file(input_video_file, output_path)
                        st.write("Source Video: " + src_video_file_path)

                if "gs://" in input_video:
                    file_name = input_video.split("/")[-1]
                    if os.path.exists(f"{output_path}/{file_name}"):
                        st.write(file_name + " already exists")
                        src_video_file_path = f"{output_path}/{file_name}"
                    else:
                        input_video_file = download_blob(input_video)
                        src_video_file_path = move_file(input_video_file, output_path)
                        st.write("Source Video: " + src_video_file_path)

                
                with open(f"{src_video_file_path.split('.')[0]}.json", "w") as f:
                    # 将 response 写入文件
                    json.dump(response, f, indent=4)

            with st.status("Generating highlights..."):
                output_video_path = f"{src_video_file_path.split('.')[0]}_clipped.mp4"
                print(clip_timestamps)
                output = cut_and_merge_video(
                    input_video_path=src_video_file_path,
                    time_stamps=clip_timestamps,
                    output_video_path=output_video_path,
                )
                st.write("Highlights Clipped: " + output_video_path)
                # st.video(output)

            # if st.button("添加解说字幕"):
                subtitle_data = convert_to_subtitle_data(response)

                output_with_subtitle = add_bilingual_subtitle(output_video_path, subtitle_data, f"{output_video_path.split('.')[0]}_with_subtitle.mp4")
                st.write("Highlights Clipped with subtitles: " + output_with_subtitle)
                
                st.video(output_with_subtitle)


elif "shot" in usecase:
    st.subheader(("Video shot analysis"), divider=True)

    col1, col2 = st.columns([1, 3])
    with col1:
        option = st.selectbox(
            "Choose a Prompt template",
            ("Video shots analysis (率土之滨)"),
        )
        if "Video" in option:
            shot_prompt = st.text_area(
                "**:blue-background[Prompt]**",
                value=shot_prompt,
                height=340,
                label_visibility="visible",
            )
        # else: 
        #     prompt = st.text_area(
        #         "**:blue-background[Prompt]**",
        #         value=,
        #         height=340,
        #         label_visibility="visible",
        #     )

        images_input = st.text_area("可输入参考图片, 格式示例: 曹操--ImageUrl(GCS or HTTP), 每个一行")
        reference_images = []
        if images_input:
            lines = images_input.split('\n')
            for l in lines:
                doc = {}
                doc["text"] = l.split("--")[0]
                doc["url"] = l.split("--")[1]
                reference_images.append(doc)
            # st.write(reference_images)




    with col2:
        if st.button("Analyze video"):
            shot_analysis_output_path = output_path + "/shot-analysis"

            if not os.path.exists(shot_analysis_output_path):
                os.makedirs(shot_analysis_output_path)
            with st.status("Analyzing..."):
                if reference_images:
                    response = generate_with_image(shot_prompt, reference_images, video_url, generation_config)
                else:
                    response = generate(shot_prompt, video_url, generation_config)

                print(response)
                df = pd.DataFrame(json.loads(response))

                st.dataframe(df, hide_index=True)
                # st.markdown(df.to_html(escape=False), unsafe_allow_html=True)
                # st.table(df)
                # edited_df = st.data_editor(df, hide_index=True)

                df.insert(0, "video", "")
                df.insert(0, "time", "")
                # 写入文件名
                df.loc[0, "video"] = input_video
                df.loc[0, "time"] = current_datetime

                full_file_path = f"{shot_analysis_output_path}/shot-analysis.csv"

                file = df.to_csv(
                    full_file_path,
                    mode="a",
                    header=not os.path.exists(full_file_path),
                    index=False,
                )
                st.write(full_file_path)

                with open(full_file_path, "rb") as file:
                    btn = st.download_button(
                        label="Download output",
                        data=file,
                        file_name="shot-analysis.csv",
                        mime="text/csv",
                    )
