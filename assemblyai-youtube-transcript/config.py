import os
from dotenv import load_dotenv

load_dotenv()

class Config(object):
    ASSEMBLYAI_AUTH_KEY = os.environ.get('ASSEMBLYAI_AUTH_KEY')
    # ASSEMBLYAI_TRANSCRIPT_ENPOINT = 'https://api.assemblyai.com/v2/transcript'
    # ASSEMBLYAI_TRANSCRIPT_UPLOAD = 'https://api.assemblyai.com/v2/upload'


config = Config()