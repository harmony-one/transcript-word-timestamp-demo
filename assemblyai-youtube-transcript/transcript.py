import argparse
import contextlib
import subprocess
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
            font_path = os.path.join('assets', 'Anton', 'Anton-Regular.ttf')

            if not os.path.exists(font_path):
                raise Exception(f"Font file not found at: {font_path}")
            
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
                        f"fontfile='{font_path}':"
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
        output_dir: str = "clips",
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
    def find_text_segment(transcript: aai.Transcript, 
                         start_text: str,
                         end_text: str,
                         similarity_threshold: int = 80) -> Optional[Tuple[float, float, str, float]]:
        """
        Find a segment between two pieces of text in the transcript.
        
        Args:
            transcript: AssemblyAI transcript
            start_text: Text to find the beginning of segment
            end_text: Text to find the end of segment
            similarity_threshold: Minimum similarity score (0-100)
            
        Returns:
            Tuple of (start_time, end_time, full_text, average_score) or None if not found
        """
        # Find occurrences of start and end text
        start_occurrences = AssemblyAITranscriptSearcher.find_phrase_occurrences(
            transcript, start_text, similarity_threshold)
        end_occurrences = AssemblyAITranscriptSearcher.find_phrase_occurrences(
            transcript, end_text, similarity_threshold)
        
        if not start_occurrences or not end_occurrences:
            return None
            
        # Get best start and end matches that form a valid segment
        for start_occ in start_occurrences:
            start_time = start_occ[0]
            for end_occ in end_occurrences:
                end_time = end_occ[1]
                
                # Check if segment is valid (end comes after start)
                if end_time > start_time:
                    # Get all words between start and end
                    segment_words = []
                    for word in transcript.words:
                        if start_time * 1000 <= word.start <= end_time * 1000:
                            segment_words.append(word.text)

                    full_text = ' '.join(segment_words)
                    average_score = (start_occ[3] + end_occ[3]) / 2
                    
                    return (start_time, end_time, full_text, average_score)
        
        return None

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


# def process_video(url: str, search_phrase: str, 
#                  similarity_threshold: int = 80,
#                  clip_duration: Optional[int] = 30,
#                  cleanup: bool = True,
#                  subtitle_mode: str = 'word') -> None:  # Add subtitle_mode parameter
#     """
#     Process YouTube video: download audio, transcribe, search, and optionally create clip.
    
#     Args:
#         url: YouTube URL
#         search_phrase: Phrase to search for
#         similarity_threshold: Minimum similarity score (0-100)
#         clip_duration: Duration of clip in seconds (None to skip clip creation)
#         cleanup: Whether to remove downloaded files after processing
#         subtitle_mode: Subtitle mode ('word', 'full', or 'none')
#     """
#     try:
#         # Check and truncate search phrase if necessary
#         words = search_phrase.split()
#         original_phrase = search_phrase
#         if len(words) > 5:
#             truncated_phrase = ' '.join(words[:5])
#             print(f"\nWarning: Search phrase exceeds 5 words.")
#             print(f"Original phrase: '{original_phrase}'")
#             print(f"Truncated phrase: '{truncated_phrase}'")
            
#             while True:
#                 response = input("\nDo you want to continue with the truncated phrase? (Y/n): ").strip().lower()
#                 if response in ['y', 'yes', '']:
#                     search_phrase = truncated_phrase
#                     break
#                 elif response in ['n', 'no']:
#                     print("\nProcess canceled. Please try again with a shorter phrase.")
#                     return
#                 else:
#                     print("Please answer 'Y' for yes or 'N' for no.")

#         # Get video ID
#         video_id = YouTubeHandler.get_video_id(url)
#         if not video_id:
#             raise ValueError("Invalid YouTube URL")

#         # Download audio
#         print("\nDownloading audio...")
#         audio_path = YouTubeHandler.download_audio(url)
        
#         # Transcribe and search
#         print(f"Transcribing audio... {audio_path}")
#         transcriber = aai.Transcriber()
#         transcript =  aai.Transcript.get_by_id('b329f1b0-5188-4033-b827-6b0b0cc23152') # transcriber.transcribe(audio_path)
        
