from django.contrib.auth import get_user_model

User = get_user_model()


class UserSingleton:
    """Singleton для получения зафиксированного пользователя-создателя"""
    _instance = None
    _creator_user = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UserSingleton, cls).__new__(cls)
        return cls._instance

    def get_creator_user(self):
        """Получить пользователя-создателя (зафиксированного)"""
        if self._creator_user is None:
            # Создаем или получаем пользователя-создателя
            self._creator_user, created = User.objects.get_or_create(
                username='wells_creator',
                defaults={
                    'email': 'creator@wells.local',
                    'first_name': 'Wells',
                    'last_name': 'Creator',
                    'is_staff': True,
                }
            )
            # Устанавливаем пароль при создании (если пользователь был только что создан)
            if created:
                self._creator_user.set_password('wells_creator_password')
                self._creator_user.save()
        return self._creator_user


def get_creator_user():
    """Функция для получения пользователя-создателя"""
    singleton = UserSingleton()
    return singleton.get_creator_user()
