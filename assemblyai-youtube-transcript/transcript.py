import argparse
import contextlib
import time
from urllib.parse import parse_qs, urlparse
from rapidfuzz import fuzz, process
from typing import List, Dict, Optional, Tuple
from yt_dlp.utils import download_range_func
from subprocess import DEVNULL
from typing import Optional


import assemblyai as aai
import yt_dlp
import config as app_config
import sys
import os

aai.settings.api_key = app_config.config.ASSEMBLYAI_AUTH_KEY

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
    def download_audio(url: str, output_dir: str = "temp") -> str:
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
    def extract_clip(url: str, start_time: float, duration: int = 30, 
                    output_dir: str = "clips") -> str:
        """
        Extract video clip, optimized for short segments.
        """
        os.makedirs(output_dir, exist_ok=True)
        
        video_id = YouTubeHandler.get_video_id(url)
        final_output = f"{video_id}_clip_{int(start_time)}.mp4"
        final_output_path = os.path.join(output_dir, final_output)

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
                # Fix the output template format
                'outtmpl': {
                    'default': os.path.join(output_dir, '%(id)s_clip_%(time)s.%(ext)s')
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
            print(f"Debug: Final output path: {final_output_path}")

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    # Get the actual output filename from yt-dlp
                    downloaded_file = ydl.prepare_filename(info)
                    print(f"Debug: Downloaded file: {downloaded_file}")
                    
                    if os.path.exists(downloaded_file):
                        # Rename to our desired filename if different
                        if downloaded_file != final_output_path:
                            os.rename(downloaded_file, final_output_path)
                        print(f"\nClip successfully created at: {final_output_path}")
                        return final_output_path
                    else:
                        raise Exception(f"Downloaded file not found at: {downloaded_file}")

            except Exception as e:
                print(f"Debug: YDL error: {str(e)}")
                raise

        except Exception as e:
            print(f"\nError during clip extraction: {str(e)}")
            if os.path.exists(final_output_path):
                os.remove(final_output_path)
            raise

        
class AssemblyAITranscriptSearcher:
    def compare_phrases(phrase1: str, phrase2: str) -> Tuple[float, float, float]:
        """
        Compare two phrases using different fuzzy matching strategies.
        Returns tuple of (ratio, partial_ratio, token_sort_ratio)
        """
        return (
            fuzz.ratio(phrase1.lower(), phrase2.lower()),
            fuzz.partial_ratio(phrase1.lower(), phrase2.lower()),
            fuzz.token_sort_ratio(phrase1.lower(), phrase2.lower())
        )

    @staticmethod
    def find_phrase_occurrences(transcript: aai.Transcript, 
        search_phrase: str, 
        similarity_threshold: int = 80) -> List[Tuple[float, float, str, float]]:
        """
        Find phrases in the transcript using fuzzy matching.
        
        Returns:
        List of tuples containing (start_time, end_time, text, best_score), 
        sorted by best_score in descending order (highest scores first).
        """
        occurrences = []
        search_phrase = search_phrase.lower()
        search_words = search_phrase.split()
        search_word_count = len(search_words)
        
        words = transcript.words
        
        for i in range(len(words) - search_word_count + 1):
            sequence_words = words[i:i + search_word_count]
            sequence_text = ' '.join(word.text for word in sequence_words)
            
            ratio, partial_ratio, token_ratio = AssemblyAITranscriptSearcher.compare_phrases(
                search_phrase, sequence_text
            )
            
            best_score = max(ratio, partial_ratio, token_ratio)
            
            if best_score >= similarity_threshold:
                start_time = sequence_words[0].start / 1000
                end_time = sequence_words[-1].end / 1000
                
                occurrences.append((
                    start_time,
                    end_time,
                    sequence_text,
                    best_score
                ))
        
        # Sort occurrences primarily by best_score in descending order
        occurrences.sort(key=lambda x: (-x[3]))  # Only sort by best_score (index 3)
        
        # Filter out overlapping occurrences, keeping the ones with higher scores
        filtered_occurrences = []
        for occ in occurrences:
            # Check if there's already a similar occurrence with higher or equal score
            similar_exists = any(
                abs(existing[0] - occ[0]) < 0.5 and
                existing[3] >= occ[3]  # Compare scores
                for existing in filtered_occurrences
            )
            if not similar_exists:
                filtered_occurrences.append(occ)

        return filtered_occurrences

    @staticmethod
    def format_time(seconds: float) -> str:
        """Format seconds into HH:MM:SS."""
        seconds = round(seconds)
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def process_video(url: str, search_phrase: str, 
                 similarity_threshold: int = 80,
                 clip_duration: Optional[int] = 30,
                 cleanup: bool = True) -> None:
    """
    Process YouTube video: download audio, transcribe, search, and optionally create clip.
    
    Args:
        url: YouTube URL
        search_phrase: Phrase to search for
        similarity_threshold: Minimum similarity score (0-100)
        clip_duration: Duration of clip in seconds (None to skip clip creation)
        cleanup: Whether to remove downloaded files after processing
    """
    try:
        # Check and truncate search phrase if necessary
        words = search_phrase.split()
        original_phrase = search_phrase
        
        if len(words) > 5:
            truncated_phrase = ' '.join(words[:5])
            print(f"\nWarning: Search phrase exceeds 5 words.")
            print(f"Original phrase: '{original_phrase}'")
            print(f"Truncated phrase: '{truncated_phrase}'")
            
            while True:
                response = input("\nDo you want to continue with the truncated phrase? (Y/n): ").strip().lower()
                if response in ['y', 'yes', '']:
                    search_phrase = truncated_phrase
                    break
                elif response in ['n', 'no']:
                    print("\nProcess canceled. Please try again with a shorter phrase.")
                    return
                else:
                    print("Please answer 'Y' for yes or 'N' for no.")

        # # Get video ID and create YouTube handler
        video_id = YouTubeHandler.get_video_id(url)
        if not video_id:
            raise ValueError("Invalid YouTube URL")

        # # Download audio
        print("Downloading audio...")
        audio_path = YouTubeHandler.download_audio(url)
        
        # Transcribe and search
        print(f"Transcribing audio... {audio_path}")
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_path) # aai.Transcript.get_by_id('b329f1b0-5188-4033-b827-6b0b0cc23152') # transcriber.transcribe(audio_path)
        searcher = AssemblyAITranscriptSearcher()
        occurrences = searcher.find_phrase_occurrences(
            transcript=transcript,
            search_phrase=search_phrase,
            similarity_threshold=similarity_threshold
        )
        
        # Display results
        if not occurrences:
            print(f"\nNo similar phrases found for '{search_phrase}'")
            return
       
         # Display all occurrences with index numbers
        print(f"\nFound {len(occurrences)} matches, sorted by match score (highest first):")
        for idx, (start_time, end_time, text, similarity) in enumerate(occurrences, 1):
            formatted_time = searcher.format_time(start_time)
            print(f"\nMatch #{idx}:")
            print(f"Time: {formatted_time}")
            print(f"Match score: {similarity:.1f}%")
            print(f"Text: \"{text}\"")
            print("YouTube URL with timestamp:")
            print(f"https://youtube.com/watch?v={video_id}&t={int(start_time)}s")

        # Ask if user wants to generate a clip
        if clip_duration is not None:
            while True:
                print("\nWould you like to generate a clip? Enter the match number or 'n' to skip")
                choice = input(f"Enter 1-{len(occurrences)} or 'n': ").strip().lower()
                
                if choice == 'n':
                    print("Skipping clip generation.")
                    break
                
                try:
                    idx = int(choice)
                    if 1 <= idx <= len(occurrences):
                        # Get the selected occurrence
                        start_time = occurrences[idx-1][0]
                        
                        # Generate clip
                        max_retries = 2
                        last_error = None
                        
                        for attempt in range(max_retries):
                            try:
                                print(f"\nAttempt {attempt + 1}/{max_retries} to extract video clip...")
                                clip_path = YouTubeHandler.extract_clip(
                                    url=url,
                                    start_time=start_time,
                                    duration=clip_duration
                                )
                                print(f"Clip saved to: {clip_path}")
                                break
                            except Exception as e:
                                last_error = e
                                if attempt < max_retries - 1:
                                    print(f"Retry {attempt + 1}/{max_retries} after error: {str(e)}")
                                    time.sleep(1)
                                else:
                                    print(f"Warning: All attempts to create clip failed. Last error: {str(last_error)}")
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(occurrences)}")
                except ValueError:
                    print("Please enter a valid number or 'n'")

        # Cleanup temporary files
        if cleanup:
            try:
                os.remove(audio_path)
                print("\nCleaned up temporary files")
            except:
                pass
            
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Search YouTube videos for similar phrases (max 5 words)'
    )
    parser.add_argument('url', help='YouTube video URL')
    parser.add_argument('phrase', help='Phrase to search for (will be truncated to first 5 words if longer)')
    parser.add_argument(
        '--threshold', 
        type=int, 
        default=80,
        help='Minimum similarity threshold (0-100)'
    )
    parser.add_argument(
        '--clip-duration',
        type=int,
        default=30,
        help='Duration of extracted clips in seconds (0 to disable)'
    )
    parser.add_argument(
        '--no-cleanup',
        action='store_true',
        help='Do not delete temporary files after processing'
    )
    
    try:
        args = parser.parse_args()
        process_video(
            url=args.url,
            search_phrase=args.phrase,
            similarity_threshold=args.threshold,
            clip_duration=args.clip_duration if args.clip_duration > 0 else None,
            cleanup=not args.no_cleanup
        )
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Critical error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
