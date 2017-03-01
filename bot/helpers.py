import functools

from django.conf import settings

from bot.models import TgChat, FakeFeedbackTgChat


@functools.lru_cache()
def feedback_tgchat() -> TgChat:
    try:
        tgchat = TgChat.objects.get(tg_id=settings.FEEDBACK_GROUP_ID)
    except TgChat.DoesNotExist:
        tgchat = FakeFeedbackTgChat()
    assert isinstance(tgchat, TgChat)
    return tgchat
