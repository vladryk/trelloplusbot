import logging
import re
from datetime import timedelta
from json import JSONDecodeError

from bitfield import BitField
from dirtyfields import DirtyFieldsMixin
from django.conf import settings
from django.db import models
from django.template import engines
from django.template.loaders.app_directories import Loader
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from telebot.apihelper import ApiException
from telebot.types import User, Chat, Message, CallbackQuery

from base import utils as base_utils
from base.models import DateTimeModel, MyModel
from bot import utils as bot_utils, emoji, smile
from bot.keyboards import InlineKeyboard
from bot.utils import TrelloClient

logger = logging.getLogger(__name__)


class TgBotApiModel(DirtyFieldsMixin, DateTimeModel, MyModel):
    tg_id = models.BigIntegerField(unique=True)
    active = models.BooleanField(default=True, verbose_name=u'Активен?')

    message = None  # Message
    callback_query = None  # CallbackQuery

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mute = False
        self.requests_made = 0

    @classmethod
    def load(cls, user, item):
        return cls.objects

    def smart_save(self, update_fields=None, *args, **kwargs):
        if update_fields:
            dirty_fields = self.get_dirty_fields().keys()
            if not list(set(update_fields) & set(dirty_fields)):
                return False
                # надо быть осторожнее, потому что если сохранить только некоторые поля, то флаг is_dirty с сущности снимается
        if not self.is_dirty():
            return False
        return self.save(update_fields=update_fields, *args, **kwargs)

    def mute(self):
        self._mute = True

    def unmute(self):
        self._mute = False

    def is_muted(self):
        return self._mute

    def deactivate(self):
        self.active = False
        self.save(update_fields=['active'])

    @classmethod
    def __process(cls, kwargs):
        kwargs.setdefault('disable_web_page_preview', True)
        kwargs.setdefault('parse_mode', 'HTML')
        return kwargs

    @classmethod
    def __text_length(cls, text):
        original_text = text
        max_length = 4096
        while len(str.encode(text)) > max_length:
            text = text[:len(text) - 5]
        if original_text != text:
            logger.warning('Too long text: %s' % original_text)
        return text

    @staticmethod
    def _load(template_name: str):
        django_engine = engines['django'].engine
        for template_loader in django_engine.template_loaders:
            if isinstance(template_loader, Loader):
                content, _ = template_loader.load_template_source(template_name)
                return content
        return None

    def render_to_string(self, template_name: str, context=None, sticker=None, document=None, photo=None, keyboard=None, reply_markup=None, edit=False, **kwargs):
        """
        На самом деле этот метод отправляет диалог. Но это имя ему задано для того чтобы IDE проверял пути к шаблонам.
        """
        if not self.active:
            return False
        if not context:
            context = {}
        self_key = self.__class__.__name__.lower()
        if self_key not in context:
            context[self_key] = self
        context['emoji'] = emoji
        context['smile'] = smile
        text = self._load(template_name)
        version = base_utils.md5(text.encode('utf-8'))
        title = None
        m = re.search(r'title:(?P<title>.+)\n', text)
        if m:
            title = m.group('title')
            text = text[:m.start()] + text[m.end():]
        name = template_name
        if name.find('bot/', 0, 4) == 0:
            name = name[4:]
        if name.find('.html', -5) != -1:
            name = name[:-5]
        title_parts = name.split('/')
        title_associate = {
            'private': 'Приватный чат',
            'group': 'Групповой чат',
            'errors': 'Ошибки',
            'tutorial': 'Обучение',
            'admin': 'Админам',
        }
        for i in range(len(title_parts)):
            part = title_parts[i]
            if part in title_associate:
                title_parts[i] = title_associate[part]
            elif i == len(title_parts) - 1 and title:
                title_parts[i] = title.strip()
        title = ' / '.join(title_parts)
        m = re.search(r'comment:(?P<comment>.+)\n', text)
        comment = ''
        if context and isinstance(context, dict):
            comment = 'context=%s' % list(context.keys())
        if m:
            comment += '\n' + m.group('comment')
            text = text[:m.start()] + text[m.end():]
        text = text.strip()
        text = bot_utils.render_from_string(text, context)
        if sticker:
            self.send_sticker(sticker, **kwargs)
        kwargs['keyboard'] = keyboard
        kwargs['reply_markup'] = reply_markup
        if document or photo:
            kwargs['caption'] = text
            if document:
                return self.send_document(document, **kwargs)
            elif photo:
                return self.send_photo(photo, **kwargs)
        return self.send_message(text, edit=edit, **kwargs)

    def reset(self):
        self.call_parent(super())

    def _exec_api_request(self, method: callable, *args, simple=False, reply=False, **kwargs):
        if not self.active:
            return False
        if self.is_muted():
            return False
        reply_markup = kwargs.pop('reply_markup', None)
        keyboard = kwargs.pop('keyboard', None)
        if reply_markup or keyboard:
            if not reply_markup and keyboard and isinstance(self, TgUser):
                keyboard = bot_utils.keyboard_factory(self, keyboard, reply_markup=False)
                if not simple or isinstance(keyboard, InlineKeyboard):
                    reply_markup = keyboard.get_reply_markup()
            kwargs['reply_markup'] = reply_markup
        if not simple and reply and self.message and self.message.message_id and 'reply_to_message_id' not in kwargs:
            kwargs['reply_to_message_id'] = self.message.message_id
        self.requests_made += 1
        try:
            if simple:
                return method(*args, **kwargs)
            else:
                return method(self.tg_id, *args, **kwargs)
        except ApiException as e:
            try:
                json_data = e.result.json()
            except JSONDecodeError:
                if settings.DEBUG:
                    raise
                base_utils.error_log_to_group_chat('Telegram response: %s' % e.result.content, trace=False)
                return False
            description = str(json_data['description'])
            if description in ('Bad Request: QUERY_ID_INVALID', 'Bad Request: message is not modified'):
                pass
            elif e.result.status_code == 403 \
                    or (e.result.status_code == 400 and description == 'Bad Request: chat not found'):
                self.deactivate()
            elif e.result.status_code == 429:
                logger.warning('tg_id: %d, %s' % (self.tg_id, description))
            else:
                text = 'tg_id: %d, e: %s, args: %s, kwargs: %s' % (self.tg_id, e, args, base_utils.get_dict(kwargs))
                logger.warning(text)
                if settings.DEBUG:
                    raise
                base_utils.error_log_to_group_chat(text)
        return False

    def send_message(self, text, reply_markup=None, edit=False, **kwargs):
        if not text:
            raise Warning('Empty text to send_message passed')
        if edit and self.callback_query and not hasattr(self, '_edited'):
            return self.edit_message_text(text, reply_markup=reply_markup, **kwargs)
        kwargs = self.__process(kwargs)
        text = self.__text_length(text)
        from bot.handlers import tgbot
        return self._exec_api_request(tgbot.send_message, text, reply_markup=reply_markup, **kwargs)

    def edit_message_text(self, text, reply_markup=None, **kwargs):
        if not self.callback_query:
            return False
        message = self.callback_query.message
        if not isinstance(message, Message):
            return False
        if not text:
            raise Warning('Empty text to send_message passed')
        self._edited = True
        kwargs = self.__process(kwargs)
        text = self.__text_length(text)
        from bot.handlers import tgbot
        return self._exec_api_request(tgbot.edit_message_text, text, message.chat.id, message.message_id, reply_markup=reply_markup, simple=True, **kwargs)

    def edit_message_reply_markup(self, reply_markup=None, **kwargs):
        if not self.callback_query:
            return False
        message = self.callback_query.message
        if not isinstance(message, Message):
            return False
        self._edited = True
        from bot.handlers import tgbot
        return self._exec_api_request(tgbot.edit_message_reply_markup, message.chat.id, message.message_id, reply_markup=reply_markup, simple=True, **kwargs)

    def send_sticker(self, code, **kwargs):
        from bot.handlers import tgbot
        return self._exec_api_request(tgbot.send_sticker, code, **kwargs)

    def send_venue(self, latitude, longitude, title, address, **kwargs):
        from bot.handlers import tgbot
        text = '%s\nКоординаты: %f,%f' % (address, latitude, longitude)
        self._exec_api_request(tgbot.send_message, text)
        return self._exec_api_request(tgbot.send_venue, latitude, longitude, title, address, **kwargs)

    def send_document(self, data, **kwargs):
        from bot.handlers import tgbot
        return self._exec_api_request(tgbot.send_document, data, **kwargs)

    def send_video(self, data, **kwargs):
        from bot.handlers import tgbot
        return self._exec_api_request(tgbot.send_video, data, **kwargs)

    def send_photo(self, data, **kwargs):
        from bot.handlers import tgbot
        return self._exec_api_request(tgbot.send_photo, data, **kwargs)

    def send_voice(self, data, **kwargs):
        from bot.handlers import tgbot
        return self._exec_api_request(tgbot.send_voice, data, **kwargs)

    def send_chat_action(self, action='typing'):
        from bot.handlers import tgbot
        return self._exec_api_request(tgbot.send_chat_action, action)

    def forward_message(self, from_chat_id, message_id, **kwargs):
        from bot.handlers import tgbot
        return self._exec_api_request(tgbot.forward_message, from_chat_id, message_id, **kwargs)

    def send_contact(self, phone_number, first_name, last_name=None, **kwargs):
        from bot.handlers import tgbot
        return self._exec_api_request(tgbot.send_contact, phone_number=phone_number, first_name=first_name, last_name=last_name, **kwargs)

    def answer_callback_query(self, text=None, show_alert=None, **kwargs):
        if not self.callback_query:
            return False
        answered = getattr(self, '__answered', False)
        if not answered:
            self.__answered = True
            from bot.handlers import tgbot
            return self._exec_api_request(tgbot.answer_callback_query, self.callback_query.id, text=text, show_alert=show_alert, simple=True, **kwargs)
        return False

    def simple_checks(self):
        # fake
        return True

    def checks(self, function: callable):
        # fake
        return True

    @cached_property
    def callback_query_splitted(self) -> list or None:
        return self.callback_query and self.callback_query.data.split()

    def callback_query_data_get(self, index: int, default=None, as_int=False):
        value = base_utils.get_item_safe(self.callback_query_splitted, index=index, default=default)
        if as_int:
            value = base_utils.my_int(value)
        return value

    def callback_query_data_answer(self):
        return self.callback_query_splitted[-1] == 'yes'

    def remove_inline_keyboard(self, text=None, show_alert=None, **kwargs):
        if not self.callback_query:
            return False
        self.edit_message_reply_markup()
        return self.answer_callback_query(text=text, show_alert=show_alert, **kwargs)


