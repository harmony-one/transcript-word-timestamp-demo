# main.py
import argparse
import os
import sys
from typing import Optional
import assemblyai as aai
from config import config as app_config
from handlers import YouTubeHandler, TranscriptionHandler
from searchers import FuzzySearcher
from utils import format_time, get_segment_texts, parse_arguments

def process_video(url: str, search_phrase: str = None, 
                 start_text: str = None, end_text: str = None,
                 similarity_threshold: int = app_config.DEFAULT_SIMILARITY_THRESHOLD,
                 clip_duration: Optional[int] = app_config.DEFAULT_CLIP_DURATION,
                 cleanup: bool = True,
                 subtitle_mode: str = app_config.DEFAULT_SUBTITLE_MODE) -> None:
    
    youtube_handler = YouTubeHandler()
    searcher = FuzzySearcher()
    transcriber = TranscriptionHandler(searcher) 

    try:
        if search_phrase and (start_text or end_text):
            raise ValueError("Cannot specify both search_phrase and start/end text")
            
        if bool(start_text) != bool(end_text):
            raise ValueError("Must specify both start_text and end_text or neither")

        video_id = youtube_handler.get_video_id(url)
        if not video_id:
            raise ValueError("Invalid YouTube URL")
        
        print("\nDownloading audio...")
        audio_path = youtube_handler.download_audio(url)
        
        print(f"Transcribing audio... {audio_path}")
        transcript = transcriber.transcribe(audio_path)

        # Search phase
        occurrences = []
        if search_phrase:
            words = search_phrase.split()
            if len(words) > 5:
                truncated_phrase = ' '.join(words[:5])
                print(f"\nWarning: Search phrase truncated to: '{truncated_phrase}'")
                search_phrase = truncated_phrase

            occurrences = transcriber.find_phrase_occurrences(
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
                formatted_time = format_time(start_time)
                print(f"\nMatch #{idx}:")
                print(f"Time: {formatted_time}")
                print(f"Match score: {similarity:.1f}%")
                print(f"Text: \"{text}\"")
                print(f"https://youtube.com/watch?v={video_id}&t={int(start_time)}s")

        else: # Text segment search
            segment = transcriber.find_text_segment(
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
            print(f"Start time: {format_time(start_time)}")
            print(f"End text: \"{end_text}\"")
            print(f"End time: {format_time(end_time)}")
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
                    word_by_word=subtitle_mode == app_config.DEFAULT_SUBTITLE_MODE,
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
    args = parse_arguments()
    
    try:        
        if args.phrase:
            process_video(
                url=args.url,
                search_phrase=args.phrase,
                similarity_threshold=args.threshold,
                clip_duration=args.clip_duration if args.clip_duration > 0 else None,
                cleanup=not args.no_cleanup,
                subtitle_mode=args.subtitles
            )
        else:  # args.text
            start_text, end_text = get_segment_texts(args.text)
            print(f"\nSearching with segments:")
            print(f"Start: '{start_text}'")
            print(f"End: '{end_text}'")
            
            process_video(
                url=args.url,
                start_text=start_text,
                end_text=end_text,
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


