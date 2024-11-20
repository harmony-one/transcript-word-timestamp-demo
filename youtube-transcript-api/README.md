# YouTube Transcript Search Tool
A Python tool for semantic search in YouTube video transcripts.

## Features
- Search for specific phrases in YouTube video transcripts
- Semantic matching to find similar phrases regardless of exact wording
- Configurable similarity threshold
- Support for both pip and pipenv workflows

## Installation

### Using pip
```bash
pip install -r requirements.txt
```

### Using pipenv
```bash
pip install pipenv
pipenv install
pipenv shell
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
| search_phrase | Text to search for in the transcript | Yes | - |
| --threshold | Minimum similarity threshold (0-100) | No | 80 |

### Examples

Search for an exact phrase:
```bash
python transcript.py "https://www.youtube.com/watch?v=hX4KgFNuwZ8" "get to 10 million" --threshold 85
```

Search with semantic matching (finds similar meanings):
```bash
python transcript.py "https://www.youtube.com/watch?v=hX4KgFNuwZ8" "get to ten milion" --threshold 85
```

## Requirements
- Python 3.7 or higher
- See `requirements.txt` for package dependencies
