import streamlit as st
import subprocess
import os
import openai
import re
from datetime import datetime

openai.api_key = st.secrets["OPENAI_API_KEY"]

st.title("🎬 Viral Clip Maker")
url = st.text_input("Paste YouTube video URL here:")

def srt_time_to_seconds(time_str):
    dt = datetime.strptime(time_str, "%H:%M:%S,%f")
    return dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1e6

def parse_srt(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read().strip()
    entries = content.split("\n\n")
    subtitles = []
    for entry in entries:
        lines = entry.split("\n")
        if len(lines) >= 3:
            start_str, end_str = lines[1].split(" --> ")
            text = " ".join(lines[2:])
            subtitles.append({
                "start": srt_time_to_seconds(start_str.strip()),
                "end": srt_time_to_seconds(end_str.strip()),
                "text": text
            })
    return subtitles

def download_video(video_url):
    subprocess.run(["yt-dlp", "-f", "best[ext=mp4]", "-o", "video.mp4", video_url], check=True)

def transcribe_video():
    subprocess.run(["whisper", "video.mp4", "--language", "English", "--model", "base", "--output_format", "srt"], check=True)

def load_transcript():
    with open("video.srt", "r", encoding="utf-8") as f:
        return f.read()

def analyze_with_gpt(transcript):
    prompt = f"""
You're a viral video expert. Analyze the following YouTube transcript and identify all moments that are likely to go viral.

For each moment, return:
- Start time in seconds
- End time in seconds
- A short summary of the moment
- A virality score from 1 to 10
- One sentence explaining why it might go viral

Only return moments you genuinely believe have viral potential based on emotional impact, surprise, humor, storytelling, or unique content.

Transcript:
{transcript}
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response["choices"][0]["message"]["content"]

def parse_gpt_response(response):
    clips = []
    matches = re.findall(
        r"Start:\s*(\d+\.?\d*)\s*End:\s*(\d+\.?\d*)\s*Summary:\s*(.*?)\s*Virality Score:\s*(\d+)\s*Why:\s*(.*?)\n",
        response, re.DOTALL
    )
    for match in matches:
        clips.append({
            "start": float(match[0]),
            "end": float(match[1]),
            "summary": match[2].strip(),
            "score": int(match[3]),
            "reason": match[4].strip()
        })
    return clips

def generate_clips(clip_data):
    os.makedirs("clips", exist_ok=True)
    for i, clip in enumerate(clip_data):
        out_file = f"clips/clip_{i+1}.mp4"
        subprocess.run([
            "ffmpeg", "-ss", str(clip["start"]), "-to", str(clip["end"]),
            "-i", "video.mp4", "-c", "copy", out_file
        ], check=True)

if st.button("Generate Clips"):
    with st.spinner("Processing..."):
        try:
            download_video(url)
            transcribe_video()
            transcript = load_transcript()
            gpt_response = analyze_with_gpt(transcript)
            clip_data = parse_gpt_response(gpt_response)
            generate_clips(clip_data)
            st.success("Done! Download your clips below:")
            for i, clip in enumerate(clip_data):
                clip_path = f"clips/clip_{i+1}.mp4"
                st.video(clip_path)
                st.markdown(f"**Summary**: {clip['summary']}  \n**Score**: {clip['score']}  \n**Why it might go viral**: {clip['reason']}")
                with open(clip_path, "rb") as f:
                    st.download_button(f"Download Clip {i+1}", f, file_name=f"clip_{i+1}.mp4")
        except Exception as e:
            st.error(f"Error: {e}")
