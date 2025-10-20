from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from .models import RiskAssessment, AssessmentSymptom, ClinicalSymptom, SymptomCategory


class RiskAssessmentModelTests(TestCase):
    def setUp(self) -> None:
        """Настройка тестовых данных"""
        self.user = get_user_model().objects.create_user(
            username="patient1",
            password="test12345"
        )
        
        # Создаем категории симптомов
        self.category_clinical = SymptomCategory.objects.create(
            name="Клинические признаки",
            description="Видимые клинические проявления"
        )
        self.category_history = SymptomCategory.objects.create(
            name="Анамнез",
            description="История болезни пациента"
        )
        
        # Создаем тестовые симптомы
        self.symptom_dvt = ClinicalSymptom.objects.create(
            category=self.category_clinical,
            name="Клинические симптомы ТГВ",
            slug="clinical-dvt",
            description="Отек нижней конечности, болезненность по ходу глубоких вен",
            points=3,
            image_key="dvt_symptoms",
            risk_factor="Отек, болезненность, покраснение",
        )
        
        self.symptom_immobilization = ClinicalSymptom.objects.create(
            category=self.category_history,
            name="Недавняя иммобилизация",
            slug="immobilization",
            description="Постельный режим более 3 дней",
            points=1,
            image_key="immobilization",
            risk_factor="Длительная неподвижность",
        )
    
    def test_total_score_calculation(self) -> None:
        """Тест расчета общего балла"""
        assessment = RiskAssessment.objects.create(
            patient=self.user,
            topic="Тест оценки"
        )
        
        # Добавляем симптомы
        AssessmentSymptom.objects.create(
            assessment=assessment,
            symptom=self.symptom_dvt,
            quantity=1,
            symptom_points=self.symptom_dvt.points,
        )
        AssessmentSymptom.objects.create(
            assessment=assessment,
            symptom=self.symptom_immobilization,
            quantity=2,
            symptom_points=self.symptom_immobilization.points,
        )
        
        # Проверяем общий балл: 3*1 + 1*2 = 5
        self.assertEqual(assessment.total_score, 5)
    
    def test_risk_level_low(self) -> None:
        """Тест определения низкого уровня риска"""
        assessment = RiskAssessment.objects.create(
            patient=self.user,
            topic="Тест низкого риска"
        )
        
        # Добавляем симптом с 1 баллом
        AssessmentSymptom.objects.create(
            assessment=assessment,
            symptom=self.symptom_immobilization,
            quantity=1,
            symptom_points=self.symptom_immobilization.points,
        )
        
        assessment.calculate_risk_level()
        self.assertEqual(assessment.risk_level, RiskAssessment.RiskLevel.LOW)
        self.assertIn("Низкая вероятность", assessment.recommendation)
    
    def test_risk_level_moderate(self) -> None:
        """Тест определения среднего уровня риска"""
        assessment = RiskAssessment.objects.create(
            patient=self.user,
            topic="Тест среднего риска"
        )
        
        # Добавляем симптомы на 4 балла
        AssessmentSymptom.objects.create(
            assessment=assessment,
            symptom=self.symptom_dvt,
            quantity=1,
            symptom_points=self.symptom_dvt.points,
        )
        AssessmentSymptom.objects.create(
            assessment=assessment,
            symptom=self.symptom_immobilization,
            quantity=1,
            symptom_points=self.symptom_immobilization.points,
        )
        
        assessment.calculate_risk_level()
        self.assertEqual(assessment.risk_level, RiskAssessment.RiskLevel.MODERATE)
        self.assertIn("Умеренная вероятность", assessment.recommendation)
    
    def test_risk_level_high(self) -> None:
        """Тест определения высокого уровня риска"""
        assessment = RiskAssessment.objects.create(
            patient=self.user,
            topic="Тест высокого риска"
        )
        
        # Добавляем симптомы на 7+ баллов
        AssessmentSymptom.objects.create(
            assessment=assessment,
            symptom=self.symptom_dvt,
            quantity=3,  # 3 * 3 = 9 баллов
            symptom_points=self.symptom_dvt.points,
        )
        
        assessment.calculate_risk_level()
        self.assertEqual(assessment.risk_level, RiskAssessment.RiskLevel.HIGH)
        self.assertIn("Высокая вероятность", assessment.recommendation)
    
    def test_unique_symptom_in_assessment(self) -> None:
        """Тест уникальности симптома в оценке"""
        assessment = RiskAssessment.objects.create(
            patient=self.user,
            topic="Тест уникальности"
        )
        
        AssessmentSymptom.objects.create(
            assessment=assessment,
            symptom=self.symptom_dvt,
            quantity=1,
            symptom_points=self.symptom_dvt.points,
        )
        
        # Попытка добавить тот же симптом должна вызвать ошибку
        with self.assertRaises(IntegrityError):
            AssessmentSymptom.objects.create(
                assessment=assessment,
                symptom=self.symptom_dvt,
                quantity=1,
                symptom_points=self.symptom_dvt.points,
            )
    
    def test_image_url_generation(self) -> None:
        """Тест генерации URL изображения"""
        expected_url = "http://localhost:9000/medical-images/dvt_symptoms.jpg"
        self.assertEqual(self.symptom_dvt.get_image_url(), expected_url)
        
        # Тест с другим расширением
        self.symptom_dvt.image_ext = "png"
        expected_url = "http://localhost:9000/medical-images/dvt_symptoms.png"
        self.assertEqual(self.symptom_dvt.get_image_url(), expected_url)
    
    def test_draft_status_default(self) -> None:
        """Тест статуса черновика по умолчанию"""
        assessment = RiskAssessment.objects.create(
            patient=self.user,
            topic="Тест статуса"
        )
        self.assertEqual(assessment.status, RiskAssessment.Status.DRAFT)
    
    def test_multiple_assessments_per_user(self) -> None:
        """Тест создания нескольких оценок для одного пользователя"""
        assessment1 = RiskAssessment.objects.create(
            patient=self.user,
            topic="Первая оценка"
        )
        assessment2 = RiskAssessment.objects.create(
            patient=self.user,
            topic="Вторая оценка"
        )
        
        user_assessments = RiskAssessment.objects.filter(patient=self.user)
        self.assertEqual(user_assessments.count(), 2)
        self.assertIn(assessment1, user_assessments)
        self.assertIn(assessment2, user_assessments)