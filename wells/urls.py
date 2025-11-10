from django.urls import path
from . import views

urlpatterns = [
    # Главная - список симптомов
    path("", views.symptoms_list, name="symptoms_list"),

    # Детальная страница симптома
    path("symptom/<int:symptom_id>/", views.symptom_detail, name="symptom_detail"),

    # Оценка риска
    path("deep-vein-thrombosis/<int:assessment_id>/", views.assessment_detail, name="assessment_detail"),
    path("deep-vein-thrombosis/current/", views.current_assessment_view, name="current_assessment"),
    path(
        "deep-vein-thrombosis/<int:assessment_id>/delete/",
        views.delete_assessment,
        name="delete_assessment",
    ),
    path(
        "deep-vein-thrombosis/<int:assessment_id>/deleted/",
        views.deleted_assessment_detail,
        name="deleted_assessment_detail",
    ),

    # Добавление симптома в оценку
    path(
        "symptom/<int:symptom_id>/add/",
        views.add_symptom_to_assessment,
        name="add_symptom_to_assessment",
    ),
    path(
        "deep-vein-thrombosis/<int:assessment_id>/symptom/<int:symptom_item_id>/remove/",
        views.remove_symptom_from_assessment,
        name="remove_symptom_from_assessment",
    ),

    # Обновление комментария к оценке
    path(
        "deep-vein-thrombosis/<int:assessment_id>/update_comment/",
        views.update_assessment_comment,
        name="update_assessment_comment",
    ),
]