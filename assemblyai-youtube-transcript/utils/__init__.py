from typing import Tuple
from .cli import parse_arguments

def format_time(seconds: float) -> str:
      """Format seconds into HH:MM:SS."""
      seconds = round(seconds)
      hours = int(seconds // 3600)
      minutes = int((seconds % 3600) // 60)
      secs = int(seconds % 60)
      return f"{hours:02d}:{minutes:02d}:{secs:02d}"

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