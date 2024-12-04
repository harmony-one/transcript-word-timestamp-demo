def format_time(seconds: float) -> str:
    """Format seconds into HH:MM:SS for display purposes."""
    seconds = round(seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def millisec_to_srt_time(ms: float) -> str:
    """Convert milliseconds to SRT timestamp format (HH:MM:SS,mmm)."""
    seconds = ms / 1000
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"

def parse_srt_timestamp(timestamp: str) -> int:
    """Convert SRT timestamp to milliseconds."""
    # Format: 00:00:00,000
    time_parts = timestamp.replace(',', ':').split(':')
    hours = int(time_parts[0])
    minutes = int(time_parts[1])
    seconds = int(time_parts[2])
    milliseconds = int(time_parts[3])
    
    total_ms = (hours * 3600000 + 
                minutes * 60000 + 
                seconds * 1000 + 
                milliseconds)
    return total_ms