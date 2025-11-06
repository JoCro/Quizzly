import os
import shutil
import logging
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .serializers import QuizSerializer, QuestionSerializer, QuizSlimSerializer, QuizDetailSerializer, QuizListSerializer, QuizUpdateSerializer
from .services import validate_youtube_url, download_audio_wav, whisper_transcribe, generate_quiz_from_transcript
from quizzly_app.models import Quiz, Question

logger = logging.getLogger(__name__)


class CreateQuizView(APIView):
    """
    POST /api/createQuiz/
    Creates a new quiz from a YouTube video URL provided in the request data.
    Expected request data: {"url": "https://www.youtube.com/watch?v=VIDEO_ID"}
    """
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        url = (request.data or {}).get("url", "").strip()
        if not url:
            return Response({"detail": "Ungültige URL oder Anfragedaten."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_youtube_url(url)
        except ValueError:
            return Response({"detail": "Ungültige URL oder Anfragedaten."}, status=status.HTTP_400_BAD_REQUEST)

        tmpdir = None
        try:
            try:
                wav_path, meta = download_audio_wav(url)
                tmpdir = meta.get("tmpdir")
            except Exception as e:
                logger.exception("Download-Fehler")
                msg = f"Audio-Download fehlgeschlagen: {e}" if settings.DEBUG else "Interner Serverfehler."
                return Response({"detail": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            try:
                transcript = whisper_transcribe(wav_path)
                if not transcript:
                    return Response(
                        {"detail": "Transkript konnte nicht erzeugt werden."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
            except Exception as e:
                logger.exception("Whisper-Fehler")
                msg = f"Transkription fehlgeschlagen: {e}" if settings.DEBUG else "Interner Serverfehler."
                return Response({"detail": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            try:
                quiz_data = generate_quiz_from_transcript(transcript)
            except Exception as e:
                logger.exception("Gemini-Fehler")
                msg = f"Quiz-Generierung fehlgeschlagen: {e}" if settings.DEBUG else "Interner Serverfehler."
                return Response({"detail": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            title = (quiz_data.get("title") or "Quiz")[:255]
            description = quiz_data.get("description") or ""
            questions = quiz_data.get("questions") or []

            quiz = Quiz.objects.create(
                owner=request.user,
                title=title,
                description=description,
                video_url=url,
            )

            created_any = False
            for q in questions:
                opts = q.get("question_options") or []
                if not isinstance(opts, list) or len(opts) != 4:
                    continue
                Question.objects.create(
                    quiz=quiz,
                    question_title=(q.get("question_title") or "").strip(),
                    question_options=opts,
                    answer=(q.get("answer") or "").strip(),
                )
                created_any = True

            if not created_any:
                quiz.delete()
                return Response(
                    {"detail": "Quiz konnte nicht erstellt werden (keine gültigen Fragen)."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            data = QuizSerializer(quiz).data
            return Response(data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception("Unerwarteter Fehler in CreateQuizView")
            msg = f"Interner Serverfehler: {e}" if settings.DEBUG else "Interner Serverfehler."
            return Response({"detail": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        finally:
            if tmpdir and os.path.isdir(tmpdir):
                shutil.rmtree(tmpdir, ignore_errors=True)


class UserQuizzesView(APIView):
    """
    GET /api/quizzes/
    permission_classes = isAuthenticated
    Retrieve a list of quizzes owned by the authenticated user.
    """
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        try:
            qs = (
                Quiz.objects
                .filter(owner=request.user)
                .prefetch_related("questions")
                .order_by("-created_at")
            )
            data = QuizListSerializer(qs, many=True).data
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Internal server error: {e}" if settings.DEBUG else "Internal server error."
            return Response({"detail": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class QuizDetailView(APIView):
    """
    GET/api/quizzes/{id}/
    PATCH/api/quizzes/{id}/
    DELETE/api/quizzes/{id}/
    permission_classes = isAuthenticated
    Retrieve detailed information about a specific quiz owned by the authenticated user.
    Update the title and/or description of a specific quiz owned by the authenticated user.
    Delete a specific quiz owned by the authenticated user.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id: int):
        try:
            try:
                quiz = (
                    Quiz.objects.prefetch_related("questions")
                    .get(pk=id)
                )
            except Quiz.DoesNotExist:
                return Response({'detail': 'Quiz could not be found.'}, status=status.HTTP_404_NOT_FOUND)
            if quiz.owner_id != request.user.id:
                return Response({'detail': 'You do not have permission to access this quiz.'}, status=status.HTTP_403_FORBIDDEN)
            data = QuizDetailSerializer(quiz).data
            return Response(data, status=status.HTTP_200_OK)
        except Exception:
            return Response({'detail': 'Internal Server Error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, id: int):
        try:
            try:
                quiz = Quiz.objects.prefetch_related("questions").get(pk=id)
            except Quiz.DoesNotExist:
                return Response({"detail": "Quiz nicht gefunden."}, status=status.HTTP_404_NOT_FOUND)

            if quiz.owner_id != request.user.id:
                return Response({"detail": "Zugriff verweigert."}, status=status.HTTP_403_FORBIDDEN)

            serializer = QuizUpdateSerializer(
                quiz, data=request.data, partial=True)
            if not serializer.is_valid():
                return Response(
                    {"detail": "Ungültige Anfragedaten.",
                        "errors": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            serializer.save()
            return Response(QuizDetailSerializer(quiz).data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("PATCH quiz_detail failed")
            msg = f"Interner Serverfehler: {e}" if settings.DEBUG else "Interner Serverfehler."
            return Response({"detail": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, id: int):
        try:
            try:
                quiz = Quiz.objects.get(pk=id)
            except Quiz.DoesNotExist:
                return Response({'detail': 'Quiz could not be found.'},  status=status.HTTP_404_NOT_FOUND)
            if quiz.owner_id != request.user.id:
                return Response({'detail': 'You do not have permission to delete this quiz.'}, status=status.HTTP_403_FORBIDDEN)
            quiz.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception:
            return Response({'detail': 'Internal Server Error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
