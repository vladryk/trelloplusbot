from django.utils.translation import ugettext_lazy as _
import logging
import re
from collections import OrderedDict
from importlib import import_module

import six
from django.db import transaction
from django.utils import timezone
from django.utils.datetime_safe import datetime
from telebot import TeleBot
from telebot import util as telebot_util
from telebot.types import Message, JsonDeserializable, CallbackQuery, ReplyKeyboardRemove

from bot import utils as bot_utils
from bot.models import TgUser, TgMessage
from django.conf import settings
from base import utils as base_utils

tgbot = TeleBot(settings.TELEGRAM_BOT_TOKEN, threaded=False)

logger = logging.getLogger(__name__)


@base_utils.monkeypatch_method(JsonDeserializable)
def __str__(self):
    d = {}
    for x, y in six.iteritems(self.__dict__):
        if hasattr(y, '__dict__'):
            d[x] = y.__dict__
        elif y is not None:
            d[x] = y

    return six.text_type(d)


@base_utils.monkeypatch_method(TeleBot)
def callback_query_handler(self, *simple_funcs, **kwargs):
    def decorator(handler):
        handler_dict = self._build_handler_dict(handler, *simple_funcs, **kwargs)
        self.add_callback_query_handler(handler_dict)
        return handler

    return decorator


def exec_task(function, tguser: TgUser):
    check_result = tguser.checks(function)
    result = ''
    fnc = function.__qualname__
    if check_result is True:
        try:
            res = function(tguser)
            if res is False:
                result = 'fail'
            else:
                result = 'ok'
        except bot_utils.BaseErrorHandler as e:
            name = base_utils.un_camel(e.__class__.__name__).replace('_handler', '')
            result = '%s:%s' % (name, str(e))
    else:
        result = 'checks:' + check_result
    tguser.update_last_active()
    return fnc, result


def message_task(function, tgmessage: TgMessage, message: Message, tguser: TgUser):
    logger.debug('message: %s' % function.__qualname__)
    tgmessage.fnc, tgmessage.result = exec_task(function, tguser)
    tgmessage.requests_made = tguser.requests_made
    if not tguser.id:
        # was deleted
        return
    tgmessage.save()
    tguser.save_dirty_fields()


@base_utils.monkeypatch_method(TeleBot)
def _before_exec_message_task(self, msg_handler, message: Message, tguser: TgUser):
    tgmessage = TgMessage(
        tguser=tguser,
        tgchat=tguser.tgchat,
        tg_id=message.chat.id,
        from_tg_id=message.from_user.id,
        message_id=message.message_id,
        chat_type=message.chat.type,
        text=message.text or message.caption or 'content_type:%s' % message.content_type,
        message=base_utils.to_json(message),
        date=timezone.make_aware(datetime.fromtimestamp(message.date)),
    )
    self._exec_task(message_task, msg_handler['function'], tgmessage, message, tguser)


def callback_query_task(function: callable, tgmessage: TgMessage, callback_query: CallbackQuery, tguser: TgUser):
    logger.debug('callback: %s' % function.__qualname__)
    tgmessage.fnc, tgmessage.result = exec_task(function, tguser)
    tgmessage.requests_made = tguser.requests_made
    tgmessage.save()
    tguser.answer_callback_query()
    tguser.save_dirty_fields()


@base_utils.monkeypatch_method(TeleBot)
def _before_exec_callback_query_task(self, msg_handler, callback_query: CallbackQuery, tguser: TgUser):
    tgmessage = TgMessage(
        tguser=tguser,
        tg_id=callback_query.from_user.id,
        from_tg_id=callback_query.from_user.id,
        message_id=callback_query.message and callback_query.message.message_id,
        chat_type='callback_query',
        text=callback_query.data,
        message=base_utils.to_json(callback_query),
        date=timezone.now(),
    )
    self._exec_task(callback_query_task, msg_handler['function'], tgmessage, callback_query, tguser)


