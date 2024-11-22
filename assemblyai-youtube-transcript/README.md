# YouTube Transcript Search and Clip Extraction Tool
A Python tool that combines AssemblyAI transcription with semantic search to find and extract specific moments from YouTube videos.

## Prerequisites
- Python 3.7 or higher
- AssemblyAI API key (set in config.py)
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
python transcript.py <youtube_url> "<search_phrase>" [options]
```

### Parameters
| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| youtube_url | Full URL of the YouTube video | Yes | - |
| search_phrase | Text to search for (max 5 words) | Yes | - |
| --threshold | Minimum similarity threshold (0-100) | No | 80 |
| --clip-duration | Duration of extracted clips in seconds (0 to disable) | No | 30 |
| --no-cleanup | Keep temporary files after processing | No | False |

### Examples

Search for a phrase and create a 30-second clip:
```bash
python transcript.py "https://www.youtube.com/watch?v=example" "interesting phrase" --clip-duration 30
```

Search with higher similarity threshold:
```bash
python transcript.py "https://www.youtube.com/watch?v=example" "exact phrase" --threshold 90
```

Keep temporary files:
```bash
python transcript.py "https://www.youtube.com/watch?v=example" "test phrase" --no-cleanup
```

## Output
The tool will:
1. Download and transcribe the video audio
2. Search for matches using fuzzy string matching
3. Display matches with:
   - Timestamp
   - Match score
   - Matched text
   - Direct YouTube URL with timestamp
4. Optionally create video clips of matches

## Notes
- Search phrases are limited to 5 words for optimal matching
- Clips are extracted in MP4 format
- The tool uses fuzzy matching to find similar phrases, not just exact matches
- Temporary files are automatically cleaned up unless --no-cleanup is specified