import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    ASSEMBLYAI_AUTH_KEY = os.environ.get('ASSEMBLYAI_AUTH_KEY')
    DEFAULT_OUTPUT_DIR = "clips"
    DEFAULT_TEMP_DIR = "temp"
    DEFAULT_SIMILARITY_THRESHOLD = 80
    DEFAULT_CLIP_DURATION = 30
    DEFAULT_SUBTITLE_MODE = "word"

config = Config()