#         searcher = AssemblyAITranscriptSearcher()
#         occurrences = searcher.find_phrase_occurrences(
#             transcript=transcript,
#             search_phrase=search_phrase,
#             similarity_threshold=similarity_threshold
#         )
        
#         # Display results
#         if not occurrences:
#             print(f"\nNo similar phrases found for '{search_phrase}'")
#             return

#         # Display all occurrences with index numbers
#         print(f"\nFound {len(occurrences)} matches, sorted by match score (highest first):")
#         for idx, (start_time, end_time, text, similarity) in enumerate(occurrences, 1):
#             formatted_time = searcher.format_time(start_time)
#             print(f"\nMatch #{idx}:")
#             print(f"Time: {formatted_time}")
#             print(f"Match score: {similarity:.1f}%")
#             print(f"Text: \"{text}\"")
#             print("YouTube URL with timestamp:")
#             print(f"https://youtube.com/watch?v={video_id}&t={int(start_time)}s")

#         # Ask if user wants to generate a clip
#         if clip_duration is not None:
#             while True:
#                 print("\nWould you like to generate a clip? Enter the match number or 'n' to skip")
#                 choice = input(f"Enter 1-{len(occurrences)} or 'n': ").strip().lower()
                
#                 if choice == 'n':
#                     print("Skipping clip generation.")
#                     break
                
#                 try:
#                     idx = int(choice)
#                     if 1 <= idx <= len(occurrences):
#                         # Get the selected occurrence
#                         start_time, end_time, text, _ = occurrences[idx-1]
                        
#                         # Set subtitle text based on mode
#                         subtitle_text = None if subtitle_mode == 'none' else text
#                         word_by_word = subtitle_mode == 'word'

#                         # Calculate clip end time in milliseconds
#                         clip_end_ms = (start_time + clip_duration) * 1000  # Convert to milliseconds
#                         clip_start_ms = start_time * 1000
                        
#                         # Get the word objects for this occurrence from the transcript until the duration time.
#                         occurrence_words = []
#                         for word in transcript.words:
#                             word_start_ms = word.start
#                             if word.start >= clip_start_ms and word.start <= clip_end_ms:
#                                 # Adjust end time if it exceeds clip duration
#                                 word_end_ms = min(word.end, clip_end_ms)
#                                 occurrence_words.append({
#                                     'text': word.text,
#                                     'start': word_start_ms,
#                                     'end': word_end_ms
#                                 })
                        
#                         # Generate clip with word timestamps
#                         max_retries = 2
#                         last_error = None
                        
#                         for attempt in range(max_retries):
#                             try:
#                                 print(f"\nAttempt {attempt + 1}/{max_retries} to extract video clip...")
#                                 clip_path = YouTubeHandler.extract_clip(
#                                     url=url,
#                                     start_time=start_time,
#                                     duration=clip_duration,
#                                     subtitle_text=subtitle_text,
#                                     word_by_word=word_by_word,
#                                     words=occurrence_words  # Pass the word objects
#                                 )
#                                 print(f"Clip saved to: {clip_path}")
#                                 break
#                             except Exception as e:
#                                 last_error = e
#                                 if attempt < max_retries - 1:
#                                     print(f"Retry {attempt + 1}/{max_retries} after error: {str(e)}")
#                                     time.sleep(1)
#                                 else:
#                                     print(f"Warning: All attempts to create clip failed. Last error: {str(last_error)}")
#                         break
#                     else:
#                         print(f"Please enter a number between 1 and {len(occurrences)}")
#                 except ValueError:
#                     print("Please enter a valid number or 'n'")

#         # Cleanup temporary files
#         if cleanup:
#             try:
#                 os.remove(audio_path)
#                 print("\nCleaned up temporary files")
#             except:
#                 pass
            
#     except Exception as e:
#         print(f"Error: {str(e)}")
#         sys.exit(1)


