import os
import tempfile
import shutil
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_list_quizzes_requires_auth_401(api_client):
    resp = api_client.get('/api/quizzes/')
    assert resp.status_code in (401, 403)


def test_list_quizzes_only_own_and_shape(api_client, login_user, create_user, make_quiz):
    me, _ = login_user
    other, _pwd = create_user(username='x', email='x@example.com')

    q1 = make_quiz(owner=me, num_questions=2, title="Testen1")
    q2 = make_quiz(owner=me, num_questions=1, title='Testen2')
    make_quiz(owner=other, num_questions=3, title='TestenFremd')

    resp = api_client.get('/api/quizzes/')
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    titles = {q['title'] for q in data}
    assert titles == {'Testen1', 'Testen2'}

    item = data[0]
    assert 'created_at' in item and 'updated_at' in item
    assert 'questions' in item and isinstance(item['questions'], list)
    if item['questions']:
        q = item['questions'][0]
        assert 'question_title' in q and 'question_options' in q and 'answer' in q
        assert 'created_at' not in q and 'updated_at' not in q


def test_quiz_detail_200_own(api_client, login_user, make_quiz):
    me, _ = login_user
    quiz = make_quiz(owner=me, num_questions=2, title='Detail OK')
    resp = api_client.get(f'/api/quizzes/{quiz.id}/')
    assert resp.status_code == 200
    obj = resp.json()
    assert obj['id'] == quiz.id
    assert 'created_at' in obj and 'updated_at' in obj
    assert obj['questions']
    assert 'created_at' not in obj['questions'][0]


def test_quiz_detail_403_other_user(api_client, create_user, login_user, make_quiz):
    me, _ = login_user
    other, _ = create_user(username='patrick', email='patrick@star.com')
    quiz = make_quiz(owner=other, num_questions=1)
    resp = api_client.get(f'/api/quizzes/{quiz.id}/')
    assert resp.status_code == 403


def test_quiz_detail_404_missing(api_client, login_user):
    login_user
    resp = api_client.get('/api/quizzes/999999/')
    assert resp.status_code == 404


