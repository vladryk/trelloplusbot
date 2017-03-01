import logging

from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR
from telebot.types import Message, CallbackQuery, Update

from bot.permissions import BotPermission
from django.conf import settings
from base import utils as base_utils

logger = logging.getLogger(__name__)


class BotRequestView(CreateAPIView):
    permission_classes = [BotPermission]

    def post(self, request, *args, **kwargs):
        if len(request.data) == 0:
            return Response({'error': 'no data'}, status=HTTP_400_BAD_REQUEST)
        from bot.handlers import tgbot
        message_id = tg_id = ''
        try:
            update = Update.de_json(request.data)
            if update.message:
                assert isinstance(update.message, Message)
                message_id = update.message.message_id
                tg_id = update.message.from_user.id
            elif update.callback_query:
                assert isinstance(update.callback_query, CallbackQuery)
                message_id = update.callback_query.id
                tg_id = update.callback_query.from_user.id
            tgbot.process_new_updates([update])
        except Exception as e:
            if settings.TESTING:
                raise e
            base_utils.error_log_to_group_chat()
            logger.exception(e)
            if settings.TELEGRAM_RESPONSE_ERROR_ON_EXCEPTION:
                return Response({'error': 'exception'}, status=HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'status': 'OK'}, status=HTTP_200_OK)