def process_video(url: str, search_phrase: str = None, 
                 start_text: str = None, end_text: str = None,
                 similarity_threshold: int = 80,
                 clip_duration: Optional[int] = 30,
                 cleanup: bool = True,
                 subtitle_mode: str = 'word') -> None:
    """Process YouTube video: download audio, transcribe, search, and create clip."""
    try:
        if search_phrase and (start_text or end_text):
            raise ValueError("Cannot specify both search_phrase and start/end text")
            
        if bool(start_text) != bool(end_text):
            raise ValueError("Must specify both start_text and end_text or neither")

        # Common setup
        video_id = YouTubeHandler.get_video_id(url)
        if not video_id:
            raise ValueError("Invalid YouTube URL")
            
        print("\nDownloading audio...")
        audio_path = YouTubeHandler.download_audio(url)
        
        print(f"Transcribing audio... {audio_path}")
        transcriber = aai.Transcriber()
        transcript = aai.Transcript.get_by_id('b329f1b0-5188-4033-b827-6b0b0cc23152') # transcriber.transcribe(audio_path)
        searcher = AssemblyAITranscriptSearcher()

        # Search phase
        occurrences = []
        if search_phrase:
            occurrences = searcher.find_phrase_occurrences(
                transcript=transcript,
                search_phrase=search_phrase,
                similarity_threshold=similarity_threshold
            )
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
                print(f"https://youtube.com/watch?v={video_id}&t={int(start_time)}s")

        else:  # Text segment search
            segment = searcher.find_text_segment(
                transcript=transcript,
                start_text=start_text,
                end_text=end_text,
                similarity_threshold=similarity_threshold
            )
            if not segment:
                print(f"\nNo matching segment found")
                return

            start_time, end_time, text, similarity = segment
            duration = end_time - start_time
            print(f"\nFound matching segment:")
            print(f"Start text: \"{start_text}\"")
            print(f"Start time: {searcher.format_time(start_time)}")
            print(f"End text: \"{end_text}\"")
            print(f"End time: {searcher.format_time(end_time)}")
            print(f"Full text: {text}")
            print(f"Duration: {int(duration)}s\n")
            print(f"YouTube URL: https://youtube.com/watch?v={video_id}&t={int(start_time)}s")
            occurrences = [(start_time, end_time, text, similarity)]

        # Clip generation phase
        if clip_duration is not None:
            choice = None
            if search_phrase:
                while True:
                    print("\nWould you like to generate a clip? Enter the match number or 'n' to skip")
                    choice = input(f"Enter 1-{len(occurrences)} or 'n': ").strip().lower()
                    if choice == 'n':
                        break
                    try:
                        idx = int(choice)
                        if 1 <= idx <= len(occurrences):
                            start_time, end_time, text, _ = occurrences[idx-1]
                            break
                    except ValueError:
                        print("Please enter a valid number or 'n'")
            else:
                choice = input("\nGenerate clip? (Y/n): ").strip().lower()
                if choice in ['y', 'yes', '']:
                    start_time, end_time, text, _ = occurrences[0]

            if choice != 'n':
                # Get words for the segment
                segment_words = []
                clip_duration = min(clip_duration, end_time - start_time) if end_time else clip_duration
                clip_end_ms = (start_time + clip_duration) * 1000
                clip_start_ms = start_time * 1000
                
                for word in transcript.words:
                    if clip_start_ms <= word.start <= clip_end_ms:
                        segment_words.append({
                            'text': word.text,
                            'start': word.start,
                            'end': min(word.end, clip_end_ms)
                        })
                
                subtitle_text = text if subtitle_mode != 'none' else None
                clip_path = YouTubeHandler.extract_clip(
                    url=url,
                    start_time=start_time,
                    duration=clip_duration,
                    subtitle_text=subtitle_text,
                    word_by_word=subtitle_mode == 'word',
                    words=segment_words
                )
                print(f"Clip saved to: {clip_path}")

        # Cleanup
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
    parser.add_argument(
        '--subtitles',
        choices=['word', 'full', 'none'],
        default='word',
        help='Subtitle mode: word-by-word (default), full text, or none'
    )
    
    try:
        args = parser.parse_args()
        process_video(
            url=args.url,
            search_phrase=args.phrase,
            similarity_threshold=args.threshold,
            clip_duration=args.clip_duration if args.clip_duration > 0 else None,
            cleanup=not args.no_cleanup,
            subtitle_mode=args.subtitles
        )
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Critical error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