def test_quiz_patch_200_updates_title(api_client, login_user, csrf_token, make_quiz):
    me, _ = login_user
    quiz = make_quiz(owner=me, num_questions=1, title='BikiniBottom')
    resp = api_client.patch(
        f'/api/quizzes/{quiz.id}/',
        {'title': "KrosseKrabbe"},
        format='json',
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert resp.status_code == 200
    obj = resp.json()
    assert obj['title'] == 'KrosseKrabbe'
    if obj['questions']:
        assert 'created_at' not in obj['questions'][0]


def test_quiz_patch_400_invalid_title(api_client, login_user, csrf_token, make_quiz):
    me, _ = login_user
    quiz = make_quiz(owner=me, num_questions=1)
    resp = api_client.patch(
        f'/api/quizzes/{quiz.id}/',
        {'title': ""},
        format='json',
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert resp.status_code == 400


def test_quiz_patch_403_other_user(api_client, create_user, login_user, csrf_token, make_quiz):
    me, _ = login_user
    other, _ = create_user(username='plankton',
                           email='plankton@abfalleimer.de')
    quiz = make_quiz(owner=other)
    resp = api_client.patch(
        f'/api/quizzes/{quiz.id}/',
        {'title': "Krabbenburger"},
        format='json',
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert resp.status_code == 403


def test_quiz_delete_204(api_client, login_user, csrf_token, make_quiz):
    me, _ = login_user
    quiz = make_quiz(owner=me)
    resp = api_client.delete(
        f'/api/quizzes/{quiz.id}/', HTTP_X_CSRFTOKEN=csrf_token)
    assert resp.status_code == 204

    resp2 = api_client.get(f'/api/quizzes/{quiz.id}/')
    assert resp2.status_code == 404


def test_quiz_delete_403_other_user(api_client, login_user, create_user, csrf_token, make_quiz):
    me, _ = login_user
    other, _ = create_user(username='mrKrabs', email='moneymaker@example.com')
    quiz = make_quiz(owner=other)
    resp = api_client.delete(
        f'/api/quizzes/{quiz.id}/', HTTP_X_CSRFTOKEN=csrf_token)
    assert resp.status_code == 403


def _mk_tmp_wav():
    tmpdir = tempfile.mkdtemp(prefix="test_quizzly_err_")
    wav_path = os.path.join(tmpdir, "dummy.wav")
    with open(wav_path, "wb") as f:
        f.write(b"\x00")
    return tmpdir, wav_path


def test_create_quiz_400_invalid_url(api_client, login_user, csrf_token, monkeypatch, settings):
    settings.DEBUG = True
    login_user
    from quizzly_app.api import views as v
    monkeypatch.setattr(v, 'validate_youtube_url', lambda url: (
        _ for _ in ()).throw(ValueError("bad url")))

    resp = api_client.post(
        '/api/createQuiz/',
        {'url': 'IncorrectURl'},
        format='json',
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert resp.status_code == 400
    assert 'Ungültige URL' in resp.json()[
        'detail']


def test_create_quiz_500_download_fail(api_client, login_user, csrf_token, monkeypatch, settings):
    settings.DEBUG = True
    login_user
    from quizzly_app.api import views as v
    monkeypatch.setattr(v, 'validate_youtube_url', lambda url: "OK")
    monkeypatch.setattr(v, 'download_audio_wav', lambda url: (
        _ for _ in ()).throw(RuntimeError("dl fail")))
    resp = api_client.post(
        '/api/createQuiz/',
        {'url': 'https://www.youtube.com/watch?v=h6nIgUDfov0'},
        format='json',
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert resp.status_code == 500
    assert resp.json()['detail'].startswith("Audio-Download fehlgeschlagen")


def test_create_quiz_500_transcribe_fail_and_tmp_cleanup(api_client, login_user, csrf_token, monkeypatch, settings):
    settings.DEBUG = True
    login_user
    from quizzly_app.api import views as v

    tmpdir, wav_path = _mk_tmp_wav()
    monkeypatch.setattr(v, "validate_youtube_url", lambda url: "OK")
    monkeypatch.setattr(v, "download_audio_wav", lambda url: (
        wav_path, {"tmpdir": tmpdir, "info": {}}))
    monkeypatch.setattr(v, "whisper_transcribe", lambda path: (
        _ for _ in ()).throw(RuntimeError("whisper oops")))

    resp = api_client.post(
        '/api/createQuiz/',
        {'url': 'https://www.youtube.com/watch?v=h6nIgUDfov0'},
        format='json',
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert resp.status_code == 500
    assert 'Transkription fehlgeschlagen' in resp.json()['detail']
    assert not os.path.isdir(tmpdir)


def test_create_quiz_500_quizgen_fail(api_client, login_user, csrf_token, monkeypatch, settings):
    settings.DEBUG = True
    login_user
    from quizzly_app.api import views as v

    tmpdir, wav_path = _mk_tmp_wav()
    monkeypatch.setattr(v, "validate_youtube_url", lambda url: "OK")
    monkeypatch.setattr(v, "download_audio_wav", lambda url: (
        wav_path, {"tmpdir": tmpdir, "info": {}}))
    monkeypatch.setattr(v, "whisper_transcribe",
                        lambda path: "transcript")
    monkeypatch.setattr(v, "generate_quiz_from_transcript", lambda t: (
        _ for _ in ()).throw(RuntimeError("gemini!")))

    resp = api_client.post(
        "/api/createQuiz/",
        {"url": "https://www.youtube.com/watch?v=h6nIgUDfov0"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert resp.status_code == 500
    assert "Quiz-Generierung fehlgeschlagen" in resp.json()["detail"]
    assert not os.path.isdir(tmpdir)


def test_create_quiz_500_no_valid_questions(api_client, login_user, csrf_token, monkeypatch, settings, django_assert_num_queries):
    settings.DEBUG = True
    user, _ = login_user

    from quizzly_app.api import views as v

    from quizzly_app.models import Quiz

    tmpdir, wav_path = _mk_tmp_wav()
    monkeypatch.setattr(v, "validate_youtube_url", lambda url: "OK")
    monkeypatch.setattr(v, "download_audio_wav", lambda url: (
        wav_path, {"tmpdir": tmpdir, "info": {}}))
    monkeypatch.setattr(v, "whisper_transcribe",
                        lambda path: "transcript")
    monkeypatch.setattr(v, "generate_quiz_from_transcript", lambda t: {
        "title": "Bad Quiz",
        "description": "opts wrong",
        "questions": [
            {"question_title": "Q1", "question_options": [
                "A", "B", "C"], "answer": "A"},
        ],
    })
    assert Quiz.objects.filter(owner=user).count() == 0

    resp = api_client.post(
        "/api/createQuiz/",
        {"url": "https://www.youtube.com/watch?v=h6nIgUDfov0"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert resp.status_code == 500
    assert "keine gültigen fragen" in resp.json()["detail"].lower()
    assert not os.path.isdir(tmpdir)
