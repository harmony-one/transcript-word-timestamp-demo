# YouTube Transcript Search Tool
Search for specific phrases in YouTube video transcripts.

## Installation

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

## Usage

```bash
python transcript.py <youtube_url> "<search_phrase>" [--show-text]
```

### Parameters

- `youtube_url`: URL of the YouTube video
- `search_phrase`: Text to search for in the transcript
- `--show-text`: (Optional) Display the transcript text containing the found phrase

### Example

```bash
python transcript.py "https://www.youtube.com/watch?v=hX4KgFNuwZ8" "number one monetization" --show-text
```