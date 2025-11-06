from rest_framework import serializers
from quizzly_app.models import Quiz, Question


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'question_title', 'question_options',
                  'answer', 'created_at', 'updated_at']


class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True)

    class Meta:
        model = Quiz
        fields = ['id', 'title', 'description', 'created_at',
                  'updated_at', 'video_url', 'questions']


class QuestionSlimSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'question_title', 'question_options', 'answer']


class QuizSlimSerializer(serializers.ModelSerializer):
    questions = QuestionSlimSerializer(many=True)

    class Meta:
        model = Quiz
        fields = ['id', 'title', 'description', 'video_url', 'questions']


class QuizDetailSerializer(serializers.ModelSerializer):
    questions = QuestionSlimSerializer(many=True)

    class Meta:
        model = Quiz
        fields = ['id', 'title', 'description', 'created_at',
                  'updated_at', 'video_url', 'questions']


class QuizListSerializer(serializers.ModelSerializer):
    questions = QuestionSlimSerializer(many=True)

    class Meta:
        model = Quiz
        fields = ['id', 'title', 'description', 'created_at',
                  'updated_at', 'video_url', 'questions']


class QuizUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quiz
        fields = ['title', 'description']
        extra_kwargs = {
            "title": {"required": False, "allow_blank": False, "max_length": 255},
            "description": {"required": False, "allow_blank": True},
        }
