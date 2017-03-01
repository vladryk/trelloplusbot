from django.core import serializers
from telebot.types import ReplyKeyboardRemove

from bot import utils as bot_utils
from bot.handlers import tgbot
from bot.models import TgUser


class AdminHandler(bot_utils.BaseHandler):
    @staticmethod
    @tgbot.message_handler(TgUser.is_private, TgUser.is_admin, commands=['deleteme'])
    def deleteme(tguser: TgUser):
        tguser.delete()
        reply_markup = ReplyKeyboardRemove()
        tguser.send_message('Deleted', reply_markup=reply_markup)

    @staticmethod
    @tgbot.message_handler(TgUser.is_private, TgUser.is_admin, commands=['me'])
    def me(tguser: TgUser):
        tguser.send_message(serializers.serialize('json', [tguser], indent=True, ensure_ascii=False))

    @staticmethod
    @tgbot.callback_query_handler(TgUser.is_admin, data='/error_fixed')
    def error_fixed(tguser: TgUser):
        tguser.edit_message_text('Marked as fixed with %s' % tguser)