@base_utils.monkeypatch_method(TeleBot)
def _notify_command_handlers(self, handlers, items):
    for item in items:
        with base_utils.lock('tguser_%d' % item.from_user.id):
            with transaction.atomic():
                tguser = TgUser.load(item.from_user, item)
                assert isinstance(tguser, TgUser)
                if settings.UNDER_CONSTRUCTION and not tguser.is_admin():
                    tguser.send_message(_('The bot is under construction...'), reply=True, reply_markup=ReplyKeyboardRemove())
                    continue
                tries = 0
                while True:
                    tries += 1
                    try:
                        next_raised = False
                        for handler in handlers:
                            if self._test_message_handler(handler, item, tguser):
                                try:
                                    if isinstance(item, CallbackQuery):
                                        self._before_exec_callback_query_task(handler, item, tguser)
                                    elif isinstance(item, Message):
                                        self._before_exec_message_task(handler, item, tguser)
                                    next_raised = False
                                except bot_utils.NextHandler:
                                    next_raised = True
                                    continue
                                break
                        else:
                            if settings.DEBUG:
                                logger.debug('Unhandled update: %s', item)
                        if next_raised:
                            logger.warning('NextHandler raised but was not proceed! TgUser: %s, message: %s', tguser, base_utils.to_json(item, indent=None))
                    except bot_utils.RestartHandler:
                        if tries >= 10:
                            raise
                        continue
                    else:
                        break


def filter_commands(msg, tgu, filter_value):
    if msg.content_type != 'text':
        return False
    command = telebot_util.extract_command(msg.text)
    if not command:
        return False
    command = str(command).lower()
    return command in map(str.lower, filter_value)


test_cases = OrderedDict((
    ('content_types', lambda msg, tgu, filter_value: msg.content_type in filter_value),
    ('commands', filter_commands),
    ('func', lambda msg, tgu, filter_value: filter_value(tgu)),
    ('all', lambda msg, tgu, filter_value: all([func(tgu) for func in filter_value])),
    ('data', lambda msg, tgu, filter_value: msg.data and msg.data == filter_value),
    ('data_startswith', lambda msg, tgu, filter_value: msg.data and msg.data.startswith(filter_value)),
    ('regexp', lambda msg, tgu, filter_value: msg.content_type == 'text' and msg.text and re.search(filter_value, msg.text)),
))


@base_utils.monkeypatch_method(TeleBot)
def _build_handler_dict(self, handler, *simple_funcs, **filters):
    return {
        'function': handler,
        'simple_funcs': simple_funcs,
        'filters': filters
    }


@base_utils.monkeypatch_method(TeleBot)
def message_handler(self, *simple_funcs, content_types=None, commands=None, func=None, data=None, data_startswith=None, regexp=None, **kwargs):
    if content_types is None:
        content_types = ['text']

    def decorator(handler):
        handler_dict = self._build_handler_dict(
            handler,
            *simple_funcs,
            commands=commands,
            regexp=regexp,
            func=func,
            content_types=content_types,
            data=data,
            data_startswith=data_startswith,
            **kwargs
        )
        self.add_message_handler(handler_dict)
        return handler

    return decorator


@base_utils.monkeypatch_method(TeleBot)
def _test_message_handler(self, msg_handler, message, tguser):
    for func in msg_handler['simple_funcs']:
        if not func(tguser):
            return False
    for filter_name, filter_func in test_cases.items():
        if filter_name not in msg_handler['filters']:
            continue
        filter_value = msg_handler['filters'][filter_name]
        if filter_value is None:
            continue
        if not filter_func(message, tguser, filter_value):
            return False
    return True


def define_handlers(path):
    module = import_module(path)
    for name in dir(module):
        kls = 'Handler' in name and getattr(module, name)
        if not kls or not issubclass(kls, bot_utils.BaseHandler):
            continue
        if not kls.is_abstract():
            getattr(kls, bot_utils.BaseHandler.define_handlers.__name__)()


for pth in settings.BOT_HANDLERS_MODULES:
    define_handlers(pth)
