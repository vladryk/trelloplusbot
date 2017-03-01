import re
from copy import deepcopy

from django.utils import timezone
from telebot import types

from base import utils as base_utils
from bot import models as bot_models, emoji


class Keyboard(object):
    button_rows = [
        # examples:
        # ['title'],
        # [('emoji', 'title')],
        # [dict(text='title')],
    ]
    button = None
    SEPARATOR = ' '  # NO-BREAK SPACE

    def __init__(self, tguser, *args, **kwargs):
        assert isinstance(tguser, bot_models.TgUser)
        self.tguser = tguser
        self.args = args
        self.kwargs = kwargs

    @classmethod
    def emoji_to_regexp(cls, *emojis):
        if not emojis and not isinstance(cls.button, (tuple, list)):
            raise Exception('wrong button')
        return r'^(%s)%s' % ('|'.join([re.escape(cur_emoji) for cur_emoji in emojis or [cls.button[0]]]), Keyboard.SEPARATOR)

    @classmethod
    def text_to_regexp(cls, *texts, exact=True):
        if not texts and not isinstance(cls.button, (tuple, list)):
            raise Exception('wrong button')
        texts = texts or [cls.button[1]]
        text = '|'.join(map(re.escape, texts))
        if exact:
            return re.compile('^\w*(%s)$' % text, re.I)
        else:
            return re.compile('(%s)' % text, re.I)

    @classmethod
    def commands(cls) -> list:
        return [base_utils.un_camel(cls.__name__)]

    @classmethod
    def first_command(cls) -> str:
        return '/' + cls.commands()[0]

    @classmethod
    def join_button(cls, button: tuple or list):
        if len(button) > 2:
            raise Exception('too many elements in button')
        return cls.SEPARATOR.join(button)

    @classmethod
    def split_button(cls, text: str):
        res = text.split(cls.SEPARATOR, maxsplit=1)
        if len(res) == 2:
            return res
        return '', res[0]

    @classmethod
    def get_cls_button(cls) -> dict:
        if not cls.button:
            return {}
        button = deepcopy(cls.button)
        if isinstance(button, (str, tuple, list)):
            button = {'text': button}
        return button

    @classmethod
    def get_button(cls, button: dict or str or tuple or list = None, self_show=False, **kwargs) -> dict:
        button_defined = bool(button)
        update = button or kwargs
        if isinstance(update, (str, tuple, list)):
            update = {'text': update}
        button = cls.get_cls_button()
        button.update(update)
        text = button.get('text')
        if isinstance(text, (tuple, list)):
            button['text'] = cls.join_button(text)
        elif not button_defined and cls.button and isinstance(text, str):
            icon = None
            if isinstance(cls.button, (tuple, list)):
                icon = cls.button[0]
            elif isinstance(cls.button, dict) and 'text' in cls.button and isinstance(cls.button['text'], (tuple, list)):
                icon = cls.button['text'][0]
            if icon:
                button['text'] = cls.join_button((icon, text))
        return button

    def create_reply_markup(self):
        raise Exception('create_reply_markup is not implemented')

    def button_type(self, *args, **kwargs):
        raise Exception('button_type is not implemented')

    def create_button(self, button):
        button = self.get_button(button)
        assert isinstance(button, dict)
        text = button.pop('text', '')
        return self.button_type(text, **button)

    def get_reply_markup(self):
        reply_markup = self.create_reply_markup()
        assert isinstance(reply_markup, (types.InlineKeyboardMarkup, types.ReplyKeyboardMarkup, types.ReplyKeyboardRemove, types.ForceReply))
        for button_row in self.get_button_rows():
            # noinspection PyTypeChecker
            items = [self.create_button(button) for button in button_row]
            reply_markup.row(*items)
        return reply_markup

    def collect(self):
        return []

    def get_button_rows(self):
        button_rows = []
        keyboards = self.collect()
        if not any((keyboards, self.button_rows)):
            return [[self.get_self_button()]]
        for kb in keyboards:
            assert isinstance(kb, Keyboard)
            button_rows += kb.get_button_rows()
        return button_rows + list(self.button_rows)

    def redirect(self, klass):
        return klass(self.tguser, *self.args, **self.kwargs).get_button_rows()

    def get_self_button(self) -> dict:
        return self.get_button()


class InlineKeyboard(Keyboard):
    button_rows = [
        # example:
        # [dict(text='title', url=None, callback_data=None, switch_inline_query=None)],
    ]

    def create_reply_markup(self):
        return types.InlineKeyboardMarkup()

    def button_type(self, text, **button):
        return types.InlineKeyboardButton(text, **button)

    def get_self_button(self) -> dict:
        return self.get_button(callback_data=base_utils.join(*self.args))


