from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
import assemblyai as aai

class BaseSearcher(ABC):
    """Base class for implementing different search strategies."""
    
    @abstractmethod
    def find_phrase_occurrences(self, 
                              transcript: aai.Transcript,
                              search_phrase: str,
                              similarity_threshold: float) -> List[Tuple[float, float, str, float]]:
        """
        Find occurrences of a phrase in the transcript.
        
        Args:
            transcript: The transcript to search in
            search_phrase: The phrase to search for
            similarity_threshold: Minimum similarity score (0-100)
            
        Returns:
            List of tuples (start_time, end_time, text, score)
        """
        pass
    
    @abstractmethod
    def find_text_segment(self,
                         transcript: aai.Transcript,
                         start_text: str,
                         end_text: str,
                         similarity_threshold: float) -> Optional[Tuple[float, float, str, float]]:
        """
        Find a segment between two pieces of text.
        
        Args:
            transcript: The transcript to search in
            start_text: Text to find the beginning of segment
            end_text: Text to find the end of segment
            similarity_threshold: Minimum similarity score (0-100)
            
        Returns:
            Tuple of (start_time, end_time, text, score) or None if not found
        """
        pass