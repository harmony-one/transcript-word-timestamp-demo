import traceback
from urllib.parse import parse_qs, urlparse
from typing import List
from yt_dlp.utils import download_range_func
from config import config as app_config
from enum import Enum
import yt_dlp
import os
from moviepy import VideoFileClip, TextClip, CompositeVideoClip

class SubtitleConfig:
    """Configuration class for subtitle styling"""
    ACTIVE_COLOR = 'purple'     # Color for the currently spoken word
    INACTIVE_COLOR = 'gray'     # Color for other visible words
    DEFAULT_WINDOW_SIZE = 5     # Number of words visible at once
    FONT_SIZE = 48             # Base font size
    FONT_PATH = os.path.join('assets', 'Anton', 'Anton-Regular.ttf')
    DEFAULT_SIMILARITY_THRESHOLD = 80
    
    
class SubtitleMode(Enum):
    WORD = "word"
    PHRASE = "phrase"
    NONE = "none"

def escape_text(text) -> str:
    """Helper function to properly escape text for FFmpeg."""
    text = text.replace("'", "\u2019")  # Use Unicode right single quotation mark
    text = text.replace('"', '\\"')
    text = text.replace(',', '\\,')
    text = text.replace(':', '\\:')
    return text

class YouTubeHandler:
    @staticmethod
    def get_video_id(url: str) -> str:
        """Extract video ID from various YouTube URL formats."""
        if not url:
            return None
            
        if "youtu.be" in url:
            return url.split('/')[-1].split('?')[0]
            
        if "youtube.com" in url:
            parsed_url = urlparse(url)
            if "watch" in url:
                return parse_qs(parsed_url.query).get('v', [None])[0]
            elif "embed" in url:
                return parsed_url.path.split('/')[-1]
                
        return None

    @staticmethod
    def download_audio(url: str, output_dir: str = app_config.DEFAULT_TEMP_DIR) -> str:
        """
        Download audio from YouTube video.
        Returns path to downloaded file.
        """
        os.makedirs(output_dir, exist_ok=True)
        
        ydl_opts = {
            'format': 'm4a/bestaudio/best',
            'paths': {'home': output_dir},
            'outtmpl': {'default': '%(id)s.%(ext)s'},
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }]
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_id = info['id']
                return os.path.join(output_dir, f"{video_id}.m4a")
        except Exception as e:
            raise Exception(f"Failed to download audio: {str(e)}")

    def process_video_with_highlights(input_file: str, output_file: str, 
                            words: List[dict], duration: float,
                            window_size: int = SubtitleConfig.DEFAULT_WINDOW_SIZE,
                            font_size: int = SubtitleConfig.FONT_SIZE) -> bool:
        try:
            video = VideoFileClip(input_file)
            clips = []
            clip_start_ms = words[0]['start']
            char_width = font_size * 0.45  # Reduced for tighter character spacing
            word_spacing = font_size * 0.36  # Reduced for closer word spacing

            for i in range(0, len(words), window_size):
                window_words = words[i:i + window_size]
                if not window_words:
                    continue

                window_start = (window_words[0]['start'] - clip_start_ms) / 1000
                window_end = (window_words[-1]['end'] - clip_start_ms) / 1000

                # Calculate total width with adjusted spacing
                total_width = sum(len(w['text']) for w in window_words) * char_width + \
                            (len(window_words) - 1) * word_spacing
                start_x = (video.w - total_width) / 2
                current_x = start_x

                for word_idx, word in enumerate(window_words):
                    word_start = (word['start'] - clip_start_ms) / 1000
                    word_end = (word['end'] - clip_start_ms) / 1000
                    word_width = len(word['text']) * char_width

                    # Background word
                    text_clip = (TextClip(
                        text=word['text'].upper(),
                        size=(int(word_width * 1.1), None),  # Slightly wider than text
                        font_size=font_size,
                        color='white',
                        stroke_color='black',
                        stroke_width=2,
                        font=SubtitleConfig.FONT_PATH,
                        method='label'
                    )
                    .with_duration(window_end - window_start)
                    .with_start(window_start)
                    .with_position((int(current_x), video.h - font_size * 2)))
                    clips.append(text_clip)

                    # Highlighted version
                    highlight = (TextClip(
                        text=word['text'].upper(),
                        size=(int(word_width * 1.1), None),
                        font_size=font_size,
                        color='yellow',
                        stroke_color='black',
                        stroke_width=2,
                        font=SubtitleConfig.FONT_PATH,
                        method='label'
                    )
                    .with_duration(word_end - word_start)
                    .with_start(word_start)
                    .with_position((int(current_x), video.h - font_size * 2)))
                    clips.append(highlight)

                    current_x += word_width + word_spacing

            final_video = CompositeVideoClip([video] + clips)
            final_video.write_videofile(output_file, codec='libx264', audio_codec='aac')
            video.close()
            final_video.close()
            return True

        except Exception as e:
            print(f"Error processing video: {str(e)}")
            traceback.print_exc()
            return False
    
    @staticmethod
    def extract_clip(
        url: str,
        start_time: float,
        duration: int = 30, 
        output_dir: str = app_config.DEFAULT_OUTPUT_DIR,
        window_size: int = 5,
        words: List[dict] = []
    ) -> str:
        """
        Extract video clip, optimized for short segments.
        """
        os.makedirs(output_dir, exist_ok=True)

        video_id = YouTubeHandler.get_video_id(url)
        base_output = f"{video_id}_clip_{int(start_time)}.mp4"
        base_output_path = os.path.join(output_dir, base_output)

        final_output_path = os.path.join(
            output_dir, 
            f"{video_id}_clip_{int(start_time)}_subtitled.mp4"
        )

        try:
            print(f"Starting clip extraction ({duration}s from {int(start_time)}s)")
            
            def progress_hook(d):
                if d['status'] == 'downloading':
                    # Only show progress every 20%
                    if '_percent_str' in d and float(d['_percent_str'].rstrip('%')) % 20 == 0:
                        print(f"\rDownloading: {d['_percent_str']}", end='', flush=True)
                elif d['status'] == 'finished':
                    print("\nProcessing...")

            ydl_opts = {
                'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best',
                'outtmpl': {
                    'default': base_output_path  # Use base output path for initial download
                },
                'download_ranges': download_range_func(None, [(start_time, start_time + duration)]),
                'force_keyframes_at_cuts': True,
                'quiet': True,
                'no_warnings': True,
                'progress_hooks': [progress_hook],
                'postprocessor_args': {
                    'ffmpeg': ['-loglevel', 'error', '-hide_banner']
                },
                'retries': 1,
                'fragment_retries': 1,
                'buffersize': 1024,
                'http_chunk_size': 1024 * 1024,
            }

            print(f"Debug: Output directory: {output_dir}")
            print(f"Debug: Video ID: {video_id}")
            print(f"Debug: Base output path: {base_output_path}")
            # print(f"Debug: Final output path: {final_output_path}")
            print()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                downloaded_file = ydl.prepare_filename(info)
                print(f"Debug: Downloaded file: {downloaded_file}")
                
                if not os.path.exists(downloaded_file):
                    raise Exception(f"Downloaded file not found at: {downloaded_file}")

                # If the downloaded file has a different name, rename it to our base output
                if downloaded_file != base_output_path:
                    os.rename(downloaded_file, base_output_path)
                
                print(f"\nClip successfully created at: {base_output_path}")
                
                try:
                    success = False
                    success = YouTubeHandler.process_video_with_highlights(
                        base_output_path,
                        final_output_path,
                        words,
                        duration=duration,
                        window_size=window_size,
                        font_size=SubtitleConfig.FONT_SIZE
                    )

                    # Cleanup and return appropriate path
                    if success and os.path.exists(final_output_path):
                        os.remove(base_output_path)
                        print(f"Subtitles added successfully")
                        return final_output_path
                    else:
                        print(f"Warning: Failed to add subtitles, returning original clip")
                        return base_output_path
                        
                except Exception as e:
                    print(f"Warning: Failed to add subtitles: {str(e)}, returning original clip")
                    return base_output_path

        except Exception as e:
            print(f"\nError during clip extraction: {str(e)}")
            # Cleanup any leftover files
            for path in [base_output_path, final_output_path]:
                if os.path.exists(path):
                    os.remove(path)
            raise