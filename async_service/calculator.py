"""
Логика вычисления risk_level и recommendation на основе total_score
"""
from typing import Dict


def calculate_risk_assessment(total_score: int) -> Dict[str, any]:
    """
    Рассчитать уровень риска и рекомендации на основе общего балла.
    
    Логика перенесена из Django модели RiskAssessment.calculate_risk_level()
    
    Args:
        total_score: Сумма баллов всех симптомов
        
    Returns:
        Словарь с ключами: result_value, risk_level, recommendation
    """
    # result_value = total_score (числовое значение для хранения)
    result_value = float(total_score)
    
    # Вычисление risk_level и recommendation по существующей логике
    if total_score <= 2:
        risk_level = "low"
        recommendation = (
            "Низкая вероятность ТГВ/ТЭЛА (менее 15%). "
            "Рекомендуется D-димер тест и наблюдение."
        )
    elif total_score <= 6:
        risk_level = "moderate"
        recommendation = (
            "Умеренная вероятность ТГВ/ТЭЛА (около 30%). "
            "Требуется УЗИ вен или КТ-ангиография."
        )
    else:
        risk_level = "high"
        recommendation = (
            "Высокая вероятность ТГВ/ТЭЛА (более 60%). "
            "Срочная консультация специалиста и начало антикоагулянтной терапии."
        )
    
    return {
        "result_value": result_value,
        "risk_level": risk_level,
        "recommendation": recommendation
    }
