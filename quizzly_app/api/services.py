import os
import tempfile
import yt_dlp
import re
import shutil
import whisper
import json
from typing import Any, Dict, List, Tuple
from google import genai
from google.genai.errors import ClientError


YOUTUBE_REGEX = re.compile(
    r"^https:\/\/www\.youtube\.com\/watch\?v=([A-Za-z0-9_-]{11})$")

_model = None
_PROMPT = """Based on the following transcript, generate a quiz in valid JSON format.

The quiz must follow this exact structure:

{{

  "title": "Create a concise quiz title based on the topic of the transcript.",

  "description": "Summarize the transcript in no more than 150 characters. Do not include any quiz questions or answers.",

  "questions": [

    {{

      "question_title": "The question goes here.",

      "question_options": ["Option A", "Option B", "Option C", "Option D"],

      "answer": "The correct answer from the above options"

    }},

    ...

    (exactly 10 questions)

  ]

}}

Requirements:

- Each question must have exactly 4 distinct answer options.

- Only one correct answer is allowed per question, and it must be present in 'question_options'.

- The output must be valid JSON and parsable as-is (e.g., using Python's json.loads).

- Do not include explanations, comments, or any text outside the JSON."""


class AudioDownloadError(Exception):
    pass


class TranscriptionError(Exception):
    pass


class QuizGenerationOverloaded(Exception):
    pass


class QuizGenerationError(Exception):
    pass


def create_quiz_payload(url: str) -> dict:
    """
    Given a YouTube URL, downloads the audio, transcribes it using Whisper,
    and generates a quiz using Gemini API.
    Returns the quiz as a dictionary.
    """
    validate_youtube_url(url)
    tmpdir = None
    wav_path, ctx = download_audio_wav(url)
    try:
        transcript = whisper_transcribe(wav_path)
    finally:
        tmpdir = (ctx or {}).get("tmpdir")
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
    quiz_json = generate_quiz_from_transcript(transcript)
    return quiz_json


def rename_quiz_instance(quiz, new_title: str):
    """
    Renames the given quiz instance and updates question titles accordingly.
    """
    quiz.title = new_title
    quiz.save(update_fields=['title'])
    return quiz


def delete_quiz_instance(quiz) -> None:
    """
    Deletes the given quiz instance and all its related questions.
    """
    quiz.delete()


def _pick_flash_model(client: genai.Client) -> str:
    """
    Chooses an available *Flah*-model (preferably 2.x).
    Prefers in this order:

      - models/gemini-2.5-flash
      - models/gemini-2.5-flash-preview-*
      - models/gemini-2.5-flash-lite-*
      - models/gemini-2.0-flash*
    returns the complete model name.
    """
    all_models: List[str] = [m.name for m in client.models.list()]

    def first_present(candidates: List[str]) -> str | None:
        for c in candidates:
            if c in all_models:
                return c
            for m in all_models:
                if c.endswith("*") and m.startswith(c[:-1]):
                    return m
        return None

    preferred_order = [
        "models/gemini-2.5-flash",
        "models/gemini-2.5-flash-preview-*",
        "models/gemini-2.5-flash-lite-*",
        "models/gemini-2.0-flash*",
    ]
    pick = first_present(preferred_order)
    if pick:
        return pick
    any_flash = [m for m in all_models if "gemini-2." in m and "-flash" in m]
    if any_flash:
        return any_flash[0]
    raise RuntimeError(
        "Kein Gemini *Flash*-Modell verfügbar. Gefundene Modelle: "
        + ", ".join(all_models[:10])
    )


def generate_quiz_from_transcript(transcript: str) -> Dict[str, Any]:
    """
    Generates a quiz from the given transcript using Gemini API.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY ist nicht gesetzt")

    client = genai.Client(api_key=api_key)
    model_name = _pick_flash_model(client)
    contents = _PROMPT + "\n\nTRANSKRIPT:\n" + transcript[:10000]

    try:
        resp = client.models.generate_content(
            model=model_name, contents=contents)
    except ClientError as ce:
        raise RuntimeError(
            f"Gemini-Call failed ({model_name}): {ce}") from ce

    text = (resp.text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    data = json.loads(text)
    if "title" not in data or "questions" not in data:
        raise ValueError("invalid quiz-structure from gemini.")
    return data


def whisper_transcribe(audio_path: str) -> str:
    """
    Transcribes the given audio file using the Whisper model.
    """
    global _model
    if _model is None:
        _model = whisper.load_model('base')
    result = _model.transcribe(audio_path, fp16=False)
    return (result.get('text') or "").strip()


def validate_youtube_url(url: str) -> str:
    """
    Validates and extracts the video ID from a YouTube URL.
    """
    if not isinstance(url, str):
        raise ValueError('URL must be a string.')
    url = url.strip()
    match = YOUTUBE_REGEX.match(url)
    if not match:
        raise ValueError(
            'Invalid YouTube URL format. Expected format: https://www.youtube.com/watch?v=VIDEO_ID')
    return match.group(1)


def download_audio_wav(url: str) -> tuple[str, dict]:
    """
    Gets Audio as WAV (16 kHz) from a YouTube URL using yt-dlp.
    """
    tmpdir = tempfile.mkdtemp(prefix='quizzly_')
    tmp_filename = os.path.join(tmpdir, '%(id)s')
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': tmp_filename,
        'paths': {'home': tmpdir},
        'quiet': True,
        'noplaylist': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '0',
        }],
        'postprocessor_args': ['-ar', '16000'],
        'extractor_args': {'youtube': {'player_client': ['android']}},
        'http_headers': {
            'User-Agent': (
                'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36'
            )
        },
        'socket_timeout': 30,
        'retries': 3,
        'geo_bypass': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    wav_path = None
    for f in os.listdir(tmpdir):
        if f.endswith('.wav'):
            wav_path = os.path.join(tmpdir, f)
            break

    if not wav_path or not os.path.exists(wav_path):
        raise FileNotFoundError(
            'WAV file cannot be created from the provided URL (SABR/nsig).')

    return wav_path, {'tmpdir': tmpdir, 'info': info}
