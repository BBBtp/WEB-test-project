import uuid
import requests

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
from django.views.decorators.csrf import ensure_csrf_cookie

from wells_project import settings
from .models import ClinicalSymptom, RiskAssessment, AssessmentSymptom
from .serializers import (
    ClinicalSymptomSerializer, ClinicalSymptomCreateSerializer,
    RiskAssessmentSerializer, RiskAssessmentListSerializer, RiskAssessmentUpdateSerializer,
    AssessmentSymptomSerializer, UserSerializer, UserCreateSerializer, UserLoginSerializer
)
from .minio_utils import upload_image, delete_image, generate_image_name
from .rsa_utils import create_auth_token, get_public_key_pem
from .redis_lua_utils import get_active_users_with_sessions_lua

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
        OpenApiParameter(name='recently_viewed', description='Фильтр по недавно просмотренным (true/false)', required=False, type=bool),
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

        # Фильтрация по недавно просмотренным (только для неавторизованных пользователей)
        recently_viewed = self.request.query_params.get('recently_viewed', None)
        if recently_viewed and recently_viewed.lower() == 'true' and not self.request.user.is_authenticated:
            from .guest_session_utils import get_viewed_symptoms
            guest_session_id = getattr(self.request, 'guest_session_id', None)
            if guest_session_id:
                viewed_symptom_ids = get_viewed_symptoms(guest_session_id)
                if viewed_symptom_ids:
                    # Фильтруем по просмотренным симптомам, сохраняя порядок просмотра
                    # Создаем словарь для сохранения порядка
                    order_dict = {symptom_id: idx for idx, symptom_id in enumerate(viewed_symptom_ids)}
                    queryset = queryset.filter(id__in=viewed_symptom_ids)
                    # Сортируем по порядку просмотра (последние просмотренные первыми)
                    queryset = sorted(queryset, key=lambda x: order_dict.get(x.id, 999), reverse=True)
                    return queryset
                else:
                    # Если нет просмотренных симптомов, возвращаем пустой queryset
                    return queryset.none()

        return queryset.order_by('name')


