import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.conf import settings
from quizzly_app.models import Quiz, Question


@pytest.fixture
def api_client():
    """
    DRF APIClient with activated CSRF-Checks, to get browser simulation.
    """
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def create_user(db):

    def _create_user(username="alice", email="alice@example.com", password="examplePasswort1"):
        User = get_user_model()
        user = User.objects.create_user(
            username=username, email=email, password=password)
        return user, password
    return _create_user


@pytest.fixture
def csrf_token(api_client):
    url = "/api/login/"
    api_client.get(url)
    return api_client.cookies.get("csrftoken").value


@pytest.fixture
def login_user(api_client, create_user, csrf_token):
    (user, password) = create_user()
    resp = api_client.post("/api/login/", {'username': user.username,
                           'password': password}, format='json', HTTP_X_CSRFTOKEN=csrf_token,)
    assert resp.status_code == 200, resp.data
    return user, password


@pytest.fixture
def make_quiz(db, create_user):
    def _make_quiz(owner=None, num_questions=3, **kwargs):
        if owner is None:
            owner, _pwd = create_user()
        title = kwargs.get('title', 'Sample Quiz')
        description = kwargs.get('description', 'Sample Description')
        video_url = kwargs.get(
            'video_url', 'https://www.youtube.com/watch?v=h6nIgUDfov0')
        quiz = Quiz.objects.create(
            owner=owner, title=title, description=description, video_url=video_url)
        for i in range(num_questions):
            Question.objects.create(
                quiz=quiz,
                question_title=f"Q{i+1}",
                question_options=['A', 'B', 'c', 'D'],
                answer='A',
            )
        return quiz
    return _make_quiz


@pytest.fixture(autouse=True)
def _forbid_yt_dlp(monkeypatch):
    """
    blocks tests from starting real downloads from yt-dlp.
    if extract_info es executed, the test fails automatically.
    """
    class _DummyYDL:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, *args, **kwargs):
            raise AssertionError(
                "Network/yt-dlp call attempted in tests. Mock 'download_audio_wav' in quizzly_app.api.services!"
            )
    monkeypatch.setattr("yt_dlp.YoutubeDL", _DummyYDL, raising=True)


@pytest.fixture(autouse=True)
def _stub_google_genai(monkeypatch):
    """
    If a test uses google.genai.Client unexpected, the test is stubbed, to ensure no network-calls can be done.
    """
    class _DummyResp:
        text = '{"title": "Stub", "description":"","questions":[]}'

    class _DummyModels:
        def generate_content(self, *a, **k): return _DummyResp()
        def list(self, *a, **k): return []

    class _DummyClient:
        models = _DummyModels()
    monkeypatch.setattr("google.genai.Client",
                        lambda api_key=None: _DummyClient(), raising=False)
