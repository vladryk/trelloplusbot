from datetime import timedelta

import trolly
from django.utils import timezone
from telebot.types import Message

from base import utils as base_utils
from base.utils import mytime
from bot import utils as bot_utils, keyboards
from bot.handlers import tgbot
from bot.models import TgUser, Token, Timer
from bot.utils import TrelloClient


class PrivateHandler(bot_utils.BaseHandler):
    @staticmethod
    @tgbot.message_handler(TgUser.is_private, commands=keyboards.Start.commands())
    def start(tguser: TgUser):
        parts = tguser.message.text.split()
        if len(parts) == 2:
            # noinspection PyBroadException
            try:
                s = base_utils.real_urlsafe_b64decode(parts[1].encode()).decode()
                if s.startswith('token:'):
                    p = s.split(':')
                    if len(p) == 2:
                        token_id = p[1]
                        t = Token.objects.filter(id=token_id, created_at__gt=timezone.now() - timedelta(days=1)).first()
                        if t:
                            token = t.token
                            t.delete()
                            tguser.authorize(token)
                            return tguser.render_to_string('bot/private/authorized.html', keyboard=keyboards.Start)
            except Exception as e:
                pass
        if not tguser.is_authorized():
            PrivateHandler.unauthorized(tguser)

    @classmethod
    def unauthorized(cls, tguser: TgUser):
        assert isinstance(tguser.client, TrelloClient)
        url = tguser.client.get_authorisation_url()
        tguser.render_to_string('bot/private/errors/not_authorized.html', context=dict(url=url), edit=True)

    @staticmethod
    @tgbot.message_handler(TgUser.is_private, TgUser.is_authorized, regexp=keyboards.Boards.emoji_to_regexp())
    @tgbot.message_handler(TgUser.is_private, TgUser.is_authorized, commands=keyboards.Boards.commands())
    def boards(tguser: TgUser):
        assert isinstance(tguser.client, TrelloClient)
        boards = tguser.client.get_boards()
        timer_board_ids = tguser.timer_set.values_list('board_id', flat=True)
        tguser.render_to_string('bot/private/choose_board.html', keyboard=keyboards.Boards(tguser, boards, timer_board_ids), edit=True)

    @staticmethod
    @tgbot.callback_query_handler(TgUser.is_authorized, data_startswith='/board ')
    def board(tguser: TgUser, board_id=None):
        if board_id is None:
            board_id = tguser.callback_query_data_get(1)
        assert isinstance(tguser.client, TrelloClient)
        board = tguser.client.get_board(board_id)
        assert isinstance(board, trolly.Board)
        lists = board.get_lists()
        timer_list_ids = tguser.timer_set.values_list('list_id', flat=True)
        tguser.render_to_string('bot/private/choose_list.html', keyboard=keyboards.Lists(tguser, lists, timer_list_ids), edit=True)

    @staticmethod
    @tgbot.callback_query_handler(TgUser.is_authorized, data_startswith='/board_list ')
    def board_list(tguser: TgUser, list_id=None):
        if list_id is None:
            list_id = tguser.callback_query_data_get(1)
        assert isinstance(tguser.client, TrelloClient)
        board_list = tguser.client.get_list(list_id)
        assert isinstance(board_list, trolly.List)
        cards = board_list.get_cards()
        timer_card_ids = tguser.timer_set.values_list('card_id', flat=True)
        tguser.render_to_string('bot/private/choose_card.html', keyboard=keyboards.Cards(tguser, list_id, cards, timer_card_ids), edit=True)

    @staticmethod
    @tgbot.callback_query_handler(TgUser.is_authorized, data_startswith='/card ')
    def card(tguser: TgUser):
        card_id = tguser.callback_query_data_get(1)
        assert isinstance(tguser.client, TrelloClient)
        card = tguser.client.get_card(card_id)
        assert isinstance(card, trolly.Card)
        card_info = card.get_card_information()
        timer = tguser.timer_set.filter(card_id=card_id).first()
        message = tguser.render_to_string('bot/private/show_card.html', context=dict(card=card_info), keyboard=keyboards.Card(tguser, card_id, timer), edit=True)
        if timer:
            assert isinstance(message, Message)
            timer.message_id = message.message_id
            timer.save()

    @staticmethod
    @tgbot.callback_query_handler(TgUser.is_authorized, data_startswith='/timer_start ')
    def timer_start(tguser: TgUser):
        card_id = tguser.callback_query_data_get(1)
        assert isinstance(tguser.client, TrelloClient)
        card = tguser.client.get_card(card_id)
        assert isinstance(card, trolly.Card)
        timer = tguser.timer_set.filter(card_id=card_id).first()
        if timer:
            tguser.answer_callback_query('Timer was already started', show_alert=True)
            raise bot_utils.StateErrorHandler('timer_already_started')
        if tguser.timer_set.exists():
            tguser.answer_callback_query('You cannot start more than one timer simultaneously', show_alert=True)
            raise bot_utils.StateErrorHandler('multiple_timers')
        card_info = card.get_card_information()
        timer = tguser.timer_set.create(
            board_id=card_info['idBoard'],
            list_id=card_info['idList'],
            card_id=card_id,
            message_id=tguser.callback_query.message.message_id,
        )
        tguser.edit_message_reply_markup(keyboard=keyboards.Card(tguser, card_id, timer))

    @staticmethod
    @tgbot.callback_query_handler(TgUser.is_authorized, data_startswith='/timer ')
    def timer(tguser: TgUser):
        card_id = tguser.callback_query_data_get(1)
        assert isinstance(tguser.client, TrelloClient)
        card = tguser.client.get_card(card_id)
        assert isinstance(card, trolly.Card)
        timer = tguser.timer_set.filter(card_id=card_id).first()
        if not timer:
            tguser.answer_callback_query('Timer was not started', show_alert=True)
            raise bot_utils.StateErrorHandler('timer_not_started')
        tguser.edit_message_reply_markup(keyboard=keyboards.Card(tguser, card_id, timer))

    @staticmethod
    @tgbot.callback_query_handler(TgUser.is_authorized, data_startswith='/timer_stop ')
    def timer_stop(tguser: TgUser):
        card_id = tguser.callback_query_data_get(1)
        assert isinstance(tguser.client, TrelloClient)
        card = tguser.client.get_card(card_id)
        assert isinstance(card, trolly.Card)
        timer = tguser.timer_set.filter(card_id=card_id).first()
        if not timer:
            tguser.answer_callback_query('Timer was not started', show_alert=True)
            raise bot_utils.StateErrorHandler('timer_not_started')
        assert isinstance(timer, Timer)
        dur = timezone.now() - timer.created_at
        d = '%.2f' % (dur.seconds / 3600)
        card.add_comments('plus! %s/%s' % (d, d))
        timer.delete()
        logged = mytime(dur, True)
        tguser.answer_callback_query('Logged %s' % logged)
        tguser.edit_message_reply_markup(keyboard=keyboards.Card(tguser, card_id, None))

    @staticmethod
    @tgbot.callback_query_handler(TgUser.is_authorized, data_startswith='/timer_reset ')
    def timer_reset(tguser: TgUser):
        card_id = tguser.callback_query_data_get(1)
        assert isinstance(tguser.client, TrelloClient)
        card = tguser.client.get_card(card_id)
        assert isinstance(card, trolly.Card)
        timer = tguser.timer_set.filter(card_id=card_id).first()
        if not timer:
            tguser.answer_callback_query('Timer was not started', show_alert=True)
            raise bot_utils.StateErrorHandler('timer_not_started')
        timer.delete()
        tguser.answer_callback_query('Timer was reset!')
        tguser.edit_message_reply_markup(keyboard=keyboards.Card(tguser, card_id, None))

    @staticmethod
    @tgbot.callback_query_handler(TgUser.is_authorized, data_startswith='/back ')
    def back(tguser: TgUser):
        obj_type = tguser.callback_query_data_get(1)
        obj_id = tguser.callback_query_data_get(2)
        assert isinstance(tguser.client, TrelloClient)
        if obj_type == 'card':
            card = tguser.client.get_card(obj_id)
            assert isinstance(card, trolly.Card)
            card_info = card.get_card_information()
            return PrivateHandler.board_list(tguser, card_info['idList'])
        if obj_type == 'list':
            board_list = tguser.client.get_list(obj_id)
            assert isinstance(board_list, trolly.List)
            board = board_list.get_board()
            return PrivateHandler.board(tguser, board.id)
        PrivateHandler.boards(tguser)

    @staticmethod
    @tgbot.message_handler(TgUser.is_private, regexp=keyboards.Help.emoji_to_regexp())
    @tgbot.message_handler(TgUser.is_private, commands=keyboards.Help.commands() + ['sos'])
    def help(tguser: TgUser):
        tguser.render_to_string('bot/private/help.html', keyboard=tguser.keyboards.Start)

    @staticmethod
    @tgbot.message_handler(TgUser.is_private, commands=['settings'])
    def settings(tguser: TgUser):
        tguser.send_message('Настроек пока нет', keyboard=tguser.keyboards.Start)
