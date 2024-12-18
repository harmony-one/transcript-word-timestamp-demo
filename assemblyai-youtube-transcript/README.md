# YouTube Transcript Search and Clip Extraction Tool
A Python tool that combines AssemblyAI transcription with semantic search to find and extract specific moments from YouTube videos.

## Prerequisites
- Python 3.10 or higher
- AssemblyAI API key (set in .env file)
- FFmpeg (required for audio/video processing)

## Installation

### 1. Install FFmpeg

#### macOS
Using Homebrew (recommended):
```bash
brew install ffmpeg
```

For other methods visit [FFmpeg website](https://ffmpeg.org/download.html)

### 2. Verify FFmpeg Installation
```bash
ffmpeg -version
```

### 3. Install Python Dependencies

Using pip:
```bash
pip install -r requirements.txt
```

Using pipenv:
```bash
pip install pipenv
pipenv install
pipenv shell
```

## Configuration
Create a `.env` file with your AssemblyAI API key:
```
ASSEMBLYAI_AUTH_KEY=your-api-key-here
```

## Usage

### Basic Command
```bash
python transcript.py <youtube_url> (-p PHRASE | -t TEXT | -s SRT_FILE) [options]
```

### Parameters
| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| youtube_url | Full URL of the YouTube video | Yes | - |
| -p, --phrase | Short phrase to search for (max 5 words) | No* | - |
| -t, --text | Full text to search for (split into segments) | No* | - |
| -s, --srt | Path to SRT file for subtitle timestamps | No* | - |
| --threshold | Minimum similarity threshold (0-100) | No | 80 |
| --clip-duration | Duration of extracted clips in seconds (0 to disable) | No | 30 |
| --no-cleanup | Keep temporary files after processing | No | False |
| -w, --words | Words per subtitle frame (window size) | No | 1 |
| -f, --font-size | Font size for the subtitle text | No | 72 |

\* One of --phrase, --text, or --srt must be specified, but they are mutually exclusive

### Examples

Search for a specific phrase:
```bash
python transcript.py "https://youtube.com/watch?v=example" -p "interesting phrase" --clip-duration 30
```

Search for a longer text segment:
```bash
python transcript.py "https://youtube.com/watch?v=example" -t "this is a longer text that will be split into start and end segments" --threshold 90
```

Search with five-word subtitle window:
```bash
python transcript.py "https://youtube.com/watch?v=example" -p "interesting phrase" --clip-duration 30 --words 5
```

Use a predefined SRT file:
```bash
python transcript.py "https://youtube.com/watch?v=example" -s subtitles.srt --words 5
```

Customize subtitle font size:
```bash
python transcript.py "https://youtube.com/watch?v=example" -p "interesting phrase" --font-size 48
```

## Output
The tool will:
1. Download and transcribe the video audio (or use provided SRT file)
2. Search for matches using fuzzy string matching (when using -p or -t)
3. Display matches with:
   - Timestamp
   - Match score (for phrase/text search)
   - Matched text
   - Direct YouTube URL with timestamp
4. Create video clips with word-by-word subtitles

## Notes
- Search phrases are limited to 5 words for optimal matching
- Long text inputs are automatically split into start and end segments
- Temporary files are automatically cleaned up unless --no-cleanup is specified
- When using an SRT file (-s), phrase searching is disabled and the timestamps from the file are used directly
