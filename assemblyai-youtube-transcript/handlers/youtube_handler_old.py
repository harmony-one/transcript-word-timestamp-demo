import traceback
from urllib.parse import parse_qs, urlparse
from typing import List, Optional
from yt_dlp.utils import download_range_func
from subprocess import DEVNULL
from typing import Optional
from config import config as app_config
from enum import Enum
import yt_dlp
import os
import subprocess

class SubtitleConfig:
    """Configuration class for subtitle styling"""
    ACTIVE_COLOR = 'purple'     # Color for the currently spoken word
    INACTIVE_COLOR = 'gray'     # Color for other visible words
    DEFAULT_WINDOW_SIZE = 5     # Number of words visible at once
    FONT_SIZE = 48             # Base font size
    FONT_PATH = app_config.ANTON_FONT_PATH
    
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


    def add_subtitles_to_clip(input_file, output_file, words, duration, mode, window_size, font_size):
        try:
            filter_complex = []
            clip_start_ms = words[0]['start']
            
            if mode == SubtitleMode.WORD:
                for word in words:
                    word_start = (word['start'] - clip_start_ms) / 1000
                    word_end = (word['end'] - clip_start_ms) / 1000
                    
                    if word_start < duration and word_end > 0:
                        word_start = max(0, word_start)
                        word_end = min(duration, word_end)
                        escaped_word = word['text'].upper().replace("'", "'\\''").replace('"', '\\"')
                        filter_complex.append(
                            f"drawtext=text='{escaped_word}':"
                            f"fontsize={font_size}:fontfile='{app_config.ANTON_FONT_PATH}':"
                            f"fontcolor=lime@1.0:borderw=3:bordercolor=black@1.0:"
                            f"x=(w-text_w)/2:y=h-h/4:"
                            f"enable='between(t,{word_start},{word_end})'"
                        )
            else:  # PHRASE mode
                for i in range(0, len(words), window_size):
                    window_words = words[i:i + window_size]
                    text = ' '.join(word['text'] for word in window_words)
                    
                    phrase_start = (window_words[0]['start'] - clip_start_ms) / 1000
                    if i < len(words) - window_size:
                        phrase_end = (words[i + window_size]['start'] - clip_start_ms) / 1000
                    else:
                        phrase_end = (window_words[-1]['end'] - clip_start_ms) / 1000
                    
                    filter_complex.append(
                        f"drawtext=text='{escape_text(text.upper())}':"
                        f"fontsize={font_size}:fontfile='{app_config.ANTON_FONT_PATH}':"
                        f"fontcolor=white:borderw=2:bordercolor=black:"
                        f"x=(w-text_w)/2:y=h-h/4:"
                        f"enable='between(t,{phrase_start},{phrase_end})'"
                    )

                    for word_idx, word in enumerate(window_words):
                        word_start = (word['start'] - clip_start_ms) / 1000
                        word_end = (word['end'] - clip_start_ms) / 1000
                        
                        # Calculate position for each word in the window
                        chars_before = sum(len(w['text']) for w in window_words[:word_idx]) + word_idx  # Add spaces
                        word_width = len(word['text'])
                        total_chars = sum(len(w['text']) for w in window_words) + len(window_words) - 1
                        
                        x_offset = f"(w-text_w)/2+{chars_before}*{font_size/2}"
                        
                        filter_complex.append(
                            f"drawtext=text='{escape_text(word['text'].upper())}':"
                            f"fontsize={font_size}:fontfile='{app_config.ANTON_FONT_PATH}':"
                            f"x={x_offset}:y=h-h/4:fontcolor=#00000000:"
                            f"box=1:boxcolor=purple@0.3:boxborderw=0:"
                            f"enable='between(t,{word_start},{word_end})'"
                        )




            return YouTubeHandler.execute_ffmpeg(input_file, output_file, filter_complex)
        except Exception as e:
            print(f"Error adding subtitles: {str(e)}")
            return False

    def highlight_active_word(input_file, output_file, words, duration, window_size, font_size):
        try:
            filter_complex = []
            clip_start_ms = words[0]['start']
            
            for i in range(0, len(words), window_size):
                window_words = words[i:i + window_size]
                
                for word_idx, word in enumerate(window_words):
                    word_start = (word['start'] - clip_start_ms) / 1000
                    word_end = (word['end'] - clip_start_ms) / 1000
                    
                    # Calculate position for each word in the window
                    chars_before = sum(len(w['text']) for w in window_words[:word_idx]) + word_idx  # Add spaces
                    word_width = len(word['text'])
                    total_chars = sum(len(w['text']) for w in window_words) + len(window_words) - 1
                    
                    x_offset = f"(w-text_w)/2+{chars_before}*{font_size/2}"
                    
                    filter_complex.append(
                        f"drawtext=text='{escape_text(word['text'].upper())}':"
                        f"fontsize={font_size}:fontfile='{app_config.ANTON_FONT_PATH}':"
                        f"x={x_offset}:y=h-h/4:fontcolor=#00000000:"
                        f"box=1:boxcolor=purple@0.3:boxborderw=0:"
                        f"enable='between(t,{word_start},{word_end})'"
                    )

            return YouTubeHandler.execute_ffmpeg(input_file, output_file, filter_complex)
        except Exception as e:
            print(f"Error adding highlights: {str(e)}")
            return False
    
    def execute_ffmpeg(input_file, output_file, filter_complex):
        try:
            filter_string = ','.join(filter_complex)
            cmd = [
                'ffmpeg',
                '-i', input_file,
                '-vf', filter_string,
                '-c:a', 'copy',
                '-y',
                output_file
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print("FFmpeg error:", result.stderr)
            return os.path.exists(output_file) and os.path.getsize(output_file) > 0
        except Exception as e:
            print(f"Error executing FFmpeg: {str(e)}")
            return False
    
    # def add_subtitles_to_clip(
    #     input_file: str,
    #     output_file: str, 
    #     words: List[dict],
    #     duration: int,
    #     mode: SubtitleMode = SubtitleMode.WORD,
    #     window_size: int = SubtitleConfig.DEFAULT_WINDOW_SIZE,
    #     font_size: int = SubtitleConfig.FONT_SIZE
    # ) -> bool:
    #     """
    #     Add subtitles to video clip using FFmpeg with support for word-by-word
    #     and phrase modes with highlighting.
        
    #     Args:
    #         input_file: Path to input video file
    #         output_file: Path to output video file
    #         words: List of word dictionaries with timing info
    #         duration: Clip duration in seconds
    #         mode: SubtitleMode.WORD or SubtitleMode.PHRASE
    #         window_size: Number of words to show at once in phrase mode
    #         font_size: Base font size for the text
    #     """
    #     try:
    #         if not os.path.exists(SubtitleConfig.FONT_PATH):
    #             raise Exception(f"Font file not found at: {SubtitleConfig.FONT_PATH}")

    #         print("Total words received:", len(words))
    #         print("First few words:", words[:3])
            
    #         clip_start_ms = words[0]['start']
    #         filter_complex = []
    #         if mode == SubtitleMode.WORD:
    #             for word in words:
    #                 word_start = (word['start'] - clip_start_ms) / 1000
    #                 word_end = (word['end'] - clip_start_ms) / 1000
                    
    #                 if word_start < duration and word_end > 0:
    #                     word_start = max(0, word_start)
    #                     word_end = min(duration, word_end)
    #                     escaped_word = word['text'].upper().replace("'", "'\\''").replace('"', '\\"')
                        
    #                     filter_complex.append(
    #                     f"drawtext=text='{escaped_word}':"
    #                     f"fontsize={font_size}:"
    #                     f"fontfile='{app_config.ANTON_FONT_PATH}':"
    #                     f"fontcolor=lime@1.0:"
    #                     f"borderw=3:"
    #                     f"bordercolor=black@1.0:"
    #                     f"x=(w-text_w)/2:"
    #                     f"y=h-h/4:"
    #                     f"enable='between(t,{word_start},{word_end})'"
    #                 )

    #         else:  # PHRASE mode
    #             # Process words in fixed windows with overlap handling
    #             total_windows = (len(words) + window_size - 1) // window_size
    #             print(f"Expected number of windows: {total_windows}")
                
    #             for i in range(total_windows):
    #                 start_idx = i * window_size
    #                 end_idx = min(start_idx + window_size, len(words))
                    
    #                 # Get current window of words
    #                 window_words = words[start_idx:end_idx]
    #                 print(f"Window {i + 1}: {[w['text'] for w in window_words]}")
                    
    #                 if not window_words:
    #                     continue
                    
    #                 # Build the phrase for this window
    #                 phrase = ' '.join(word['text'] for word in window_words)
    #                 escaped_phrase = escape_text(phrase).upper()
                    
    #                 # Calculate proper timing for the phrase
    #                 phrase_start = (window_words[0]['start'] - clip_start_ms) / 1000
                    
    #                 # For all windows except the last, use next window's start as end
    #                 if i < total_windows - 1 and start_idx + window_size < len(words):
    #                     next_word = words[start_idx + window_size]
    #                     phrase_end = (next_word['start'] - clip_start_ms) / 1000
    #                 else:
    #                     # For the last window, use the last word's end time
    #                     phrase_end = (window_words[-1]['end'] - clip_start_ms) / 1000
                    
    #                 if phrase_start < duration and phrase_end > 0:
    #                     phrase_start = max(0, phrase_start)
    #                     phrase_end = min(duration, phrase_end)
                        
    #                     print(f"Adding phrase: '{phrase}' from {phrase_start} to {phrase_end}")
                        
    #                     # Draw the entire phrase
    #                     filter_complex.append(
    #                         f"drawtext=text='{escaped_phrase}'"
    #                         f":fontsize={font_size}"
    #                         f":fontfile='{app_config.ANTON_FONT_PATH}'"
    #                         f":fontcolor=white"
    #                         f":borderw=2"
    #                         f":bordercolor=black"
    #                         f":x=(w-text_w)/2"
    #                         f":y=h-h/4"
    #                         f":enable='between(t,{phrase_start},{phrase_end})'"
    #                 )

    #         print("Number of windows created:", len(range(0, len(words), window_size)))
    #         print("Number of filters created:", len(filter_complex))

    #         filter_string = ','.join(filter_complex)
    #         cmd = [
    #             'ffmpeg',
    #             '-i', input_file,
    #             '-vf', filter_string,
    #             '-c:a', 'copy',
    #             '-y',
    #             output_file
    #         ]
        
    #         result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    #         return result.returncode == 0 and os.path.exists(output_file)
                    
    #     except Exception as e:
    #         print(f"Error adding subtitles: {str(e)}")
    #         return False
        

    # def highlight_active_word(
    #         input_file: str,
    #         output_file: str,
    #         words: List[dict],
    #         duration: int,
    #         window_size: int = SubtitleConfig.DEFAULT_WINDOW_SIZE,
    #         font_size: int = SubtitleConfig.FONT_SIZE
    #     ) -> bool:
    #     """
    #     Add highlighting to active words in a video that already has base subtitles.
    #     """
    #     try:
    #         if not os.path.exists(SubtitleConfig.FONT_PATH):
    #             raise Exception(f"Font file not found at: {SubtitleConfig.FONT_PATH}")

    #         clip_start_ms = words[0]['start']
    #         filter_complex = []

    #         # Process words in fixed windows
    #         total_windows = (len(words) + window_size - 1) // window_size
            
    #         for i in range(total_windows):
    #             start_idx = i * window_size
    #             end_idx = min(start_idx + window_size, len(words))
    #             window_words = words[start_idx:end_idx]
                
    #             if not window_words:
    #                 continue
                    
    #             # For each word in the window, create a highlight overlay
    #             for word_idx, word in enumerate(window_words):
    #                 word_start = (word['start'] - clip_start_ms) / 1000
    #                 word_end = (word['end'] - clip_start_ms) / 1000
                    
    #                 if word_start < duration and word_end > 0:
    #                     word_start = max(0, word_start)
    #                     word_end = min(duration, word_end)
                        
    #                     # Create highlight box effect
    #                     filter_complex.append(
    #                         f"drawbox=x=w/2-150:y=h-h/4-24"
    #                         f":w=300:h=48"
    #                         f":color=purple@0.3:t=fill"
    #                         f":enable='between(t,{word_start},{word_end})'"
    #                     )

    #         # Combine all filters with commas
    #         filter_string = ','.join(item for item in filter_complex if item)
            
    #         if not filter_string:
    #             print("No valid filters generated")
    #             return False

    #         cmd = [
    #             'ffmpeg',
    #             '-i', input_file,
    #             '-vf', filter_string,
    #             '-c:a', 'copy',
    #             '-y',
    #             output_file
    #         ]
            
    #         result = subprocess.run(cmd, capture_output=True, text=True)
            
    #         if result.returncode != 0:
    #             print("FFmpeg error output:", result.stderr)
    #             return False
                
    #         return os.path.exists(output_file)
                    
    #     except Exception as e:
    #         print(f"Error adding highlights: {str(e)}")
    #         print(f"Full traceback: {traceback.format_exc()}")
    #         return False


    def process_video_with_highlights(
        input_file: str,
        output_file: str,
        words: List[dict],
        duration: int,
        window_size: int = SubtitleConfig.DEFAULT_WINDOW_SIZE,
        font_size: int = SubtitleConfig.FONT_SIZE
    ) -> bool:
        """
        Process video in two passes:
        1. Add base subtitles
        2. Add highlighting for active words
        """

        # Create temporary file for intermediate result
        temp_file = output_file.replace('.mp4', '_temp.mp4')
        
        try:
            # First pass: Add base subtitles
            if not YouTubeHandler.add_subtitles_to_clip(
                input_file=input_file,
                output_file=temp_file,
                words=words,
                duration=duration,
                mode=SubtitleMode.PHRASE,
                window_size=window_size,
                font_size=font_size
            ):
                raise Exception("Failed to add base subtitles")

            print('AFTER YouTubeHandler.add_subtitles_to_clip')    
            # Second pass: Add highlights
            success = YouTubeHandler.highlight_active_word(
                input_file=temp_file,
                output_file=output_file,
                words=words,
                duration=duration,
                window_size=window_size,
                font_size=font_size
            )
            print('AFTER YouTubeHandler.highlight_active_word YouTubeHandler.highlight_active_word', success)   
            # Clean up temporary file
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
            return True #success
            
        except Exception as e:
            print(f"Error in two-pass processing: {str(e)}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False
    

    @staticmethod
    def extract_clip(
        url: str,
        start_time: float,
        duration: int = 30, 
        output_dir: str = app_config.DEFAULT_OUTPUT_DIR,
        subtitle_text: Optional[str] = None, 
        subtitle_mode: SubtitleMode = SubtitleMode.WORD,  # CHANGED: replaced word_by_word with subtitle_mode
        window_size: int = 5,  # CHANGED: added window_size parameter
        words: List[dict] = []
    ) -> str:
        """
        Extract video clip, optimized for short segments.
        """
        os.makedirs(output_dir, exist_ok=True)

        video_id = YouTubeHandler.get_video_id(url)
        base_output = f"{video_id}_clip_{int(start_time)}.mp4"
        base_output_path = os.path.join(output_dir, base_output)

        # If subtitles are requested, prepare subtitle output path
        if subtitle_text:
            final_output_path = os.path.join(
                output_dir, 
                f"{video_id}_clip_{int(start_time)}_{subtitle_mode}_subtitled.mp4"
            )
        else:
            final_output_path = base_output_path

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
                
                # Add subtitles if requested
                if subtitle_text:
                    try:
                        success = False
                        if subtitle_mode == SubtitleMode.WORD:
                            success = YouTubeHandler.add_subtitles_to_clip(
                                base_output_path,
                                final_output_path,
                                words,
                                duration=duration,
                                mode=SubtitleMode.WORD,
                                window_size=window_size,
                                font_size=SubtitleConfig.FONT_SIZE
                            )
                        else:
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
                            # os.remove(base_output_path)
                            print(f"Subtitles added successfully")
                            return final_output_path
                        else:
                            print(f"Warning: Failed to add subtitles, returning original clip")
                            return base_output_path
                            
                    except Exception as e:
                        print(f"Warning: Failed to add subtitles: {str(e)}, returning original clip")
                        return base_output_path
                
                return base_output_path

        except Exception as e:
            print(f"\nError during clip extraction: {str(e)}")
            # Cleanup any leftover files
            for path in [base_output_path, final_output_path]:
                if os.path.exists(path):
                    os.remove(path)
            raise