class TgChat(TgBotApiModel):
    type = models.CharField(max_length=10)
    title = models.CharField(max_length=255)

    class Meta:
        verbose_name_plural = verbose_name = 'TgChat'

    def __str__(self):
        return 'tg_id: %s' % self.tg_id

    @classmethod
    def load(cls, chat: Chat, item=None):
        tgchat = cls.objects.get_or_create(tg_id=chat.id, defaults=dict(
            type=chat.type,
            title=chat.title,
            active=True,
        ))[0]
        tgchat.active = True
        return tgchat


class FakeFeedbackTgChat(TgChat):
    class Meta:
        abstract = True

    def _exec_api_request(self, *args, **kwargs):
        return False


class TgUser(TgBotApiModel):
    username = models.CharField(max_length=255, blank=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, blank=True, default='')
    last_active_at = models.DateTimeField(null=True, blank=True)
    dialog = models.CharField(max_length=255, blank=True, default='', editable=False)
    flags = BitField(blank=True, flags=(
    ))
    tgchat = None  # TgChat
    after_unknown_text = None  # callable

    class Meta:
        verbose_name_plural = verbose_name = 'TgUser'

    def __str__(self):
        return self.admin_name

    @classmethod
    def load(cls, user: User, item):
        qs = (super().load(user, item) or cls.objects)
        qs = qs.select_related('trello')
        tguser = qs.get_or_create(tg_id=user.id)[0]
        tguser.username = user.username or ''
        tguser.first_name = user.first_name
        tguser.last_name = user.last_name or ''
        tguser.active = True
        if isinstance(item, CallbackQuery):
            tguser.callback_query = item
        elif isinstance(item, Message):
            tguser.message = item
            if user.id != item.chat.id:
                tguser.tgchat = TgChat.load(item.chat)
                tguser.tgchat.message = tguser.message
        return tguser

    def is_empty_dialog(self):
        return self.dialog == ''

    def get_dialog(self, index: int, default=None, part=None):
        parts = self.dialog.split(':')
        if part is not None:
            if parts[0] != part:
                return default
        return base_utils.get_item_safe(parts, index, default)

    def reset(self):
        self.call_parent(super())
        self.dialog = ''

    @property
    def name(self) -> str:
        return ('%s %s' % (self.first_name, self.last_name)).strip()

    @property
    def admin_username(self) -> str:
        return self.username and '@' + self.username or self.name

    @property
    def admin_name_short(self) -> str:
        return '%s (tg_id: %d, id: %d)' % (self.admin_username, self.tg_id, self.id)

    @property
    def admin_name(self) -> str:
        return super().admin_name if hasattr(super(), base_utils.func_name()) else self.admin_name_short

    def get_admin_name_advanced(self, request=None) -> str:
        links = []
        if not request or self.has_perm(request.user, 'change'):
            links.append(format_html('<a href="{}">📋</a>', self.get_url()))
        if not request or TgMessage.has_perm(request.user, 'change'):
            links.append(format_html('<a href="{}">✉️</a>', TgMessage.get_index_url(tg_id=self.tg_id)))
        if not links:
            return self.admin_name
        return format_html('{} {}', self.admin_name, mark_safe(' '.join(links)))

    @property
    def admin_name_advanced(self) -> str:
        return self.get_admin_name_advanced()

    def update_last_active(self) -> bool:
        now = timezone.now()
        if not self.last_active_at or self.last_active_at + timedelta(minutes=1) < now:
            self.last_active_at = now
        return True

    def is_private(self):
        return self.message and self.message.chat.type == 'private'

    def is_group(self):
        return self.message and (self.message.chat.type == 'group' or self.message.chat.type == 'supergroup')

    def in_feedback(self):
        if not self.message or not self.is_group():
            return False
        from bot.helpers import feedback_tgchat
        return feedback_tgchat().tg_id and self.message.chat.id == feedback_tgchat().tg_id

    def is_reply(self):
        return bool(self.message and self.message.reply_to_message)

    def is_forward(self):
        return bool(self.message and self.message.forward_from)

    def is_text(self):
        return bool(self.message and self.message.text)

    def is_admin(self):
        return self.tg_id in settings.TG_ADMINS

    def is_authorized(self):
        try:
            return bool(self.trello)
        except Trello.DoesNotExist:
            return False

    def simple_checks(self):
        if not self.phone_number:
            return False
        return super().simple_checks()

    def checks(self, function: callable):
        message = self.message
        if message and message.chat.type != 'private':
            return True
        from bot.handlers.other import OtherHandler
        if function in (OtherHandler.unknown_text, OtherHandler.unknown_content_type, OtherHandler.unknown_command):
            return True
        from bot.handlers.admin import AdminHandler
        if function in [getattr(AdminHandler, method) for method in dir(AdminHandler) if callable(getattr(AdminHandler, method))]:
            return True
        if message and message.forward_from and not settings.DEBUG and not self.is_admin():
            self.render_to_string('bot/private/errors/cannot_forward.html')
            return 'forward'
        return super().checks(function)

    @cached_property
    def client(self) -> TrelloClient:
        token = self.trello.token if self.is_authorized() else ''
        return TrelloClient(self, token)

    def authorize(self, token):
        if self.is_authorized():
            trello = self.trello
        else:
            trello = Trello(tguser=self)
        trello.token = token
        trello.token_created_at = timezone.now()
        trello.save()
        self.client.user_auth_token = token
        return bool(self.client.get_boards())

    def unauthorized(self):
        from bot.handlers.private_chat import PrivateHandler
        PrivateHandler.unauthorized(self)


