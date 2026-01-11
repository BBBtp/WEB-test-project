from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import ClinicalSymptom, RiskAssessment, AssessmentSymptom

User = get_user_model()


class ClinicalSymptomSerializer(serializers.ModelSerializer):
    """Сериализатор для клинических симптомов"""
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ClinicalSymptom
        fields = [
            'id', 'name', 'slug', 'description', 'points',
            'risk_factor', 'is_active',
            'image_url'
        ]
        read_only_fields = ['id', 'image_url']

    def get_image_url(self, obj):
        """Получить URL изображения из Minio"""
        return obj.image_url


class ClinicalSymptomCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания симптомов (без изображения)"""

    class Meta:
        model = ClinicalSymptom
        fields = [
            'name', 'slug', 'description', 'points',
            'risk_factor', 'is_active'
        ]


class AssessmentSymptomSerializer(serializers.ModelSerializer):
    """Сериализатор для симптомов в оценке"""
    symptom_name = serializers.CharField(source='symptom.name', read_only=True)
    total_points = serializers.IntegerField(read_only=True)

    class Meta:
        model = AssessmentSymptom
        fields = [
            'id', 'symptom', 'symptom_name',
            'symptom_points', 'total_points',
        ]
        read_only_fields = ['id', 'symptom', 'symptom_name', 'total_points']


class RiskAssessmentSerializer(serializers.ModelSerializer):
    """Сериализатор для оценок риска с русскими названиями статуса и риска"""
    patient_username = serializers.CharField(source='patient.username', read_only=True)
    moderator_username = serializers.CharField(source='moderator.username', read_only=True)
    total_score = serializers.IntegerField(read_only=True)
    assessment_symptoms = AssessmentSymptomSerializer(many=True, read_only=True)

    # Вместо "status" и "risk_level" выводим русские значения
    status = serializers.CharField(source='get_status_display', read_only=True)
    risk_level = serializers.CharField(source='get_risk_level_display', read_only=True)

    class Meta:
        model = RiskAssessment
        fields = [
            'id', 'patient', 'patient_username', 'status', 'risk_level',
            'topic', 'recommendation', 'comment', 'result_value', 'formation_date',
            'completion_date', 'moderator', 'moderator_username',
            'created_at', 'total_score', 'assessment_symptoms'
        ]
        read_only_fields = [
            'id', 'patient', 'patient_username', 'status', 'risk_level',
            'recommendation', 'formation_date', 'completion_date',
            'moderator', 'moderator_username', 'created_at',
            'total_score', 'assessment_symptoms'
        ]


class RiskAssessmentListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка оценок риска"""
    patient_username = serializers.CharField(source='patient.username', read_only=True)
    moderator_username = serializers.CharField(source='moderator.username', read_only=True)
    total_score = serializers.IntegerField(read_only=True)

    class Meta:
        model = RiskAssessment
        fields = [
            'id', 'patient_username', 'status', 'risk_level',
            'topic', 'formation_date', 'completion_date',
            'moderator_username', 'created_at', 'total_score'
        ]


class RiskAssessmentUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор для обновления полей оценки"""

    class Meta:
        model = RiskAssessment
        fields = ['topic', 'comment']


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор для пользователей"""

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined', 'is_staff']
        read_only_fields = ['id', 'date_joined', 'is_staff']


class UserCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания пользователей"""
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password']

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    """Сериализатор для авторизации"""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
