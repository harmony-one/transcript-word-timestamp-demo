import os
import sys
import traceback
from typing import Optional
from config import config as app_config
from handlers import YouTubeHandler, TranscriptionHandler, SubtitleConfig
from searchers import FuzzySearcher
from utils import format_time, get_segment_texts, parse_arguments, setup_logger, parse_srt_file

logger = setup_logger('main')

def process_video(url: str, search_phrase: str = None, 
                start_text: str = None, end_text: str = None,
                srt_file: str = None,
                similarity_threshold: int = app_config.DEFAULT_SIMILARITY_THRESHOLD,
                clip_duration: Optional[int] = app_config.DEFAULT_CLIP_DURATION,
                cleanup: bool = True,
                window_size: int = SubtitleConfig.DEFAULT_WINDOW_SIZE) -> None:
    
    youtube_handler = YouTubeHandler()
    searcher = FuzzySearcher()
    transcriber = TranscriptionHandler(searcher) 

    try:
        logger.info("Starting video processing")

        if srt_file:
            logger.info(f"Using provided SRT file: {srt_file}")
            # Add debug logging for SRT file handling
            if not os.path.exists(srt_file):
                logger.error(f"SRT file not found at path: {srt_file}")
                raise FileNotFoundError(f"SRT file not found: {srt_file}")

            words = parse_srt_file(srt_file)
            logger.debug(f"Parsed {len(words)} words from SRT file")
            
            if not words:
                logger.error("No valid subtitles found in SRT file")
                return
                
            # Use the first word's timestamp as start time
            start_time = words[0]['start'] / 1000.0  # Convert to seconds
            logger.debug(f"Using start time: {start_time} seconds")

            # If no clip duration specified, use the time between first and last word
            
            clip_duration = (words[-1]['end'] - words[0]['start']) / 1000.0
            logger.info(f"Calculated clip duration: {clip_duration} seconds")
            
            clip_path = YouTubeHandler.extract_clip(
                url=url,
                start_time=start_time,
                duration=clip_duration,
                words=words,
                window_size=window_size
            )
            logger.info(f"Clip saved to: {clip_path}")
            return
        
        logger.debug(f"Parameters: similarity_threshold={similarity_threshold}, clip_duration={clip_duration}")

        if search_phrase and (start_text or end_text):
            logger.error("Cannot specify both search_phrase and start/end text")
            raise ValueError("Cannot specify both search_phrase and start/end text")
            
        if bool(start_text) != bool(end_text):
            logger.error("Must specify both start_text and end_text or neither")
            raise ValueError("Must specify both start_text and end_text or neither")

        video_id = youtube_handler.get_video_id(url)
        if not video_id:
            logger.error("Invalid YouTube URL provided")
            raise ValueError("Invalid YouTube URL")
        
        logger.info("Downloading audio...")
        audio_path = youtube_handler.download_audio(url)
        
        logger.info(f"Transcribing audio from: {audio_path}")
        transcript = transcriber.transcribe(audio_path)
        logger.debug("Transcription complete")


        # Search phase
        occurrences = []
        if search_phrase:
            words = search_phrase.split()
            if len(words) > 5:
                truncated_phrase = ' '.join(words[:5])
                logger.warning(f"Search phrase truncated from '{search_phrase}' to '{truncated_phrase}'")
                search_phrase = truncated_phrase

            logger.info(f"Searching for phrase: '{search_phrase}'")
            occurrences = transcriber.find_phrase_occurrences(
                transcript=transcript,
                search_phrase=search_phrase,
                similarity_threshold=similarity_threshold
            )
            if not occurrences:
                logger.warning(f"No similar phrases found for '{search_phrase}'")
                return

            # Display all occurrences with index numbers
            logger.info(f"Found {len(occurrences)} matches")
            for idx, (start_time, end_time, text, similarity) in enumerate(occurrences, 1):
                formatted_time = format_time(start_time)
                logger.info(f"\nMatch #{idx}:")
                logger.info(f"Time: {formatted_time}")
                logger.info(f"Match score: {similarity:.1f}%")
                logger.info(f"Text: \"{text}\"")
                logger.info(f"URL: https://youtube.com/watch?v={video_id}&t={int(start_time)}s")


        else: # Text segment search
            logger.info("Searching for text segment")
            logger.debug(f"Start text: '{start_text}'")
            logger.debug(f"End text: '{end_text}'")
        
            segment = transcriber.find_text_segment(
                transcript=transcript,
                start_text=start_text,
                end_text=end_text,
                similarity_threshold=similarity_threshold
            )
            if not segment:
                logger.warning("No matching segment found")
                return

            start_time, end_time, text, similarity = segment
            duration = end_time - start_time
            logger.info("Found matching segment:")
            logger.info(f"Start text: \"{start_text}\"")
            logger.info(f"Start time: {format_time(start_time)}")
            logger.info(f"End text: \"{end_text}\"")
            logger.info(f"End time: {format_time(end_time)}")
            logger.info(f"Full text: {text}")
            logger.info(f"Duration: {int(duration)}s")
            logger.info(f"URL: https://youtube.com/watch?v={video_id}&t={int(start_time)}s")
            occurrences = [(start_time, end_time, text, similarity)]
            clip_duration = duration

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
                        logger.warning("Invalid input provided")
            else:
                choice = input("\nGenerate clip? (Y/n): ").strip().lower()
                if choice in ['y', 'yes', '']:
                    start_time, end_time, text, _ = occurrences[0]
            # ::::::::::::::::::::::::::::::
            # start_time, end_time, text, _ = occurrences[0]
            # choice = 'y'
            if choice != 'n':
                logger.info("Preparing clip generation")
                segment_words = []
                clip_end_ms = (start_time + clip_duration) * 1000
                clip_start_ms = start_time * 1000
                
                for word in transcript.words:
                    if clip_start_ms <= word.start <= clip_end_ms:
                        segment_words.append({
                            'text': word.text,
                            'start': word.start,
                            'end': min(word.end, clip_end_ms)
                        })
                
                logger.debug(f"Processing {len(segment_words)} words for the clip")
                if (text):

                    clip_path = YouTubeHandler.extract_clip(
                        url=url,
                        start_time=start_time,
                        duration=clip_duration,
                        words=segment_words,
                        window_size=window_size
                    )
                    logger.info(f"Clip saved to: {clip_path}")

        # Cleanup
        if cleanup:
            try:
                os.remove(audio_path)
                logger.debug("Cleaned up temporary audio file")
            except:
                pass

    except Exception as e:
        logger.error(f"Process failed: {str(e)}")
        logger.debug(traceback.format_exc())
        sys.exit(1)

def main():
    args = parse_arguments()
    try:
        logger.info("Starting transcript processing")
        if args.srt:
            process_video(
                url=args.url,
                srt_file=args.srt,
                clip_duration=args.clip_duration if args.clip_duration > 0 else None,
                cleanup=not args.no_cleanup,
                window_size=args.words
            )
        elif args.phrase:
            process_video(
                url=args.url,
                search_phrase=args.phrase,
                similarity_threshold=args.threshold,
                clip_duration=args.clip_duration if args.clip_duration > 0 else None,
                cleanup=not args.no_cleanup,
                window_size=args.words
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
                clip_duration=None, # args.clip_duration if args.clip_duration > 0 else None,
                cleanup=not args.no_cleanup,
                window_size=args.words
            )
            
    except KeyboardInterrupt:
        logger.warning("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Critical error: {str(e)}")
        logger.debug(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()


