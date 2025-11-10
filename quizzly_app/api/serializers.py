from rest_framework import serializers
from quizzly_app.models import Quiz, Question


class QuestionSerializer(serializers.ModelSerializer):
    """ 
    Serializer for Question model. It is used to serialize and represent the full model data due to a detailed quiz response or an internal operation.
    """
    class Meta:
        model = Question
        fields = ['id', 'question_title', 'question_options',
                  'answer', 'created_at', 'updated_at']


class QuizSerializer(serializers.ModelSerializer):
    """
    Provides a full nested representation of the Quiz model, includig all related questions.
    """
    questions = QuestionSerializer(many=True)

    class Meta:
        model = Quiz
        fields = ['id', 'title', 'description', 'created_at',
                  'updated_at', 'video_url', 'questions']


class QuestionSlimSerializer(serializers.ModelSerializer):
    """
    A slimmed-down serializer for Question model, excluding metadata fields.
    Used in contexts where only the core question data is needed.
    """
    class Meta:
        model = Question
        fields = ['id', 'question_title', 'question_options', 'answer']


class QuizSlimSerializer(serializers.ModelSerializer):
    """
    a slimmed-down serializer for Quiz model, excluding metadata fields.
    Used in contexts where only the core quiz data is needed.
    """
    questions = QuestionSlimSerializer(many=True)

    class Meta:
        model = Quiz
        fields = ['id', 'title', 'description', 'video_url', 'questions']


class QuizDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for Quiz model including slimmed-down questions from the QuestionSlimSerializer.
    Used for detailed quiz views without full question metadata.
    """
    questions = QuestionSlimSerializer(many=True)

    class Meta:
        model = Quiz
        fields = ['id', 'title', 'description', 'created_at',
                  'updated_at', 'video_url', 'questions']


class QuizListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing multiple quizzes. Provieds summary-level quiz informations.
    """
    questions = QuestionSlimSerializer(many=True)

    class Meta:
        model = Quiz
        fields = ['id', 'title', 'description', 'created_at',
                  'updated_at', 'video_url', 'questions']


class QuizUpdateSerializer(serializers.ModelSerializer):
    """
    Handles partial updates for existing quizzes (only title and description).
    """
    class Meta:
        model = Quiz
        fields = ['title', 'description']
        extra_kwargs = {
            "title": {"required": False, "allow_blank": False, "max_length": 255},
            "description": {"required": False, "allow_blank": True},
        }
