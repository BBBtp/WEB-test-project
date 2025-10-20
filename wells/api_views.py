import uuid

import redis
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView, CreateAPIView, UpdateAPIView, DestroyAPIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from django.core.files.uploadedfile import InMemoryUploadedFile

from wells_project import settings
from .models import ClinicalSymptom, RiskAssessment, AssessmentSymptom
from .serializers import (
    ClinicalSymptomSerializer, ClinicalSymptomCreateSerializer,
    RiskAssessmentSerializer, RiskAssessmentListSerializer, RiskAssessmentUpdateSerializer,
    AssessmentSymptomSerializer, UserSerializer, UserCreateSerializer, UserLoginSerializer
)
from .minio_utils import upload_image, delete_image, generate_image_name
from .user_utils import get_creator_user

session_storage = redis.StrictRedis(host=settings.REDIS_HOST,
                                    port=settings.REDIS_PORT)


class IsModerator(permissions.BasePermission):
    """Доступ только модератору (is_staff=True)."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


@extend_schema(
    tags=["Symptoms"],
    summary="Список симптомов",
    parameters=[
        OpenApiParameter(name='search', description='Поиск по названию', required=False, type=str),
    ],
)
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


@extend_schema(tags=["Symptoms"], summary="Детали симптома")
class ClinicalSymptomDetailAPIView(RetrieveAPIView):
    """GET /api/symptoms/{id}/ - Одна запись симптома"""
    serializer_class = ClinicalSymptomSerializer
    queryset = ClinicalSymptom.objects.filter(is_active=True)


@extend_schema(tags=["Symptoms"], summary="Создать симптом")
class ClinicalSymptomCreateAPIView(CreateAPIView):
    """POST /api/symptoms/ - Добавление симптома (без изображения)"""
    serializer_class = ClinicalSymptomCreateSerializer
    permission_classes = [IsModerator]


@extend_schema(tags=["Symptoms"], summary="Обновить симптом")
class ClinicalSymptomUpdateAPIView(UpdateAPIView):
    """PUT /api/symptoms/{id}/ - Изменение симптома"""
    serializer_class = ClinicalSymptomCreateSerializer
    queryset = ClinicalSymptom.objects.filter(is_active=True)
    permission_classes = [IsModerator]


@extend_schema(tags=["Symptoms"], summary="Удалить симптом")
class ClinicalSymptomDeleteAPIView(DestroyAPIView):
    """DELETE /api/symptoms/{id}/ - Удаление симптома"""
    queryset = ClinicalSymptom.objects.filter(is_active=True)
    permission_classes = [IsModerator]

    def perform_destroy(self, instance):
        # Удаляем изображение из MinIO
        if instance.image_key:
            delete_image(f"{instance.image_key}.{instance.image_ext}")
        instance.delete()


@extend_schema(tags=["Cart"], summary="Добавить симптом в черновик заявки")
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def add_symptom_to_draft(request, symptom_id):
    """POST /api/symptoms/{id}/add-to-draft/ - Добавление симптома в оценку"""
    try:
        symptom = get_object_or_404(ClinicalSymptom, id=symptom_id, is_active=True)

        with transaction.atomic():
            # Создаем или получаем черновик оценки
            assessment, created = RiskAssessment.objects.get_or_create(
                patient=request.user,
                status=RiskAssessment.Status.DRAFT,
                defaults={
                    'topic': 'Оценка риска ТГВ/ТЭЛА',
                }
            )

            if created:
                assessment.formation_date = timezone.now()
                assessment.save()

            # Добавляем или обновляем симптом в оценке
            item, item_created = AssessmentSymptom.objects.get_or_create(
                assessment=assessment,
                symptom=symptom,
                defaults={
                    'quantity': 1,
                    'symptom_points': symptom.points,
                }
            )

            if not item_created:
                item.quantity += 1
                item.symptom_points = symptom.points
                item.save()

            return Response({
                'message': f'Симптом: {symptom.name} добавлен в оценку риска ТГВ/ТЭЛА',
                'assessment_id': assessment.id,
                'quantity': item.quantity
            }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=["Symptoms"], summary="Загрузить изображение для симптома")
@api_view(['POST'])
@permission_classes([IsModerator])
def upload_symptom_image(request, symptom_id):
    """POST /api/symptoms/{id}/upload-image/ - Добавление изображения к симптому"""
    try:
        symptom = get_object_or_404(ClinicalSymptom, id=symptom_id, is_active=True)

        if 'image' not in request.FILES:
            return Response({'error': 'Файл изображения не найден'}, status=status.HTTP_400_BAD_REQUEST)

        image_file = request.FILES['image']

        image_ext = image_file.name.rsplit('.', 1)[-1].lower()
        image_name = f"symptom_image_{symptom.id}.{image_ext}"

        # Загружаем изображение
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


@extend_schema(tags=["Cart"], summary="Информация о корзине (черновике)")
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_cart_info(request):
    """GET /api/cart/info/ - Информация о корзине (заявке-черновике)"""
    try:
        assessment = RiskAssessment.objects.filter(
            patient=request.user,
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


@extend_schema(
    tags=["Assessments"],
    summary="Список заявок",
    parameters=[
        OpenApiParameter(name='status', description='Фильтр по статусу', required=False, type=str),
        OpenApiParameter(name='date_from', description='Дата формирования от (YYYY-MM-DD)', required=False, type=str),
        OpenApiParameter(name='date_to', description='Дата формирования до (YYYY-MM-DD)', required=False, type=str),
    ],
)
class RiskAssessmentListAPIView(ListAPIView):
    """GET /api/assessments/ - Список заявок с фильтрацией"""
    serializer_class = RiskAssessmentListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = RiskAssessment.objects.exclude(
            status__in=[RiskAssessment.Status.DELETED, RiskAssessment.Status.DRAFT]
        ).select_related('patient', 'moderator')

        if not user.is_staff:
            queryset = queryset.filter(patient=user)
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


@extend_schema(tags=["Assessments"], summary="Детали заявки")
class RiskAssessmentDetailAPIView(RetrieveAPIView):
    """GET /api/assessments/{id}/ - Одна запись оценки риска ТГВ/ТЭЛА с симптомами"""
    serializer_class = RiskAssessmentSerializer
    queryset = RiskAssessment.objects.prefetch_related('assessment_symptoms__symptom')
    permission_classes = [permissions.IsAuthenticated]


@extend_schema(tags=["Assessments"], summary="Обновить заявку (только тема/комментарий)")
class RiskAssessmentUpdateAPIView(UpdateAPIView):
    """PUT /api/assessments/{id}/ - Изменение полей оценки риска ТГВ/ТЭЛА"""
    serializer_class = RiskAssessmentUpdateSerializer
    queryset = RiskAssessment.objects.all()
    permission_classes = [permissions.IsAuthenticated]


@extend_schema(tags=["Assessments"], summary="Сформировать заявку (создатель)")
@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def form_assessment(request, assessment_id):
    """PUT /api/assessments/{id}/form/ - Сформировать оценку риска ТГВ/ТЭЛА создателем"""
    try:
        assessment = get_object_or_404(
            RiskAssessment,
            id=assessment_id,
            patient=request.user,
            status=RiskAssessment.Status.DRAFT
        )

        # Проверяем обязательные поля
        if not assessment.topic:
            return Response({'error': 'Тема оценки риска ТГВ/ТЭЛА обязательна'}, status=status.HTTP_400_BAD_REQUEST)

        if assessment.assessment_symptoms.count() == 0:
            return Response({'error': 'В оценке риска ТГВ/ТЭЛА должен быть хотя бы один симптом'},
                            status=status.HTTP_400_BAD_REQUEST)

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


@extend_schema(tags=["Assessments"], summary="Завершить/отклонить заявку (модератор)")
@api_view(['PUT'])
@permission_classes([IsModerator])
def complete_assessment(request, assessment_id):
    """PUT /api/assessments/{id}/complete/ - Завершить/отклонить оценку риска ТГВ/ТЭЛА модератором"""
    try:
        assessment = get_object_or_404(RiskAssessment, id=assessment_id)

        action = request.data.get('action')  # 'complete' или 'reject'
        if action not in ['complete', 'reject']:
            return Response({'error': 'Действие должно быть "complete" или "reject"'},
                            status=status.HTTP_400_BAD_REQUEST)

        if assessment.status != RiskAssessment.Status.FORMED:
            return Response({'error': 'Можно завершить только сформированную оценку риска ТГВ/ТЭЛА'},
                            status=status.HTTP_400_BAD_REQUEST)

        if action == 'complete':
            assessment.status = RiskAssessment.Status.COMPLETED
        else:
            assessment.status = RiskAssessment.Status.REJECTED

        assessment.calculate_risk_level()
        assessment.moderator = request.user
        assessment.completion_date = timezone.now()
        assessment.save(
            update_fields=["status", "moderator", "completion_date", "risk_level", "recommendation",])

        return Response({
            'message': f'Оценка риска ТГВ/ТЭЛА {action}',
            'status': assessment.get_status_display(),
            'risk_level': assessment.get_risk_level_display()
        })

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=["Assessments"], summary="Удалить заявку (создатель)")
@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_assessment(request, assessment_id):
    """DELETE /api/assessments/{id}/ - Удаление оценки риска ТГВ/ТЭЛА"""
    try:
        assessment = get_object_or_404(
            RiskAssessment,
            id=assessment_id,
            patient=request.user
        )

        if assessment.status == RiskAssessment.Status.DELETED:
            return Response({'error': 'Оценка риска ТГВ/ТЭЛА уже удалена'}, status=status.HTTP_400_BAD_REQUEST)

        # Логическое удаление
        assessment.status = RiskAssessment.Status.DELETED
        assessment.save()

        return Response({'message': 'Оценка риска ТГВ/ТЭЛА удалена'})

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=["Assessment Items"], summary="Удалить позицию из заявки")
class AssessmentSymptomDeleteAPIView(DestroyAPIView):
    """DELETE /api/assessment-symptoms/{id}/ - Удаление симптома из оценки риска ТГВ/ТЭЛА"""
    queryset = AssessmentSymptom.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def perform_destroy(self, instance):
        instance.delete()


@extend_schema(tags=["Assessment Items"], summary="Обновить позицию заявки")
class AssessmentSymptomUpdateAPIView(UpdateAPIView):
    """PUT /api/assessment-symptoms/{id}/ - Изменение количества/порядка/значения в оценки риска ТГВ/ТЭЛА"""
    serializer_class = AssessmentSymptomSerializer
    queryset = AssessmentSymptom.objects.all()
    permission_classes = [permissions.IsAuthenticated]


@extend_schema(tags=["Auth"],
               summary="Регистрация пользователя",
               request=UserCreateSerializer,
               )
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def user_register(request):
    """POST /api/users/register/ - Регистрация пользователя"""
    serializer = UserCreateSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({'message': 'Регистрация успешна', 'username': user.username}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=["Auth"], summary="Профиль пользователя",
               request=UserSerializer)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_profile(request):
    """GET /api/users/profile/ - Получение профиля пользователя"""
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


@extend_schema(tags=["Auth"], summary="Обновить профиль пользователя",
               request=UserSerializer)
@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def user_update(request):
    """PUT /api/users/profile/ - Обновление профиля пользователя"""
    serializer = UserSerializer(request.user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response({'message': 'Профиль обновлен', 'user': serializer.data})
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=["Auth"], summary="Вход (SessionAuth)",
               request=UserLoginSerializer, )
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def user_login(request):
    """POST /api/users/login/ - Аутентификация пользователя (SessionAuth)"""
    from django.contrib.auth import authenticate, login
    serializer = UserLoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    username = request.data['username']
    password = request.data['password']
    user = authenticate(request, username=username, password=password)

    if user is None:
        return Response({"error": "Неверные данные для входа."},
                        status=status.HTTP_400_BAD_REQUEST)

    random_key = str(uuid.uuid4())
    session_storage.set(random_key, username)

    response = Response({
        'id': user.id,
        'username': user.username,
        'is_staff': user.is_staff,
    })
    response.set_cookie(
        "session_id", random_key,
    )

    return response


@extend_schema(tags=["Auth"], summary="Выход (SessionAuth)")
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def user_logout(request):
    """POST /api/users/logout/ - Деавторизация пользователя (SessionAuth)"""
    session_id = request.COOKIES.get('session_id')
    session_storage.delete(session_id)
    return Response(status=status.HTTP_204_NO_CONTENT)
