from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.utils.deprecation import MiddlewareMixin

from wells.api_views import session_storage
from wells.rsa_utils import parse_auth_token

User = get_user_model()


class SessionMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Приоритет: сначала проверяем RSA токен в заголовке, затем cookie
        auth_token = request.META.get('HTTP_X_AUTH_TOKEN') or request.META.get('HTTP_AUTHORIZATION')
        
        if auth_token:
            # Убираем префикс "Bearer " если есть
            if auth_token.startswith('Bearer '):
                auth_token = auth_token[7:]
            
            try:
                username, session_id = parse_auth_token(auth_token)
                # Проверяем, что сессия существует в Redis
                stored_username = session_storage.get(session_id)
                if stored_username and stored_username.decode('utf-8') == username:
                    request.user = User.objects.filter(username=username).first()
                    if request.user:
                        return
            except (ValueError, Exception):
                pass

        ssid = request.COOKIES.get("session_id")
        if ssid:
            username = session_storage.get(ssid)
            if username:
                username = username.decode('utf-8')
                request.user = User.objects.filter(username=username).first()
            else:
                request.user = AnonymousUser()
        else:
            request.user = AnonymousUser()

class DisableCSRFMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        setattr(request, '_dont_enforce_csrf_checks', True)
        response = self.get_response(request)
        return response



