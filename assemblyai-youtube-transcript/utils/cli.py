import argparse
from typing import Optional

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Search YouTube videos for phrases or text segments')
    parser.add_argument('url', help='YouTube video URL')
    
    # Create mutually exclusive group for phrase vs text vs srt
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--phrase', help='Short phrase to search for (max 5 words)')
    group.add_argument('-t', '--text', help='Full text to search for (will be split into segments)')
    group.add_argument('-s', '--srt', help='Path to SRT file for subtitle timestamps')
    
    # Common arguments
    parser.add_argument('--threshold', type=int, default=80,
                        help='Minimum similarity threshold (0-100)')
    parser.add_argument('--clip-duration', type=int, default=30,
                        help='Duration of extracted clips in seconds (0 to disable)')
    parser.add_argument('--no-cleanup', action='store_true',
                        help='Do not delete temporary files')
    parser.add_argument('-w', '--words', type=int, default=1,
                        help='Words per subtitle print')
    parser.add_argument('-f', '--font-size', type=int, default=72,
                        help='Font size for the subtitle')
    
    return parser.parse_args()