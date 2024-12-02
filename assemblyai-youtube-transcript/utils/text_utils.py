from typing import Tuple


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