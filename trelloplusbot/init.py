# noinspection PyUnresolvedReferences
from django.db.models import Q, F, Value

from bot.models import *


def tguser(tguser_id: int = None) -> TgUser:
    if not tguser_id:
        return TgUser.objects.last()
    return TgUser.objects.get(pk=tguser_id)

