from __future__ import annotations
from typing import Optional

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import connection, transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from django.utils import timezone

from .models import RiskAssessment, AssessmentSymptom, ClinicalSymptom

# Для совместимости с существующими шаблонами
ASSESSMENT_FORMULA = "Σ (баллы × выраженность)"


def _get_current_assessment(user) -> Optional[RiskAssessment]:
    """Получить текущий черновик оценки для авторизованного пользователя"""
    if not user.is_authenticated:
        return None

    return (
        RiskAssessment.objects.prefetch_related("assessment_symptoms__symptom")
        .filter(patient=user, status=RiskAssessment.Status.DRAFT)
        .order_by("-created_at")
        .first()
    )


def symptoms_list(request: HttpRequest) -> HttpResponse:
    """GET: Список симптомов с поиском и текущей оценкой"""
    
    search_query = request.GET.get("search", "").strip()
    symptoms = ClinicalSymptom.objects.filter(is_active=True)
    
    if search_query:
        symptoms = symptoms.filter(
            name__icontains=search_query
        )
    
    # Добавляем URL изображений для каждого симптома
    for symptom in symptoms:
        symptom.image_url = symptom.image_url
    
    current_assessment = _get_current_assessment(request.user)
    symptoms_count = 0
    if current_assessment:
        symptoms_count = current_assessment.assessment_symptoms.count()
    
    context = {
        "symptoms": symptoms,
        "search_query": search_query,
        "assessment": current_assessment,
        "symptoms_count": symptoms_count,
    }
    return render(request, "wells/symptoms_list.html", context)


def symptom_detail(request: HttpRequest, symptom_id: int) -> HttpResponse:
    """GET: Детальная информация о симптоме"""
    
    symptom = get_object_or_404(
        ClinicalSymptom,
        id=symptom_id,
        is_active=True
    )
    
    # Добавляем URL изображения
    symptom.image_url = symptom.image_url
    
    current_assessment = _get_current_assessment(request.user)
    is_in_assessment = False
    
    if current_assessment:
        is_in_assessment = current_assessment.assessment_symptoms.filter(
            symptom=symptom
        ).exists()
    
    context = {
        "symptom": symptom,
        "is_in_assessment": is_in_assessment,
        "assessment": current_assessment,
    }
    return render(request, "wells/symptom_detail.html", context)


def assessment_detail(request: HttpRequest, assessment_id: int) -> HttpResponse:
    """GET: Результат оценки риска"""
    
    if request.user.is_authenticated:
        assessment = get_object_or_404(
            RiskAssessment.objects.prefetch_related("assessment_symptoms__symptom"),
            id=assessment_id,
            patient=request.user
        )
    else:
        # Для неавторизованных пользователей - временная оценка
        assessment = get_object_or_404(
            RiskAssessment.objects.prefetch_related("assessment_symptoms__symptom"),
            id=assessment_id
        )
    
    if assessment.status == RiskAssessment.Status.DELETED:
        return redirect("deleted_assessment_detail", assessment_id=assessment.id)
    
    # Рассчитываем риск, если еще не рассчитан
    if not assessment.risk_level:
        assessment.calculate_risk_level()
    
    # Получаем симптомы с дополнительной информацией
    selected_symptoms = []
    for item in assessment.assessment_symptoms.all():
        symptom_data = {
            "item_id": item.id,
            "name": item.symptom.name,
            "points": item.symptom_points,
            "quantity": item.quantity,
            "image_url": item.symptom.image_url,
            "total_points": item.total_points,
        }
        selected_symptoms.append(symptom_data)
    
    # Определяем CSS класс для уровня риска
    risk_class = assessment.risk_level if assessment.risk_level else "low"
    
    context = {
        "assessment": assessment,
        "selected_symptoms": selected_symptoms,
        "total_score": assessment.total_score,
        "risk_level": assessment.get_risk_level_display(),
        "risk_class": risk_class,
        "recommendation": assessment.recommendation,
    }
    return render(request, "wells/assessment_detail.html", context)


@login_required
def current_assessment_view(request: HttpRequest) -> HttpResponse:
    """GET: Текущая оценка риска пользователя"""
    
    assessment = _get_current_assessment(request.user)
    if assessment is None:
        messages.info(request, "У вас пока нет активной оценки риска.")
        return redirect("symptoms_list")
    
    return redirect("assessment_detail", assessment_id=assessment.id)


