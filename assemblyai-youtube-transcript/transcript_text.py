import argparse
import sys
from typing import Tuple
from transcript import process_video

def get_segment_texts(full_text: str) -> Tuple[str, str]:
    """Extract start and end segments (5 words each) from text."""
    words = full_text.split()
    
    if len(words) <= 10:
        mid = len(words) // 2
        start_text = ' '.join(words[:min(5, mid)])
        end_text = ' '.join(words[-min(5, len(words)-mid):])
    else:
        start_text = ' '.join(words[:5])
        end_text = ' '.join(words[-5:])
        
    return start_text, end_text

def main():
    parser = argparse.ArgumentParser(
        description='Search YouTube videos for text segments'
    )
    parser.add_argument('url', help='YouTube video URL')
    parser.add_argument('text', help='Full text to search for')
    parser.add_argument('--threshold', type=int, default=80,
                       help='Minimum similarity threshold (0-100)')
    parser.add_argument('--clip-duration', type=int, default=30,
                       help='Duration of extracted clips in seconds (0 to disable)')
    parser.add_argument('--no-cleanup', action='store_true',
                       help='Do not delete temporary files after processing')
    parser.add_argument('--subtitles', choices=['word', 'full', 'none'],
                       default='word',
                       help='Subtitle mode: word-by-word (default), full text, or none')
    
    args = parser.parse_args()
    
    try:
        start_text, end_text = get_segment_texts(args.text)
        print(f"\nSearching with segments:")
        print(f"Start text: '{start_text}'")
        print(f"End text: '{end_text}'")
        
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


