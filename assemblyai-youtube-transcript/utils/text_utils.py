from typing import List, Tuple
from .time_utils import parse_srt_timestamp

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


def parse_srt_file(srt_path: str) -> List[dict]:
    """Parse SRT file and convert to word timestamps format."""
    words = []
    current_index = 0
    
    with open(srt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
            
        # Try to parse index
        try:
            subtitle_index = int(line)
            if i + 2 >= len(lines):
                break
                
            # Parse timestamp line
            timestamp_line = lines[i + 1].strip()
            time_parts = timestamp_line.split(' --> ')
            if len(time_parts) != 2:
                i += 1
                continue
                
            start_time = parse_srt_timestamp(time_parts[0])
            end_time = parse_srt_timestamp(time_parts[1])
            
            # Parse text
            text_line = lines[i + 2].strip()
            
            words.append({
                'text': text_line,
                'start': start_time,
                'end': end_time
            })
            
            i += 3
        except ValueError:
            i += 1
            
    return words

def get_ass_style(font_size: int = 120, margin_v: int = 250) -> str:
    """Returns ASS subtitle configuration with customizable styling."""
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&HFFFFFF&,&H000000&,&H000000&,&H00000000,1,0,0,0,100,100,0,0,1,2,0,2,20,20,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
