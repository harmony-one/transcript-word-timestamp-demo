import assemblyai as aai
from typing import Optional, Tuple
from searchers import FuzzySearcher, BaseSearcher
import config as app_config

class TranscriptionHandler:
    def __init__(self, searcher: Optional[BaseSearcher] = None):
        """
        Initialize transcription handler.
        
        Args:
            api_key: AssemblyAI API key
            searcher: Optional custom searcher implementation
        """
        aai.settings.api_key = app_config.config.ASSEMBLYAI_AUTH_KEY
        self.transcriber = aai.Transcriber()
        self.searcher = searcher or FuzzySearcher()  # Use FuzzySearcher as default

    def transcribe(self, audio_path: str) -> aai.Transcript:
        """Transcribe audio file using AssemblyAI."""
        return self.transcriber.transcribe(audio_path) # aai.Transcript.get_by_id('b329f1b0-5188-4033-b827-6b0b0cc23152')

    def find_text_segment(self,
                         transcript: aai.Transcript,
                         start_text: str,
                         end_text: str,
                         similarity_threshold: int = 80) -> Optional[Tuple[float, float, str, float]]:
        """Find a segment between two pieces of text in the transcript."""
        return self.searcher.find_text_segment(
            transcript, start_text, end_text, similarity_threshold)

    def find_phrase_occurrences(self,
                              transcript: aai.Transcript,
                              search_phrase: str,
                              similarity_threshold: int = 80) -> Optional[Tuple[float, float, str, float]]:
        """Find occurrences of a phrase in the transcript."""
        return self.searcher.find_phrase_occurrences(
            transcript, search_phrase, similarity_threshold)