from django.contrib import admin
from .models import RiskAssessment, AssessmentSymptom, ClinicalSymptom




@admin.register(ClinicalSymptom)
class ClinicalSymptomAdmin(admin.ModelAdmin):
    list_display = ("name", "points", "risk_factor", "is_active")
    list_filter = ("is_active", "points")
    search_fields = ("name", "description", "risk_factor")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    fieldsets = (
        ("Основная информация", {
            "fields": ("name", "slug", "is_active")
        }),
        ("Медицинские данные", {
            "fields": ("description", "risk_factor", "points")
        }),
        ("Изображение", {
            "fields": ("image_url",),
            "description": "Изображения хранятся в Minio"
        }),
    )


class AssessmentSymptomInline(admin.TabularInline):
    model = AssessmentSymptom
    extra = 0
    fields = ("symptom", "quantity", "symptom_points", "note")
    readonly_fields = ("symptom_points",)
    autocomplete_fields = ("symptom",)


@admin.register(RiskAssessment)
class RiskAssessmentAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "status", "risk_level", "total_score", "formation_date", "completion_date", "moderator", "created_at")
    list_filter = ("status", "risk_level", "moderator", "created_at")
    search_fields = ("topic", "patient__username", "patient__email", "moderator__username")
    readonly_fields = ("total_score", "created_at")
    inlines = (AssessmentSymptomInline,)
    date_hierarchy = "created_at"
    
    fieldsets = (
        ("Основная информация", {
            "fields": ("patient", "status", "topic", "moderator")
        }),
        ("Результаты оценки", {
            "fields": ("risk_level", "total_score", "recommendation")
        }),
        ("Хронология", {
            "fields": ("formation_date", "completion_date", "comment", "created_at")
        }),
    )

    def total_score(self, obj):
        """Показать общий балл в списке"""
        return obj.total_score
    total_score.short_description = "Общий балл"
    
    actions = ["calculate_risk_levels"]
    
    def calculate_risk_levels(self, request, queryset):
        """Действие для пересчета уровней риска"""
        for assessment in queryset:
            assessment.calculate_risk_level()
        self.message_user(
            request,
            f"Уровни риска пересчитаны для {queryset.count()} оценок."
        )
    calculate_risk_levels.short_description = "Пересчитать уровни риска"


@admin.register(AssessmentSymptom)
class AssessmentSymptomAdmin(admin.ModelAdmin):
    list_display = ("assessment", "symptom", "quantity", "symptom_points", "total_points")
    list_filter = ("assessment__status",)
    search_fields = ("symptom__name", "assessment__patient__username")
    autocomplete_fields = ("assessment", "symptom")
    readonly_fields = ("total_points",)
    
    def total_points(self, obj):
        """Показать общие баллы"""
        return obj.total_points
    total_points.short_description = "Общие баллы"