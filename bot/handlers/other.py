from importlib import import_module

from telebot.types import Message

from bot import keyboards
from bot import utils as bot_utils
from bot.handlers import tgbot
from bot.helpers import feedback_tgchat
from bot.models import TgUser, TgChat, MessageLink
from django.conf import settings


def define_handlers_before_unknown_text(path):
    module = import_module(path)
    unknown_texts = []
    text_regexps = []
    for name in dir(module):
        kls = 'Handler' in name and getattr(module, name)
        if not kls or not issubclass(kls, bot_utils.BaseHandler):
            continue
        if not kls.is_abstract():
            unknown_texts.append(getattr(kls, bot_utils.BaseHandler.unknown_texts.__name__))
            text_regexps.append(getattr(kls, bot_utils.BaseHandler.text_regexps.__name__))
    for fnc in unknown_texts + text_regexps:
        fnc()


class OtherHandler(bot_utils.BaseHandler):
    @staticmethod
    @tgbot.message_handler(TgUser.is_private, func=lambda tguser: tguser.message.text.startswith('/'))
    def unknown_command(tguser: TgUser):
        tguser.render_to_string('bot/private/errors/unknown_command.html', keyboard=keyboards.Start)
        if tguser.after_unknown_text:
            tguser.after_unknown_text(tguser)
        OtherHandler.send_to_feedback_tgchat(tguser, feedback_tgchat())

    @staticmethod
    @tgbot.message_handler(TgUser.is_private, content_types=['sticker', 'voice', 'audio', 'location', 'venue', 'document', 'video'])
    def unknown_content_type(tguser: TgUser):
        tguser.render_to_string('bot/private/errors/unknown_content_type.html', keyboard=keyboards.Start)
        if tguser.after_unknown_text:
            tguser.after_unknown_text(tguser)

    @staticmethod
    @tgbot.message_handler(TgUser.is_private, regexp=keyboards.Cancel.emoji_to_regexp())
    @tgbot.message_handler(TgUser.is_private, commands=keyboards.Cancel.commands())
    def cancel(tguser: TgUser):
        tguser.reset()
        tguser.render_to_string('bot/private/canceled.html', keyboard=keyboards.Start)

    for path in settings.BOT_HANDLERS_MODULES:
        define_handlers_before_unknown_text(path)

    @staticmethod
    @tgbot.message_handler(TgUser.is_private, content_types=['text', 'photo', 'sticker', 'voice'])
    def unknown_text(tguser: TgUser):
        tguser.render_to_string('bot/private/errors/unknown_text.html', keyboard=keyboards.Start)
        if tguser.after_unknown_text:
            tguser.after_unknown_text(tguser)
        OtherHandler.send_to_feedback_tgchat(tguser, feedback_tgchat())

    @staticmethod
    @tgbot.edited_message_handler(func=TgUser.is_private)
    def edit_message(tguser: TgUser):
        tguser.render_to_string('bot/private/errors/cannot_edit_message.html')

    @staticmethod
    def send_to_feedback_tgchat(tguser: TgUser, tgchat: TgChat, additional=''):
        message = tguser.message
        reply_to_message = message.reply_to_message
        if hasattr(tguser, "current_call") and tguser.current_call:
            additional = ' во время <a href="%s">рабочего дня</a> (%s)%s' % (tguser.current_call.get_url(), tguser.current_call.get_state(), additional)
        tgchat.send_message('%s прислал%s:' % (tguser.admin_name_advanced, additional))
        sent_message = tgchat.forward_message(message.chat.id, message.message_id)
        if isinstance(reply_to_message, Message):
            tgchat.send_message('в ответ на:')
            tgchat.forward_message(reply_to_message.chat.id, reply_to_message.message_id)
        MessageLink.create(message, sent_message)

    @classmethod
    def text_regexps(cls):
        tgbot.message_handler(TgUser.is_private, regexp=keyboards.Cancel.text_to_regexp())(cls.cancel)
