from typing import List, Tuple, Optional
from rapidfuzz import fuzz
import assemblyai as aai
from .base import BaseSearcher

class FuzzySearcher(BaseSearcher):
    """Implementation of fuzzy text searching using rapidfuzz."""
    
    def compare_phrases(self, phrase1: str, phrase2: str) -> Tuple[float, float, float]:
        """Compare two phrases using different fuzzy matching strategies."""
        return (
            fuzz.ratio(phrase1.lower(), phrase2.lower()),
            fuzz.partial_ratio(phrase1.lower(), phrase2.lower()),
            fuzz.token_sort_ratio(phrase1.lower(), phrase2.lower())
        )

    def find_phrase_occurrences(self,
                              transcript: aai.Transcript,
                              search_phrase: str,
                              similarity_threshold: float = 80) -> List[Tuple[float, float, str, float]]:
        """Find phrases in the transcript using fuzzy matching."""
        occurrences = []
        search_phrase = search_phrase.lower()
        search_words = search_phrase.split()
        search_word_count = len(search_words)
        
        words = transcript.words
        
        for i in range(len(words) - search_word_count + 1):
            sequence_words = words[i:i + search_word_count]
            sequence_text = ' '.join(word.text for word in sequence_words)
            
            ratio, partial_ratio, token_ratio = self.compare_phrases(
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
        
        # Sort and filter occurrences
        occurrences.sort(key=lambda x: (-x[3]))
        return self._filter_overlapping_occurrences(occurrences)

    def find_text_segment(self,
                         transcript: aai.Transcript,
                         start_text: str,
                         end_text: str,
                         similarity_threshold: float = 80) -> Optional[Tuple[float, float, str, float]]:
        """Find a segment between two pieces of text in the transcript."""
        # Find occurrences of start and end text
        start_occurrences = self.find_phrase_occurrences(
            transcript, start_text, similarity_threshold)
        end_occurrences = self.find_phrase_occurrences(
            transcript, end_text, similarity_threshold)
        
        if not start_occurrences or not end_occurrences:
            return None
        
        return self._get_best_segment(transcript, start_occurrences, end_occurrences)

    def _filter_overlapping_occurrences(self, 
                                      occurrences: List[Tuple[float, float, str, float]]
                                      ) -> List[Tuple[float, float, str, float]]:
        """Filter out overlapping occurrences, keeping the ones with higher scores."""
        filtered_occurrences = []
        for occ in occurrences:
            similar_exists = any(
                abs(existing[0] - occ[0]) < 0.5 and
                existing[3] >= occ[3]
                for existing in filtered_occurrences
            )
            if not similar_exists:
                filtered_occurrences.append(occ)
        return filtered_occurrences

    def _get_best_segment(self,
                         transcript: aai.Transcript,
                         start_occurrences: List[Tuple[float, float, str, float]],
                         end_occurrences: List[Tuple[float, float, str, float]]
                         ) -> Optional[Tuple[float, float, str, float]]:
        """Get the best matching segment from start and end occurrences."""
        for start_occ in start_occurrences:
            start_time = start_occ[0]
            for end_occ in end_occurrences:
                end_time = end_occ[1]
                
                if end_time > start_time:
                    segment_words = []
                    for word in transcript.words:
                        if start_time * 1000 <= word.start <= end_time * 1000:
                            segment_words.append(word.text)

                    full_text = ' '.join(segment_words)
                    average_score = (start_occ[3] + end_occ[3]) / 2
                    
                    return (start_time, end_time, full_text, average_score)
        
        return None