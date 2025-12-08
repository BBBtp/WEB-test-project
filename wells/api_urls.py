from django.urls import path
from . import api_views

urlpatterns = [
    # Домен услуги (симптомы)
    path('symptoms/', api_views.ClinicalSymptomListAPIView.as_view(), name='api_symptoms_list'),
    path('symptoms/<int:pk>/', api_views.ClinicalSymptomDetailAPIView.as_view(), name='api_symptom_detail'),
    path('symptoms/create/', api_views.ClinicalSymptomCreateAPIView.as_view(), name='api_symptom_create'),
    path('symptoms/<int:pk>/update/', api_views.ClinicalSymptomUpdateAPIView.as_view(), name='api_symptom_update'),
    path('symptoms/<int:pk>/delete/', api_views.ClinicalSymptomDeleteAPIView.as_view(), name='api_symptom_delete'),
    path('symptoms/<int:symptom_id>/add-to-draft/', api_views.add_symptom_to_draft, name='api_add_symptom_to_draft'),
    path('symptoms/<int:symptom_id>/upload-image/', api_views.upload_symptom_image, name='api_upload_symptom_image'),

    # Домен заявки
    path('cart/info/', api_views.get_cart_info, name='api_cart_info'),
    path('deep-vein-thrombosis/', api_views.RiskAssessmentListAPIView.as_view(), name='api_assessments_list'),
    path('deep-vein-thrombosis/<int:pk>/', api_views.RiskAssessmentDetailAPIView.as_view(), name='api_assessment_detail'),
    path('deep-vein-thrombosis/<int:pk>/update/', api_views.RiskAssessmentUpdateAPIView.as_view(), name='api_assessment_update'),
    path('deep-vein-thrombosis/<int:assessment_id>/form/', api_views.form_assessment, name='api_form_assessment'),
    path('deep-vein-thrombosis/<int:assessment_id>/complete/', api_views.complete_assessment, name='api_complete_assessment'),
    path('deep-vein-thrombosis/<int:assessment_id>/delete/', api_views.delete_assessment, name='api_delete_assessment'),

    # Домен м-м (симптомы в заявке)
    path('deep-vein-thrombosis-symptoms/<int:pk>/', api_views.AssessmentSymptomUpdateAPIView.as_view(),
         name='api_assessment_symptom_update'),
    path('deep-vein-thrombosis-symptoms/<int:pk>/delete/', api_views.AssessmentSymptomDeleteAPIView.as_view(),
         name='api_assessment_symptom_delete'),

    # Домен пользователь (пока пустые)
    path('users/register/', api_views.user_register, name='api_user_register'),
    path('users/profile/', api_views.user_profile, name='api_user_profile'),
    path('users/profile/update/', api_views.user_update, name='api_user_update'),
    path('users/login/', api_views.user_login, name='api_user_login'),
    path('users/logout/', api_views.user_logout, name='api_user_logout'),
    path('users/public-key/', api_views.get_public_key, name='api_public_key'),
    path('users/csrf-token/', api_views.get_csrf_token, name='api_csrf_token'),
    path('users/active-sessions/', api_views.get_active_users_with_sessions, name='api_active_users_sessions'),

]
