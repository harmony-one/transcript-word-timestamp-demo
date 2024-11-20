import argparse
from youtube_transcript_api import YouTubeTranscriptApi
import re
from urllib.parse import urlparse, parse_qs
import sys
from typing import List, Dict, Tuple

class YouTubeTranscriptSearcher:
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
    def find_phrase_occurrences(transcript: List[Dict], search_phrase: str, duration: int = None) -> List[Tuple[float, str]]:
      """
      Find all occurrences of a phrase in the transcript using a sliding window of 3 elements.
      Both search phrase and transcript text are cleaned consistently.
      
      Args:
          transcript: Video transcript
          search_phrase: Phrase to search for
          duration: Duration in seconds to include in the URLs (optional)
      """
      occurrences = []
      
      # Helper function to clean text - removes punctuation and converts to lowercase
      def clean_text(text):
          return re.sub(r'[^\w\s]', '', text.lower())
          
      # Clean the search phrase once
      cleaned_search_phrase = clean_text(search_phrase)
      
      for i in range(len(transcript)):
          # Get previous, current, and next elements
          prev_text = transcript[i-1]['text'] if i > 0 else ""
          current_text = transcript[i]['text']
          next_text = transcript[i+1]['text'] if i < len(transcript)-1 else ""
          
          # Create different combinations of text windows
          windows = [
              current_text,  # Single element
              f"{prev_text} {current_text}",  # Previous + current
              f"{current_text} {next_text}",  # Current + next
              f"{prev_text} {current_text} {next_text}"  # All three
          ]
          
          # Search in each window
          for window in windows:
              cleaned_window = clean_text(window)
              
              if cleaned_search_phrase in cleaned_window:
                  timestamp = transcript[i]['start']
                  
                  # Calculate end_time based on which window matched
                  if duration:
                      end_time = timestamp + duration
                  else:
                      # If we matched with next element, include its duration
                      if window == windows[2] or window == windows[3]:
                          next_duration = transcript[i+1].get('duration', 0)
                          end_time = timestamp + transcript[i].get('duration', 0) + next_duration
                      else:
                          end_time = timestamp + transcript[i].get('duration', 0)
                  
                  occurrences.append((timestamp, end_time, window))
                  break  # Found in one of the windows, move to next position
                  
      return occurrences

    @staticmethod
    def format_time(seconds: float) -> str:
        """Format seconds into HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    @staticmethod
    def create_video_urls(video_id: str, start_time: float, end_time: float = None) -> Tuple[str, str]:
        """
        Create both standard timestamp URL and clip URL.
        
        Returns:
            Tuple of (standard_url, clip_url) if duration is provided,
            otherwise (standard_url, None)
        """
        standard_url = f"https://youtube.com/watch?v={video_id}&t={int(start_time)}s"
        
        if end_time:
            # YouTube clip URL format
            clip_url = (f"https://youtube.com/clip/"
                       f"{video_id}?start={int(start_time)}&end={int(end_time)}")
            return standard_url, clip_url
        
        return standard_url, None

def main():
    parser = argparse.ArgumentParser(description='Search YouTube video transcripts for phrases')
    parser.add_argument('url', help='YouTube video URL')
    parser.add_argument('phrase', help='Phrase to search for')
    parser.add_argument('--duration', type=int, help='Duration in seconds to include from the timestamp')
    parser.add_argument('--show-text', action='store_true', help='Show the text where the phrase was found')
    args = parser.parse_args()

    searcher = YouTubeTranscriptSearcher()
    
    video_id = searcher.get_video_id(args.url)
    if not video_id:
        print("Error: Could not extract video ID from URL")
        sys.exit(1)

    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        occurrences = searcher.find_phrase_occurrences(transcript, args.phrase, args.duration)
        
        if not occurrences:
            print(f"Phrase '{args.phrase}' not found in the video transcript.")
            return

        print(f"\nFound '{args.phrase}' at:")
        for timestamp, end_time, text in occurrences:
            formatted_time = searcher.format_time(timestamp)
            standard_url, clip_url = searcher.create_video_urls(video_id, timestamp, end_time)
            
            print(f"\nTime: {formatted_time}")
            print(f"URL (timestamp): {standard_url}")
            if clip_url:
                print(f"URL (clip): {clip_url}")
            
            if args.show_text:
                print(f"Text: \"{text}\"")
                
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()