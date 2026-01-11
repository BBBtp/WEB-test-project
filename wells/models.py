from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import models


class ClinicalSymptom(models.Model):
    """Клинический симптом для оценки по шкале Уэллса"""
    name = models.CharField(max_length=200, verbose_name="Название симптома")
    slug = models.SlugField(unique=True, verbose_name="Слаг")
    description = models.TextField(verbose_name="Описание")
    points = models.IntegerField(verbose_name="Баллы по шкале Уэллса")
    image_url = models.URLField(blank=True, null=True, verbose_name="URL изображения")
    risk_factor = models.CharField(max_length=200, verbose_name="Фактор риска")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        verbose_name = "Клинический симптом"
        verbose_name_plural = "Клинические симптомы"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class RiskAssessment(models.Model):
    """Оценка риска ТГВ/ТЭЛА"""

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        FORMED = "formed", "Сформирован"
        COMPLETED = "completed", "Завершен"
        REJECTED = "rejected", "Отклонен"
        DELETED = "deleted", "Удален"

    class RiskLevel(models.TextChoices):
        LOW = "low", "Низкий риск"
        MODERATE = "moderate", "Умеренный риск"
        HIGH = "high", "Высокий риск"

    patient = models.ForeignKey(
        get_user_model(),
        on_delete=models.PROTECT,
        related_name="risk_assessments",
        verbose_name="Пациент"
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
        verbose_name="Статус"
    )
    risk_level = models.CharField(
        max_length=20,
        choices=RiskLevel.choices,
        blank=True,
        null = True,
        verbose_name="Уровень риска"
    )
    topic = models.CharField(
        max_length=180,
        null=True,
        blank=True,
        verbose_name="Тема оценки"
    )
    recommendation = models.TextField(blank=True,null = True, verbose_name="Рекомендации")
    comment = models.TextField(blank=True,null = True, verbose_name="Комментарий")
    result_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Результат вычисления"
    )
    formation_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата формирования")
    completion_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата завершения")
    moderator = models.ForeignKey(
        get_user_model(),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="moderated_risk_assessments",
        verbose_name="Модератор"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Оценка риска"
        verbose_name_plural = "Оценки риска"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("patient", "status")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("patient",),
                condition=models.Q(status="draft"),
                name="unique_draft_risk_assessment_per_patient",
            ),
        ]

    def __str__(self) -> str:
        return f"Оценка риска №{self.pk} от {self.created_at.strftime('%d.%m.%Y')}"

    @property
    def total_score(self) -> int:
        """Сумма баллов всех симптомов"""
        return sum((item.total_points for item in self.assessment_symptoms.all()), start=0)

    def calculate_risk_level(self):
        """Рассчитать уровень риска на основе общего балла"""
        score = self.total_score

        if score <= 2:
            self.risk_level = self.RiskLevel.LOW
            self.recommendation = (
                "Низкая вероятность ТГВ/ТЭЛА (менее 15%). "
                "Рекомендуется D-димер тест и наблюдение."
            )
        elif score <= 6:
            self.risk_level = self.RiskLevel.MODERATE
            self.recommendation = (
                "Умеренная вероятность ТГВ/ТЭЛА (около 30%). "
                "Требуется УЗИ вен или КТ-ангиография."
            )
        else:
            self.risk_level = self.RiskLevel.HIGH
            self.recommendation = (
                "Высокая вероятность ТГВ/ТЭЛА (более 60%). "
                "Срочная консультация специалиста и начало антикоагулянтной терапии."
            )

        return self.risk_level


class AssessmentSymptom(models.Model):
    """Связь между оценкой и симптомом (many-to-many)"""
    assessment = models.ForeignKey(
        RiskAssessment,
        on_delete=models.PROTECT,
        related_name="assessment_symptoms",
        verbose_name="Оценка"
    )
    symptom = models.ForeignKey(
        ClinicalSymptom,
        on_delete=models.PROTECT,
        related_name="symptom_assessments",
        verbose_name="Симптом"
    )

    symptom_points = models.IntegerField(
        verbose_name="Баллы симптома",
        null=True,
        help_text="Баллы на момент добавления"
    )

    class Meta:
        verbose_name = "Симптом в оценке"
        verbose_name_plural = "Симптомы в оценке"
        constraints = [
            models.UniqueConstraint(
                fields=("assessment", "symptom"),
                name="unique_assessment_symptom",
            )
        ]

    def __str__(self) -> str:
        return f"{self.symptom.name}"

    @property
    def total_points(self) -> int:
        """Общие баллы с учетом количества"""
        return self.symptom_points or 0
