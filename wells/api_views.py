from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView, CreateAPIView, UpdateAPIView, DestroyAPIView
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from django.core.files.uploadedfile import InMemoryUploadedFile

from .models import ClinicalSymptom, RiskAssessment, AssessmentSymptom
from .serializers import (
    ClinicalSymptomSerializer, ClinicalSymptomCreateSerializer,
    RiskAssessmentSerializer, RiskAssessmentListSerializer, RiskAssessmentUpdateSerializer,
    AssessmentSymptomSerializer, UserSerializer, UserCreateSerializer
)
from .minio_utils import upload_image, delete_image, generate_image_name
from .user_utils import get_creator_user


class ClinicalSymptomListAPIView(ListAPIView):
    """GET /api/symptoms/ - Список симптомов с фильтрацией"""
    serializer_class = ClinicalSymptomSerializer

    
    def get_queryset(self):
        queryset = ClinicalSymptom.objects.filter(is_active=True)
        
        # Фильтрация по названию
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        return queryset.order_by('name')


class ClinicalSymptomDetailAPIView(RetrieveAPIView):
    """GET /api/symptoms/{id}/ - Одна запись симптома"""
    serializer_class = ClinicalSymptomSerializer
    queryset = ClinicalSymptom.objects.filter(is_active=True)


class ClinicalSymptomCreateAPIView(CreateAPIView):
    """POST /api/symptoms/ - Добавление симптома (без изображения)"""
    serializer_class = ClinicalSymptomCreateSerializer


class ClinicalSymptomUpdateAPIView(UpdateAPIView):
    """PUT /api/symptoms/{id}/ - Изменение симптома"""
    serializer_class = ClinicalSymptomCreateSerializer
    queryset = ClinicalSymptom.objects.filter(is_active=True)


class ClinicalSymptomDeleteAPIView(DestroyAPIView):
    """DELETE /api/symptoms/{id}/ - Удаление симптома"""
    queryset = ClinicalSymptom.objects.filter(is_active=True)
    
    def perform_destroy(self, instance):
        # Удаляем изображение из MinIO
        if instance.image_key:
            delete_image(f"{instance.image_url}")
        instance.delete()


