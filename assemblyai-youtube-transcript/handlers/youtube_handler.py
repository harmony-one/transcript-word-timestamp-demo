import subprocess
from urllib.parse import parse_qs, urlparse
from typing import List, Optional
from yt_dlp.utils import download_range_func
from subprocess import DEVNULL
from typing import Optional
from config import config as app_config

import yt_dlp
import os

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

    @staticmethod
    def add_word_subtitles_to_clip(input_file: str, output_file: str, 
                            words: List[dict],
                            duration: int,
                            font_size: int = 48) -> bool:
        """
        Add word subtitles to video clip using a single FFmpeg command.
        """
        try:
            filter_complex = []
            clip_start_ms = words[0]['start']

            if not os.path.exists(app_config.FONT_PATH):
                raise Exception(f"Font file not found at: {app_config.FONT_PATH}")
            
            # Process all words in a single command
            for word in words:
                word_start = (word['start'] - clip_start_ms) / 1000
                word_end = (word['end'] - clip_start_ms) / 1000
                
                if word_start < duration and word_end > 0:
                    word_start = max(0, word_start)
                    word_end = min(duration, word_end)
                    escaped_word = word['text'].upper().replace("'", "'\\''").replace('"', '\\"')
                    
                    filter_complex.append(
                        f"drawtext=text='{escaped_word}':"
                        f"fontsize={font_size}:"
                        f"fontfile='{app_config.FONT_PATH}':"
                        f"fontcolor=lime@1.0:"
                        f"borderw=3:"
                        f"bordercolor=black@1.0:"
                        f"x=(w-text_w)/2:"
                        f"y=h-h/4:"
                        f"enable='between(t,{word_start},{word_end})'"
                    )
            
            # Single FFmpeg command with all filters
            filter_string = ','.join(filter_complex)
            cmd = [
                'ffmpeg',
                '-i', input_file,
                '-vf', filter_string,
                '-c:a', 'copy',
                '-y',
                output_file
            ]
            
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if result.returncode == 0 and os.path.exists(output_file):
                print("Word subtitles added successfully")
                return True
            else:
                raise Exception("Failed to create subtitled video")
                
        except Exception as e:
            print(f"Error adding word subtitles: {str(e)}")
            return False
    
    @staticmethod
    def extract_clip(
        url: str,
        start_time: float,
        duration: int = 30, 
        output_dir: str = app_config.DEFAULT_OUTPUT_DIR,
        subtitle_text: Optional[str] = None, 
        word_by_word: bool = False,
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
            subtitle_type = "word" if word_by_word else "full"
            final_output_path = os.path.join(
                output_dir, 
                f"{video_id}_clip_{int(start_time)}_{subtitle_type}_subtitled.mp4"
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
            print(f"Debug: Final output path: {final_output_path}")

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
                        if word_by_word:
                            # Split text into words and remove empty strings
                            # words = [w for w in subtitle_text.split() if w]
                            success = YouTubeHandler.add_word_subtitles_to_clip(
                                base_output_path,
                                final_output_path,
                                words,
                                duration=duration
                            )
                        else:
                            success = YouTubeHandler.add_subtitles_to_clip(
                                base_output_path,
                                final_output_path,
                                subtitle_text,
                                duration=duration
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
                
                return base_output_path

        except Exception as e:
            print(f"\nError during clip extraction: {str(e)}")
            # Cleanup any leftover files
            for path in [base_output_path, final_output_path]:
                if os.path.exists(path):
                    os.remove(path)
            raise