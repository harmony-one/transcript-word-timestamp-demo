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
    def estimate_word_duration(word: str) -> float:
        """
        Estimate relative duration of a word based on its characteristics.
        Returns a weight factor where 1.0 is the baseline.
        """
        # Count consonants (rough proxy for complexity)
        consonants = sum(1 for c in word.lower() if c not in 'aeiou ')
        
        # Count total characters
        char_count = len(word)
        
        # Words shorter than 3 chars are likely to be spoken quickly
        if char_count <= 2:
            base_weight = 0.7
        else:
            # Longer words get progressively more weight
            base_weight = 1.0 + (char_count - 3) * 0.1
        
        # Add weight for consonant clusters which typically slow speech
        consonant_weight = 1.0 + (consonants / char_count - 0.5) * 0.2
        
        return base_weight * consonant_weight

    @staticmethod
    def create_word_mapping(transcript: List[Dict]) -> Tuple[List[str], List[Dict]]:
        """
        Create word mapping with timing based on word characteristics.
        """
        words = []
        word_mappings = []
        
        for entry in transcript:
            entry_words = entry['text'].split()
            if not entry_words:
                continue
                
            # Calculate weights for each word
            word_weights = [YouTubeTranscriptSearcher.estimate_word_duration(word) 
                          for word in entry_words]
            total_weight = sum(word_weights)
            
            # Calculate timing for each word in the entry
            entry_duration = entry.get('duration', 0)
            entry_start = entry['start']
            current_time = entry_start
            
            for i, (word, weight) in enumerate(zip(entry_words, word_weights)):
                # Calculate word duration based on its weight relative to total
                word_duration = (weight / total_weight) * entry_duration
                
                word_mapping = {
                    'word': word,
                    'entry_start': entry_start,
                    'word_start': current_time,
                    'duration': word_duration,
                    'total_words': len(entry_words),
                    'position': i,
                    'weight': weight  # Store weight for debugging/tuning
                }
                
                words.append(word)
                word_mappings.append(word_mapping)
                
                # Update time for next word
                current_time += word_duration
        
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

def setup_parser() -> argparse.ArgumentParser:
    """Set up and return the argument parser."""
    parser = argparse.ArgumentParser(
        description='Search YouTube video transcripts for similar phrases',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('url', help='YouTube video URL')
    parser.add_argument('phrase', help='Phrase to search for')
    parser.add_argument(
        '--threshold', 
        type=int, 
        default=80,
        help='Minimum similarity threshold (0-100)'
    )
    parser.add_argument(
        '--duration', 
        type=int,
        help='Duration in seconds to include from the timestamp'
    )
    return parser

def format_search_results(video_id: str, phrase: str, occurrences: List[Tuple]) -> None:
    """Format and print search results."""
    if not occurrences:
        print(f"\nNo similar phrases found for '{phrase}'")
        return

    print(f"\nFound similar phrases to '{phrase}':")
    
    for timestamp, end_time, text, similarity in occurrences:
        formatted_time = YouTubeTranscriptSearcher.format_time(timestamp)
        base_timestamp = int(timestamp)
        
        # Print match details
        print(f"\nTime: {formatted_time}")
        print(f"Match score: {similarity:.1f}%")
        print(f"Text: \"{text}\"")
        
        # Print timestamped URLs
        print("\nPrimary URL:")
        print(f"https://youtube.com/watch?v={video_id}&t={base_timestamp}s")
        
        print("\nAlternative timestamps (if the exact moment is slightly off):")
        print(f"Earlier: https://youtube.com/watch?v={video_id}&t={base_timestamp - 1}s")
        print(f"Later:   https://youtube.com/watch?v={video_id}&t={base_timestamp + 1}s")

def process_video(url: str, phrase: str, threshold: int, duration: int) -> None:
    """Process video transcript and search for phrases."""
    try:
        # Extract video ID
        video_id = YouTubeTranscriptSearcher.get_video_id(url)
        if not video_id:
            raise ValueError("Could not extract video ID from URL")
        
        # Get transcript and search for phrases
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
        except Exception as e:
            raise ValueError(f"Could not fetch transcript: {str(e)}")
            
        occurrences = YouTubeTranscriptSearcher.find_phrase_occurrences(
            transcript=transcript,
            search_phrase=phrase,
            similarity_threshold=threshold,
            duration=duration
        )
        
        # Format and display results
        format_search_results(video_id, phrase, occurrences)
        
    except ValueError as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)

def main():
    """Main entry point for the script."""
    try:
        # Set up and parse arguments
        parser = setup_parser()
        args = parser.parse_args()
        
        # Process video and display results
        process_video(
            url=args.url,
            phrase=args.phrase,
            threshold=args.threshold,
            duration=args.duration
        )
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Critical error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()