class ReplyKeyboard(Keyboard):
    resize_keyboard = True
    one_time_keyboard = None
    button_rows = [
        # example:
        # [dict(text='title', request_contact=None, request_location=None)],
    ]

    def create_reply_markup(self):
        return types.ReplyKeyboardMarkup(resize_keyboard=self.resize_keyboard, one_time_keyboard=self.one_time_keyboard)

    def button_type(self, text, **button):
        return types.KeyboardButton(text, **button)


class Boards(InlineKeyboard):
    button = (emoji.BOARDS, 'Доски')

    def get_button_rows(self):
        rows = []
        boards, timer_board_ids = self.args
        for board in boards:
            name = board.name
            if board.id in timer_board_ids:
                name = (emoji.TIMER, name)
            rows.append([dict(text=name, callback_data='/board %s' % board.id)])
        return rows


class Lists(InlineKeyboard):
    def get_button_rows(self):
        rows = []
        lists, timer_list_ids = self.args
        for board_list in lists:
            name = board_list.name
            if board_list.id in timer_list_ids:
                name = (emoji.TIMER, name)
            rows.append([dict(text=name, callback_data='/board_list %s' % board_list.id)])
        rows.append([Back.get_button(callback_data='/back board')])
        return rows


class Cards(InlineKeyboard):
    def get_button_rows(self):
        rows = []
        list_id, cards, timer_card_ids = self.args
        for card in cards:
            name = card.name
            name = re.sub('\[R\]$', '', name)
            name = re.sub('#\s*$', '', name)
            if card.id in timer_card_ids:
                name = (emoji.TIMER, name)
            rows.append([dict(text=name, callback_data='/card %s' % card.id)])
        rows.append([Back.get_button(callback_data='/back list %s' % list_id)])
        return rows


class Card(InlineKeyboard):
    def get_button_rows(self):
        rows = []
        card_id, timer = self.args
        if timer:
            timer_spent = base_utils.mytime(timezone.now() - timer.created_at, True)
            rows.append([dict(text=timer_spent, callback_data='/timer %s' % card_id)])
            rows.append([
                dict(text=(emoji.STOP, 'Stop'), callback_data='/timer_stop %s' % card_id),
                dict(text=(emoji.RESET, 'Reset'), callback_data='/timer_reset %s' % card_id),
            ])
        else:
            rows.append([dict(text=(emoji.START, 'Start'), callback_data='/timer_start %s' % card_id), ])
        rows.append([Back.get_button(callback_data='/back card %s' % card_id)])
        return rows


class Start(ReplyKeyboard):
    button_rows = (
        (Boards.get_button(),),
    )


class Cancel(ReplyKeyboard):
    button = (emoji.CANCEL, 'Отмена')


class Help(ReplyKeyboard):
    button = (emoji.HELP, 'Помощь')


class Next(ReplyKeyboard):
    button = (emoji.NEXT, 'Далее')


class Skip(InlineKeyboard):
    button = (emoji.SKIP, 'Пропустить')


class Back(InlineKeyboard):
    button = (emoji.BACK, 'Назад')


class Delete(InlineKeyboard):
    button = (emoji.DELETE, 'Удалить')


class YesNo(InlineKeyboard):
    def __init__(self, tguser, *args, with_icons=True):
        super().__init__(tguser, *args)
        self.with_icons = with_icons

    def get_button_rows(self):
        buttons = [
            dict(text=(emoji.OK, 'Да') if self.with_icons else 'Да', callback_data='%s yes' % base_utils.join(*self.args)),
            dict(text=(emoji.CANCEL, 'Нет') if self.with_icons else 'Нет', callback_data='%s no' % base_utils.join(*self.args)),
        ]
        return [buttons]


class Items(InlineKeyboard):
    def __init__(self, tguser, items: list, *args, in_line: int = 5, show_item=False, item_str_func='__str__'):
        super().__init__(tguser, *args)
        self.items = items
        self.in_line = in_line
        self.show_item = show_item
        self.item_str_func = item_str_func
        args = list(self.args)
        if '%s' not in args:
            args.append('%s')
        self.command = base_utils.join(*args)

    def get_button_rows(self):
        rows = []
        for items in base_utils.chunks(list(enumerate(self.items, 1)), self.in_line):
            buttons = []
            for num, item in items:
                if self.show_item:
                    prop = getattr(item, self.item_str_func)
                    buttons.append(dict(text=prop() if callable(prop) else prop, callback_data=self.command % str(item.id)))
                else:
                    buttons.append(dict(text=str(num), callback_data=self.command % str(item)))
            rows.append(buttons)
        return rows


class List(InlineKeyboard):
    def __init__(self, tguser, command: str, items: dict, params=''):
        super().__init__(tguser)
        self.command = command
        self.items = items.items()
        self.params = str(params)

    def get_button_rows(self):
        rows = []
        for key, title in self.items:
            rows.append([dict(text=str(title), callback_data='%s %s %s' % (self.command, key, self.params))])
        return rows