@extend_schema(tags=["Symptoms"], summary="Детали симптома")
class ClinicalSymptomDetailAPIView(RetrieveAPIView):
    """GET /api/symptoms/{id}/ - Одна запись симптома"""
    serializer_class = ClinicalSymptomSerializer
    queryset = ClinicalSymptom.objects.filter(is_active=True)
    
    def retrieve(self, request, *args, **kwargs):
        # Получаем объект симптома
        instance = self.get_object()
        
        # Если пользователь не авторизован, добавляем симптом в просмотренные
        if not request.user.is_authenticated:
            from .guest_session_utils import add_viewed_symptom
            guest_session_id = getattr(request, 'guest_session_id', None)
            if guest_session_id:
                add_viewed_symptom(guest_session_id, instance.id)
        
        return super().retrieve(request, *args, **kwargs)


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
            assessment, created = RiskAssessment.objects.get_or_create(
                patient=request.user,
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
        # Используем request.user для получения черновика текущего пользователя
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

        # Проверяем, был ли уже выполнен асинхронный расчет
        # Если result_value отсутствует, запускаем асинхронный расчет
        if assessment.result_value is None:
            # Запускаем асинхронный расчет через async_service
            total_score = assessment.total_score
            import os
            async_service_url = os.getenv('ASYNC_SERVICE_URL', 'https://async_service:8444')
            if not async_service_url.endswith('/calculate'):
                async_service_url = f"{async_service_url}/calculate"
            
            payload = {
                "assessment_id": assessment_id,
                "total_score": total_score
            }
            
            try:
                # Отправляем запрос в асинхронный сервис (не ждем результата)
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                requests.post(async_service_url, json=payload, timeout=1, verify=False)
            except requests.exceptions.RequestException:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Если расчет уже был выполнен, используем существующие значения
            # risk_level и recommendation уже должны быть установлены асинхронным сервисом
            pass

        assessment.moderator = request.user
        assessment.completion_date = timezone.now()
        assessment.save(
            update_fields=["status", "moderator", "completion_date", "risk_level", "recommendation", "result_value"])

        return Response({
            'message': f'Оценка риска ТГВ/ТЭЛА {action}',
            'status': assessment.get_status_display(),
            'risk_level': assessment.get_risk_level_display() if assessment.risk_level else None,
            'calculation_status': 'async_started' if assessment.result_value is None else 'already_calculated'
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
    serializer_class = AssessmentSymptomSerializer

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

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


@extend_schema(
    tags=["Auth"], 
    summary="Вход (RSA SessionAuth)",
    description="Аутентификация пользователя с получением RSA-зашифрованного токена. "
                "Токен возвращается в заголовке X-Auth-Token. "
                "Используйте этот токен в заголовке X-Auth-Token или Authorization: Bearer <token> для последующих запросов.",
    request=UserLoginSerializer,
    responses={
        200: OpenApiResponse(
            description="Успешный вход. Токен в заголовке X-Auth-Token",
            response=UserSerializer
        ),
        400: OpenApiResponse(description="Неверные данные для входа")
    }
)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def user_login(request):
    """POST /api/users/login/ - Аутентификация пользователя (RSA SessionAuth через HTTP заголовки)"""
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

    rsa_token = create_auth_token(username, random_key)

    response = Response({
        'id': user.id,
        'username': user.username,
        'is_staff': user.is_staff,
    })

    response['X-Auth-Token'] = rsa_token
    response.set_cookie(
        "session_id", random_key,
    )

    return response


@extend_schema(
    tags=["Auth"], 
    summary="Выход (SessionAuth)",
    description="Деавторизация пользователя. Удаляет сессию из Redis и очищает cookie. "
                "После logout RSA токен становится недействительным, так как сессия удаляется из Redis."
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def user_logout(request):
    """POST /api/users/logout/ - Деавторизация пользователя (SessionAuth)"""
    # Пробуем получить session_id из заголовка или cookie
    session_id = None
    auth_token = request.META.get('HTTP_X_AUTH_TOKEN') or request.META.get('HTTP_AUTHORIZATION')
    
    if auth_token:
        if auth_token.startswith('Bearer '):
            auth_token = auth_token[7:]
        try:
            from .rsa_utils import parse_auth_token
            _, session_id = parse_auth_token(auth_token)
        except Exception:
            pass
    
    if not session_id:
        session_id = request.COOKIES.get('session_id')
    if session_id:
        session_storage.delete(session_id)
    response = Response({
    }, status=status.HTTP_200_OK)
    response.delete_cookie('session_id')
    
    return response


@extend_schema(
    tags=["Auth"], 
    summary="Получить публичный RSA ключ",
    description="Получение публичного RSA ключа для шифрования. "
                "Ключ используется для шифрования данных на клиенте. "
                "Сервер использует приватный ключ для расшифровки. "
                "Также устанавливает CSRF cookie для последующих запросов."
)
@ensure_csrf_cookie
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_public_key(request):
    """GET /api/users/public-key/ - Получение публичного RSA ключа для шифрования"""
    public_key = get_public_key_pem()
    return Response({
        'public_key': public_key,
        'format': 'PEM',
        'usage': 'Используйте этот ключ для шифрования токена аутентификации'
    })


@extend_schema(
    tags=["Auth"], 
    summary="Получить CSRF токен",
    description="Получение CSRF токена для использования в заголовке X-CSRFToken. "
                "Токен устанавливается в cookie csrftoken и возвращается в ответе."
)
@ensure_csrf_cookie
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_csrf_token(request):
    """GET /api/users/csrf-token/ - Получение CSRF токена"""
    from django.middleware.csrf import get_token
    csrf_token = get_token(request)
    return Response({
        'csrftoken': csrf_token,
        'message': 'Используйте этот токен в заголовке X-CSRFToken для POST/PUT/DELETE запросов'
    })


@extend_schema(tags=["Auth"], summary="Список активных пользователей с сессиями (Lua)")
@api_view(['GET'])
@permission_classes([IsModerator])
def get_active_users_with_sessions(request):
    """GET /api/users/active-sessions/ - Получение списка активных пользователей с их сессиями через Lua скрипт"""
    try:
        users_sessions = get_active_users_with_sessions_lua()
        return Response({
            'active_sessions': users_sessions,
            'total_users': len(users_sessions),
            'method': 'Lua script'
        })
    except Exception as e:
        return Response({
            'error': f'Ошибка получения активных сессий: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Константа для проверки API токена (8 байт)
API_TOKEN = "secret123"


@extend_schema(
    tags=["Assessments"],
    summary="Запустить асинхронный расчет risk_level",
    description="Отправляет запрос в асинхронный сервис для расчета risk_level и recommendation на основе total_score"
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def start_async_calculation(request, assessment_id):
    """
    POST /api/deep-vein-thrombosis/{id}/calculate/ - Запуск асинхронного расчета risk_level
    
    Получает total_score из заявки и отправляет запрос в асинхронный сервис.
    Возвращает 202 Accepted, так как расчет выполняется асинхронно.
    """
    try:
        # Получаем заявку
        assessment = get_object_or_404(
            RiskAssessment,
            id=assessment_id,
            patient=request.user
        )
        
        # Получаем total_score (вычисляемое свойство)
        total_score = assessment.total_score
        
        # URL асинхронного сервиса
        # Используем переменную окружения или имя контейнера Docker
        import os
        async_service_url = os.getenv('ASYNC_SERVICE_URL', 'http://async_service:8001')
        if not async_service_url.endswith('/calculate'):
            async_service_url = f"{async_service_url}/calculate"
        
        # Отправляем запрос в асинхронный сервис
        # Используем requests.post() в синхронном режиме, так как это Django view
        # Асинхронный сервис сам обработает задачу асинхронно
        payload = {
            "assessment_id": assessment_id,
            "total_score": total_score
        }
        
        try:
            # Для работы с self-signed сертификатами отключаем проверку SSL
            # В production это должно быть настроено правильно
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = requests.post(async_service_url, json=payload, timeout=1, verify=False)
            # Не ждем ответа, так как расчет выполняется асинхронно
        except requests.exceptions.RequestException:
            # Игнорируем ошибки подключения, так как сервис может быть недоступен
            # или обрабатывает запрос асинхронно
            pass
        
        return Response({
            'message': 'Расчет запущен асинхронно',
            'assessment_id': assessment_id,
            'total_score': total_score,
            'status': 'processing'
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=["Assessments"],
    summary="Принять результат от асинхронного сервиса",
    description="Принимает результат расчета от асинхронного сервиса. Требует заголовок X-API-TOKEN для авторизации."
)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])  # Разрешаем доступ без аутентификации, но проверяем токен
def receive_calculation_result(request, assessment_id):
    """
    POST /api/deep-vein-thrombosis/{id}/result/ - Прием результата от асинхронного сервиса
    
    Проверяет заголовок X-API-TOKEN и обновляет поля result_value, risk_level, recommendation.
    """
    # Проверка заголовка X-API-TOKEN
    api_token = request.META.get('HTTP_X_API_TOKEN')
    
    if api_token != API_TOKEN:
        return Response(
            {'error': 'Неверный API токен'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # Получаем заявку
        assessment = get_object_or_404(RiskAssessment, id=assessment_id)
        
        # Получаем данные из запроса
        result_value = request.data.get('result_value')
        risk_level = request.data.get('risk_level')
        recommendation = request.data.get('recommendation')
        
        # Валидация данных
        if result_value is None or risk_level is None or recommendation is None:
            return Response(
                {'error': 'Отсутствуют обязательные поля: result_value, risk_level, recommendation'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Проверка допустимых значений risk_level
        valid_risk_levels = [choice[0] for choice in RiskAssessment.RiskLevel.choices]
        if risk_level not in valid_risk_levels:
            return Response(
                {'error': f'Неверное значение risk_level. Допустимые: {valid_risk_levels}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Обновляем поля заявки
        assessment.result_value = result_value
        assessment.risk_level = risk_level
        assessment.recommendation = recommendation
        assessment.save(update_fields=['result_value', 'risk_level', 'recommendation'])
        
        return Response({
            'message': 'Результат успешно обновлен',
            'assessment_id': assessment_id,
            'result_value': result_value,
            'risk_level': risk_level
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