class TgMessage(MyModel):
    tguser = models.ForeignKey(TgUser, null=True, on_delete=models.SET_NULL)
    tgchat = models.ForeignKey(TgChat, null=True, on_delete=models.SET_NULL)
    tg_id = models.BigIntegerField(default=0, db_index=True)
    from_tg_id = models.BigIntegerField(default=0)
    message_id = models.BigIntegerField()
    chat_type = models.CharField(max_length=100)
    requests_made = models.IntegerField(default=0)
    fnc = models.CharField(max_length=80, default='', db_index=True)
    result = models.CharField(max_length=100, default='', db_index=True)
    text = models.TextField()
    message = models.TextField()
    date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name_plural = verbose_name = 'TgMessage'

    def __str__(self):
        return '%d (date: %s)' % (self.id, self.date)

    def get_message(self) -> Message or None:
        if self.chat_type == 'callback_query':
            return None
        return Message.de_json(self.message)


class MessageLink(models.Model):
    chat_id = models.BigIntegerField()
    original_message_id = models.BigIntegerField()
    new_chat_id = models.BigIntegerField(db_index=True)
    new_message_id = models.BigIntegerField(db_index=True)
    extra = models.CharField(max_length=255, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def create(cls, message: Message, sent_message: Message, extra=''):
        if not isinstance(message, Message) or not isinstance(sent_message, Message):
            return
        return cls.objects.create(
            chat_id=message.chat.id,
            original_message_id=message.message_id,
            new_chat_id=sent_message.chat.id,
            new_message_id=sent_message.message_id,
            extra=str(extra),
        )


class Trello(models.Model):
    tguser = models.OneToOneField(verbose_name=TgUser.verbose_name(), to=TgUser)
    token = models.CharField(max_length=100)
    token_created_at = models.DateTimeField()


class Token(MyModel):
    token = models.CharField(max_length=100, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Timer(MyModel):
    tguser = models.ForeignKey(verbose_name=TgUser.verbose_name(), to=TgUser)
    board_id = models.CharField(max_length=50)
    list_id = models.CharField(max_length=50)
    card_id = models.CharField(max_length=50, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    message_id = models.BigIntegerField(unique=True)
