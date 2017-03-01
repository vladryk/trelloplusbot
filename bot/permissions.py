from django.conf import settings
from rest_framework import permissions


class BotPermission(permissions.BasePermission):
    message = 'Bot token is not valid.'

    def has_permission(self, request, view):
        token_hash = request.path.split('/')[-2]
        if token_hash != settings.TELEGRAM_TOKEN_HASH:
            return False
        return True