@api_view(['POST'])
def add_symptom_to_draft(request, symptom_id):
    """POST /api/symptoms/{id}/add-to-draft/ - Добавление симптома в оценку"""
    try:
        symptom = get_object_or_404(ClinicalSymptom, id=symptom_id, is_active=True)

        with transaction.atomic():
            # Создаем или получаем черновик оценки
            assessment, created = RiskAssessment.objects.get_or_create(
                patient=get_creator_user(),
                status=RiskAssessment.Status.DRAFT,
                defaults={'topic': 'Оценка риска ТГВ/ТЭЛА'},
            )

            if created and not assessment.formation_date:
                assessment.formation_date = timezone.now()
                assessment.save(update_fields=["formation_date"])

            # Добавляем симптом, если его еще нет
            item, item_created = AssessmentSymptom.objects.get_or_create(
                assessment=assessment,
                symptom=symptom,
                defaults={'symptom_points': symptom.points},
            )

            if not item_created:
                # Симптом уже есть — просто обновляем баллы, если нужно
                item.symptom_points = symptom.points
                item.save(update_fields=["symptom_points"])
                message = f"Симптом '{symptom.name}' уже был добавлен в оценку."
            else:
                message = f"Симптом '{symptom.name}' добавлен в оценку риска ТГВ/ТЭЛА."

            return Response(
                {
                    "message": message,
                    "assessment_id": assessment.id,
                    "symptom_points": item.symptom_points,
                },
                status=status.HTTP_201_CREATED,
            )

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def upload_symptom_image(request, symptom_id):
    """POST /api/symptoms/{id}/upload-image/ - Добавление изображения к симптому"""
    try:
        symptom = get_object_or_404(ClinicalSymptom, id=symptom_id, is_active=True)

        if 'image' not in request.FILES:
            return Response({'error': 'Файл изображения не найден'}, status=status.HTTP_400_BAD_REQUEST)

        image_file = request.FILES['image']

        # Получаем расширение файла
        image_ext = image_file.name.rsplit('.', 1)[-1].lower()

        # Имя файла фиксированное для симптома
        image_name = f"symptom_image_{symptom.id}.{image_ext}"

        # Удаляем старое изображение, если нужно
        if symptom.image_url:
            delete_image(symptom.image_url.rsplit('/', 1)[-1])

        # Загружаем новое изображение
        if upload_image(image_file, image_name):
            symptom.image_url = f"http://localhost:9000/medical-images/{image_name}"
            symptom.save()

            return Response({
                'message': 'Изображение успешно загружено',
                'image_url': symptom.image_url
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({'error': 'Ошибка загрузки изображения'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def get_cart_info(request):
    """GET /api/cart/info/ - Информация о корзине (заявке-черновике)"""
    try:
        assessment = RiskAssessment.objects.filter(
            patient=get_creator_user(),
            status=RiskAssessment.Status.DRAFT
        ).first()
        
        if not assessment:
            return Response({
                'assessment_id': None,
                'symptoms_count': 0
            })
        
        symptoms_count = assessment.assessment_symptoms.count()
        
        return Response({
            'assessment_id': assessment.id,
            'symptoms_count': symptoms_count
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RiskAssessmentListAPIView(ListAPIView):
    """GET /api/assessments/ - Список заявок с фильтрацией"""
    serializer_class = RiskAssessmentListSerializer
    
    def get_queryset(self):
        queryset = RiskAssessment.objects.exclude(
            status__in=[RiskAssessment.Status.DELETED, RiskAssessment.Status.DRAFT]
        ).select_related('patient', 'moderator')
        
        # Фильтрация по статусу
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Фильтрация по диапазону даты формирования
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        
        if date_from:
            queryset = queryset.filter(formation_date__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(formation_date__date__lte=date_to)
        
        return queryset.order_by('-created_at')


class RiskAssessmentDetailAPIView(RetrieveAPIView):
    """GET /api/assessments/{id}/ - Одна запись оценки риска ТГВ/ТЭЛА с симптомами"""
    serializer_class = RiskAssessmentSerializer
    queryset = RiskAssessment.objects.prefetch_related('assessment_symptoms__symptom')


class RiskAssessmentUpdateAPIView(UpdateAPIView):
    """PUT /api/assessments/{id}/ - Изменение полей оценки риска ТГВ/ТЭЛА"""
    serializer_class = RiskAssessmentUpdateSerializer
    queryset = RiskAssessment.objects.all()


@api_view(['PUT'])
def form_assessment(request, assessment_id):
    """PUT /api/assessments/{id}/form/ - Сформировать оценку риска ТГВ/ТЭЛА создателем"""
    try:
        assessment = get_object_or_404(
            RiskAssessment,
            id=assessment_id,
            patient=get_creator_user(),
            status=RiskAssessment.Status.DRAFT
        )
        
        # Проверяем обязательные поля
        if not assessment.topic:
            return Response({'error': 'Тема оценки риска ТГВ/ТЭЛА обязательна'}, status=status.HTTP_400_BAD_REQUEST)
        
        if assessment.assessment_symptoms.count() == 0:
            return Response({'error': 'В оценке риска ТГВ/ТЭЛА должен быть хотя бы один симптом'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Обновляем статус и дату формирования
        assessment.status = RiskAssessment.Status.FORMED
        assessment.formation_date = timezone.now()
        assessment.save()
        
        return Response({
            'message': 'Оценка риска ТГВ/ТЭЛА успешно сформирована',
            'status': assessment.get_status_display()
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
def complete_assessment(request, assessment_id):
    """PUT /api/assessments/{id}/complete/ - Завершить/отклонить оценку риска ТГВ/ТЭЛА модератором"""
    try:
        assessment = get_object_or_404(RiskAssessment, id=assessment_id)
        
        action = request.data.get('action')  # 'complete' или 'reject'
        if action not in ['complete', 'reject']:
            return Response({'error': 'Действие должно быть "complete" или "reject"'}, status=status.HTTP_400_BAD_REQUEST)
        
        if assessment.status != RiskAssessment.Status.FORMED:
            return Response({'error': 'Можно завершить только сформированную оценку риска ТГВ/ТЭЛА'}, status=status.HTTP_400_BAD_REQUEST)

        if action == 'complete':
            assessment.status = RiskAssessment.Status.COMPLETED
        else:
            assessment.status = RiskAssessment.Status.REJECTED

        assessment.calculate_risk_level()
        assessment.status = RiskAssessment.Status.COMPLETED
        assessment.moderator = get_creator_user()
        assessment.completion_date = timezone.now()
        assessment.save(
            update_fields=["status", "moderator", "completion_date", "risk_level", "recommendation"])

        return Response({
            'message': f'Оценка риска ТГВ/ТЭЛА {action}',
            'status': assessment.get_status_display(),
            'risk_level': assessment.get_risk_level_display()
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
def delete_assessment(request, assessment_id):
    """DELETE /api/assessments/{id}/ - Удаление оценки риска ТГВ/ТЭЛА"""
    try:
        assessment = get_object_or_404(
            RiskAssessment,
            id=assessment_id,
            patient=get_creator_user()
        )
        
        if assessment.status == RiskAssessment.Status.DELETED:
            return Response({'error': 'Оценка риска ТГВ/ТЭЛА уже удалена'}, status=status.HTTP_400_BAD_REQUEST)

        # Логическое удаление
        assessment.status = RiskAssessment.Status.DELETED
        assessment.save()
        
        return Response({'message': 'Оценка риска ТГВ/ТЭЛА удалена'})
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AssessmentSymptomDeleteAPIView(DestroyAPIView):
    """DELETE /api/assessment-symptoms/{id}/ - Удаление симптома из оценки риска ТГВ/ТЭЛА"""
    queryset = AssessmentSymptom.objects.all()
    serializer_class = AssessmentSymptomSerializer

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


class AssessmentSymptomUpdateAPIView(UpdateAPIView):
    """PUT /api/assessment-symptoms/{id}/ - Изменение количества/порядка/значения в оценки риска ТГВ/ТЭЛА"""
    serializer_class = AssessmentSymptomSerializer
    queryset = AssessmentSymptom.objects.all()


# Пользовательские API (пока пустые)
@api_view(['POST'])
def user_register(request):
    """POST /api/users/register/ - Регистрация пользователя"""
    return Response({'message': 'Функция регистрации пока не реализована'}, status=status.HTTP_501_NOT_IMPLEMENTED)


@api_view(['GET'])
def user_profile(request):
    """GET /api/users/profile/ - Получение профиля пользователя"""
    return Response({'message': 'Функция профиля пока не реализована'}, status=status.HTTP_501_NOT_IMPLEMENTED)


@api_view(['PUT'])
def user_update(request):
    """PUT /api/users/profile/ - Обновление профиля пользователя"""
    return Response({'message': 'Функция обновления профиля пока не реализована'}, status=status.HTTP_501_NOT_IMPLEMENTED)


@api_view(['POST'])
def user_login(request):
    """POST /api/users/login/ - Аутентификация пользователя"""
    return Response({'message': 'Функция входа пока не реализована'}, status=status.HTTP_501_NOT_IMPLEMENTED)


@api_view(['POST'])
def user_logout(request):
    """POST /api/users/logout/ - Деавторизация пользователя"""
    return Response({'message': 'Функция выхода пока не реализована'}, status=status.HTTP_501_NOT_IMPLEMENTED)
