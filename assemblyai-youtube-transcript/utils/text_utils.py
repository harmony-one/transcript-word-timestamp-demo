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
