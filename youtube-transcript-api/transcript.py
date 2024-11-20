from typing import List, Dict, Tuple
from urllib.parse import parse_qs, urlparse
from rapidfuzz import fuzz, process
import sys
import argparse
from youtube_transcript_api import YouTubeTranscriptApi

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
    def create_word_mapping(transcript: List[Dict]) -> Tuple[List[str], List[Dict]]:
        """
        Create word mapping with both entry timing and calculated word timing.
        """
        words = []
        word_mappings = []
        
        for entry in transcript:
            entry_words = entry['text'].split()
            if not entry_words:
                continue
                
            # Calculate timing for each word in the entry
            entry_duration = entry.get('duration', 0)
            word_duration = entry_duration / len(entry_words)
            entry_start = entry['start']
            for i, word in enumerate(entry_words):
                # Calculate word-specific timing
                word_start = entry_start + (i * word_duration)
                
                # Store both timings
                word_mapping = {
                    'word': word,
                    'entry_start': entry_start,        # Original entry start
                    'word_start': word_start,          # Calculated word start
                    'duration': word_duration,
                    'total_words': len(entry_words),   # Words in this entry
                    'position': i                      # Position in entry
                }
                
                words.append(word)
                word_mappings.append(word_mapping)
        return words, word_mappings

    @staticmethod
    def find_phrase_occurrences(transcript: List[Dict], search_phrase: str, 
                              similarity_threshold: int = 80,
                              duration: int = None) -> List[Tuple[float, str]]:
        """
        Find phrases using averaged timing between entry and word-specific timing.
        """
        occurrences = []
        search_phrase = search_phrase.lower()
        search_words = search_phrase.split()
        search_word_count = len(search_words)
        
        # Create word mapping with both timings
        words, word_mappings = YouTubeTranscriptSearcher.create_word_mapping(transcript)
        
        for i in range(len(words) - search_word_count + 1):
            sequence_words = words[i:i + search_word_count]
            sequence_text = ' '.join(sequence_words)
            
            ratio, partial_ratio, token_ratio = YouTubeTranscriptSearcher.compare_phrases(
                search_phrase, sequence_text
            )
            
            best_score = max(ratio, partial_ratio, token_ratio)
            
            if best_score >= similarity_threshold:
                first_word = word_mappings[i]
                last_word = word_mappings[i + search_word_count - 1]
                
                # Calculate averaged start time
                entry_start = first_word['entry_start']
                word_start = first_word['word_start']
                start_time = (entry_start + word_start) / 2
                
                if duration:
                    end_time = start_time + duration
                else:
                    last_word_end = last_word['word_start'] + last_word['duration']
                    last_entry_end = last_word['entry_start'] + last_word['duration'] * last_word['total_words']
                    end_time = (last_word_end + last_entry_end) / 2
                
                occurrences.append((
                    start_time,
                    end_time,
                    sequence_text,
                    best_score
                ))
        
        # Sort by score (descending) and timestamp (ascending)
        occurrences.sort(key=lambda x: (-x[3], x[0]))
        
        # Filter duplicates and near-duplicates
        filtered_occurrences = []
        for occ in occurrences:
            similar_exists = any(
                abs(existing[0] - occ[0]) < 0.5 and  # Within 0.5 seconds
                existing[3] >= occ[3]  # Better or equal score
                for existing in filtered_occurrences
            )
            if not similar_exists:
                filtered_occurrences.append(occ)
        
        return filtered_occurrences[:1]

    @staticmethod
    def format_time(seconds: float) -> str:
        """Format seconds into HH:MM:SS."""
        # Round to nearest second for display
        seconds = round(seconds)
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def main():
    parser = argparse.ArgumentParser(description='Search YouTube video transcripts for similar phrases')
    parser.add_argument('url', help='YouTube video URL')
    parser.add_argument('phrase', help='Phrase to search for')
    parser.add_argument('--threshold', type=int, default=80,
                       help='Minimum similarity threshold (0-100)')
    parser.add_argument('--duration', type=int,
                       help='Duration in seconds to include from the timestamp')
    args = parser.parse_args()

    try:
        video_id = YouTubeTranscriptSearcher.get_video_id(args.url)
        if not video_id:
            print("Error: Could not extract video ID from URL")
            sys.exit(1)
            
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        occurrences = YouTubeTranscriptSearcher.find_phrase_occurrences(
            transcript, 
            args.phrase,
            similarity_threshold=args.threshold,
            duration=args.duration
        )
        
        if not occurrences:
            print(f"No similar phrases found for '{args.phrase}'")
            return

        print(f"\nFound similar phrases to '{args.phrase}':")
        for timestamp, end_time, text, similarity in occurrences:
            formatted_time = YouTubeTranscriptSearcher.format_time(timestamp)
            
            print(f"\nTime: {formatted_time}")
            print(f"Match score: {similarity}%")
            print(f"Text: \"{text}\"")
            print(f"URL: https://youtube.com/watch?v={video_id}&t={int(timestamp)}s")
                
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()