"""
Django management команда для предварительной генерации RSA ключей
Использование: python manage.py generate_rsa_keys
"""
from django.core.management.base import BaseCommand
from wells.rsa_utils import generate_rsa_keys, PRIVATE_KEY_PATH, PUBLIC_KEY_PATH


class Command(BaseCommand):
    help = 'Генерирует пару RSA ключей (приватный и публичный) для аутентификации'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно перезаписать существующие ключи',
        )

    def handle(self, *args, **options):
        self.stdout.write('Генерация RSA ключей...')
        
        try:
            # Проверяем, существуют ли уже ключи
            if PRIVATE_KEY_PATH.exists() or PUBLIC_KEY_PATH.exists():
                self.stdout.write(
                    self.style.WARNING(
                        f'Ключи уже существуют:\n'
                        f'  Приватный: {PRIVATE_KEY_PATH}\n'
                        f'  Публичный: {PUBLIC_KEY_PATH}\n'
                        f'Перезаписать? (y/n): '
                    )
                )
                # В неинтерактивном режиме просто перезаписываем
                if options.get('force', False):
                    self.stdout.write(self.style.WARNING('Принудительная перезапись...'))
                else:
                    self.stdout.write(self.style.WARNING('Пропуск генерации. Используйте --force для перезаписи.'))
                    return
            
            # Генерируем ключи
            private_key, public_key = generate_rsa_keys()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ RSA ключи успешно сгенерированы:\n'
                    f'  Приватный ключ: {PRIVATE_KEY_PATH}\n'
                    f'  Публичный ключ: {PUBLIC_KEY_PATH}\n'
                    f'  Размер ключа: 2048 бит'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка при генерации ключей: {str(e)}')
            )
            raise

