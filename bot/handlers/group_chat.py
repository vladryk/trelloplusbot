import re

from django.db.models import Q
from telebot.types import Message, User

from bot import utils as bot_utils
from bot.handlers import tgbot
from bot.models import TgUser, MessageLink, TgMessage


class GroupHandler(bot_utils.BaseHandler):
    @staticmethod
    @tgbot.message_handler(TgUser.in_feedback, TgUser.is_reply, content_types=['text', 'photo', 'voice', 'document', 'sticker'])
    def feedback_chat_reply(tguser: TgUser):
        message = tguser.message
        reply_message = message.reply_to_message
        tgchat = tguser.tgchat
        assert isinstance(reply_message, Message)
        forward_from = reply_message.forward_from
        if not forward_from:
            raise bot_utils.ParamsErrorHandler('empty_forward_from')
        assert isinstance(forward_from, User)
        recipient_tguser = TgUser.objects.filter(tg_id=forward_from.id).first()
        if not recipient_tguser:
            tgchat.send_message('Пользователь не найден')
            raise bot_utils.ParamsErrorHandler('user_not_found')
        feedback_message_link = MessageLink.objects.filter(new_chat_id=reply_message.chat.id, new_message_id=reply_message.message_id).first()
        kwargs = {}
        if feedback_message_link:
            kwargs['reply_to_message_id'] = feedback_message_link.original_message_id
        if message.text:
            result = recipient_tguser.send_message(message.text, **kwargs)
        elif message.photo:
            result = recipient_tguser.send_photo(message.photo[-1].file_id, **kwargs)
        elif message.voice:
            result = recipient_tguser.send_voice(message.voice.file_id, **kwargs)
        elif message.document:
            result = recipient_tguser.send_document(message.document.file_id, **kwargs)
        elif message.sticker:
            result = recipient_tguser.send_sticker(message.sticker.file_id, **kwargs)
        else:
            tgchat.send_message('Неподдерживаемый тип сообщения')
            raise bot_utils.BaseErrorHandler('not_implemented')
        if result:
            tgchat.send_message('Ответ отправлен')
        else:
            tgchat.send_message('Бот деактивирован')

    @staticmethod
    @tgbot.message_handler(TgUser.in_feedback, TgUser.is_forward, content_types=['text', 'photo', 'voice', 'document', 'sticker'])
    def feedback_chat_forward(tguser: TgUser):
        message = tguser.message
        tgchat = tguser.tgchat
        forward_from = message.forward_from
        assert isinstance(forward_from, User)
        forward_tguser = TgUser.objects.filter(tg_id=forward_from.id).first()
        kwargs = dict(reply_to_message_id=message.message_id)
        if not forward_tguser:
            tgchat.send_message('Пользователь не найден', **kwargs)
            raise bot_utils.ParamsErrorHandler('user_not_found')
        assert isinstance(forward_tguser, TgUser)
        tgchat.send_message(forward_tguser.admin_name_advanced, **kwargs)

    @staticmethod
    @tgbot.message_handler(TgUser.in_feedback, commands=['send'])
    def send(tguser: TgUser):
        message = tguser.message
        tgchat = tguser.tgchat
        parts = re.split('\s+', message.text, maxsplit=2)
        if len(parts) != 3:
            tgchat.send_message('Правильно так: <b>/send TG_ID TEXT</b>')
            raise bot_utils.ParamsErrorHandler('wrong_format')
        tg_id = parts[1]
        text = parts[2]
        recipient_tguser = TgUser.objects.filter(Q(tg_id=tg_id) | Q(id=tg_id)).first()
        if not recipient_tguser:
            tgchat.send_message('Пользователь не найден')
            raise bot_utils.ParamsErrorHandler('user_not_found')
        assert isinstance(recipient_tguser, TgUser)
        result = recipient_tguser.send_message(text)
        if result:
            tgchat.send_message('Сообщение отправлено')
        else:
            last_message = TgMessage.objects.filter(from_tg_id=recipient_tguser.tg_id, chat_type='private').last()
            if last_message:
                assert isinstance(last_message, TgMessage)
                tgchat.send_message('Пользователь заблокировал бота. Вот его последнее сообщение боту (%s):' % last_message.date)
                tgchat.forward_message(recipient_tguser.tg_id, last_message.message_id)
            else:
                tgchat.send_message('Пользователь заблокировал бота')
