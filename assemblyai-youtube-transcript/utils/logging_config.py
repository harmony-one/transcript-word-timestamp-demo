import logging
import os
from datetime import datetime
import re
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)


class ASCIIFormatter(logging.Formatter):
    """Formatter that strips ANSI escape codes and youtube-dl style brackets"""
    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)
        # Regex patterns
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        self.youtube_dl = re.compile(r'\[(youtube|download|info)\] ')  # CHANGE: Added pattern for youtube-dl
        
    def format(self, record):
        # First format the record
        formatted = super().format(record)
        # Strip ANSI escape codes and youtube-dl brackets
        cleaned = self.ansi_escape.sub('', formatted)
        cleaned = self.youtube_dl.sub('', cleaned)  # CHANGE: Remove youtube-dl brackets
        return cleaned
    
class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""
    
    COLORS = {
        'DEBUG': Fore.BLUE,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT
    }

    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{Style.RESET_ALL}"
            record.msg = f"{self.COLORS[levelname]}{record.msg}{Style.RESET_ALL}"
        return super().format(record)

class YouTubeDLFilter(logging.Filter):
    """Filter to clean up youtube-dl logging output"""
    def filter(self, record):
        # Skip youtube-dl debug messages
        if 'youtube' in record.msg or '[download]' in record.msg or '[info]' in record.msg:
            return False
        return True
    
def setup_logger(name=None):
    """
    Configure and return a logger instance with console and file output
    """
    logger = logging.getLogger(name or __name__)
    
    # Only configure if no handlers exist
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        # Create logs directory if it doesn't exist
        logs_dir = 'logs'
        os.makedirs(logs_dir, exist_ok=True)
        
        # Generate log filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(logs_dir, f'transcript_{timestamp}.log')
        
        # Create formatters
        console_formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        # file_formatter = logging.Formatter(
        #     '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        # )
        file_formatter = ASCIIFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Console handler (with colors)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.DEBUG)  # Console shows INFO and above
        
        # File handler (without colors, but with all debug info)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)  # File gets everything
        
        # Add youtube-dl filter to both handlers
        youtube_dl_filter = YouTubeDLFilter()
        console_handler.addFilter(youtube_dl_filter)
        file_handler.addFilter(youtube_dl_filter)

        # Add both handlers
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        # Prevent propagation to root logger
        logger.propagate = False
        
        # Log the start of a new session
        logger.info(f"Log file created at: {log_file}")
    
    return logger