@login_required
@transaction.atomic
def add_symptom_to_assessment(request: HttpRequest, symptom_id: int) -> HttpResponse:
    """POST: Добавить симптом в текущую оценку"""
    
    if request.method != "POST":
        raise Http404("Метод не поддерживается.")
    
    symptom = get_object_or_404(ClinicalSymptom, id=symptom_id, is_active=True)
    
    quantity_raw = request.POST.get("quantity", "1")
    try:
        quantity = int(quantity_raw)
    except ValueError:
        quantity = 1
    if quantity < 1:
        quantity = 1
    
    # Создаем или получаем черновик оценки
    assessment, assessment_created = RiskAssessment.objects.select_for_update().get_or_create(
        patient=request.user,
        status=RiskAssessment.Status.DRAFT,
        defaults={
            "topic": "Оценка риска ТГВ/ТЭЛА",
        },
    )
    
    if assessment_created and assessment.formation_date is None:
        assessment.formation_date = timezone.now()
        assessment.save(update_fields=("formation_date",))
    
    # Добавляем или обновляем симптом в оценке
    item, item_created = AssessmentSymptom.objects.get_or_create(
        assessment=assessment,
        symptom=symptom,
        defaults={
            "quantity": quantity,
            "symptom_points": symptom.points,
        },
    )

    messages.success(
        request,
        f"Симптом '{symptom.name}' добавлен в оценку. Текущая выраженность: {item.quantity}.",
    )
    return redirect("assessment_detail", assessment_id=assessment.id)


@login_required
@transaction.atomic
def remove_symptom_from_assessment(
    request: HttpRequest,
    assessment_id: int,
    symptom_item_id: int,
) -> HttpResponse:
    """POST: �?�?�?���?�?�?� �?��?���'�?�? �? �����?�%��� �?�Ő�?���"""
    
    if request.method != "POST":
        raise Http404("�?��'�?�? �?�� ���?�?�?��?���?����'�?�?.")
    
    assessment = get_object_or_404(
        RiskAssessment.objects.select_for_update(),
        id=assessment_id,
        patient=request.user,
        status=RiskAssessment.Status.DRAFT,
    )
    
    item = get_object_or_404(
        AssessmentSymptom.objects.select_for_update().select_related("symptom"),
        id=symptom_item_id,
        assessment=assessment,
    )
    symptom_name = item.symptom.name
    item.delete()
    
    # �����?�?�ؐ�'���'�? �?�?�?�?��?�? �?��?��� ��������� ����'�?���>�?�?�<��
    assessment.calculate_risk_level()
    
    messages.info(
        request,
        f"����?���'�?�? '{symptom_name}' ����?��?��? �? �����?�%��� �?�Ő�?���.",
    )
    return redirect("assessment_detail", assessment_id=assessment.id)


@login_required
def delete_assessment(request: HttpRequest, assessment_id: int) -> HttpResponse:
    """POST: Логическое удаление оценки через SQL"""
    
    if request.method != "POST":
        raise Http404("Метод не поддерживается.")
    
    assessment = get_object_or_404(
        RiskAssessment,
        id=assessment_id,
        patient=request.user,
    )
    
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE wells_riskassessment
            SET status = %s,
                formation_date = CURRENT_TIMESTAMP
            WHERE id = %s
              AND patient_id = %s
              AND status != %s
            """,
            [
                RiskAssessment.Status.DELETED,
                assessment.id,
                request.user.id,
                RiskAssessment.Status.DELETED,
            ],
        )
    
    messages.warning(request, "Оценка перемещена в удаленные.")
    return redirect("deleted_assessment_detail", assessment_id=assessment.id)


@login_required
def deleted_assessment_detail(request: HttpRequest, assessment_id: int) -> HttpResponse:
    """GET: Информация об удаленной оценке"""
    
    assessment = get_object_or_404(
        RiskAssessment.objects.select_related("patient"),
        id=assessment_id,
        patient=request.user,
    )
    
    if assessment.status != RiskAssessment.Status.DELETED:
        raise Http404("Оценка не удалена.")
    
    context = {
        "assessment": assessment,
    }
    return render(request, "wells/deleted_assessment.html", context)


def update_assessment_comment(request, assessment_id):
    assessment = get_object_or_404(RiskAssessment, id=assessment_id, patient=request.user)

    if request.method == "POST":
        comment = request.POST.get("comment", "").strip()  # получаем комментарий из формы
        assessment.comment = comment
        assessment.save(update_fields=["comment"])
        messages.success(request, "Комментарий успешно обновлён")

    return redirect("assessment_detail", assessment_id=assessment.id)