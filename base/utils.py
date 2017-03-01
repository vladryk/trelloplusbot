import base64
import hashlib
import io
import os
import sys
import tempfile
import traceback
from datetime import timedelta, time

import filelock
from django.conf import settings
from django.core.management import call_command
from django.core.serializers import json
from django.db import models
from django.db.models import QuerySet
from django.http import QueryDict
from django.utils.html import escape, conditional_escape
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


def md5(data):
    m = hashlib.md5()
    m.update(data)
    return m.hexdigest()


def get_item_safe(l: list, index: int, default=None):
    try:
        return l[index]
    except IndexError:
        return default


def site_url(path: str, **kwargs) -> str:
    query_string = ''
    if kwargs:
        q = QueryDict('', mutable=True)
        q.update(**kwargs)
        query_string = '?' + q.urlencode()
    return 'http' + ('' if settings.DEBUG else 's') + '://' + settings.ALLOWED_HOSTS[0] + path + query_string


def get_field_names(klass: models.Model, exclude=None):
    fields = []
    if exclude is None:
        exclude = ('created_at', 'updated_at')
    # noinspection PyProtectedMember
    for field in klass._meta.fields:
        if exclude and field.name in exclude:
            continue
        fields.append(field.name)
    return fields


def error_log_to_group_chat(text: str = '', trace: bool = True, **kwargs):
    from bot.models import TgChat
    text = conditional_escape(text)
    tgchat = TgChat.objects.filter(tg_id=settings.ERROR_LOG_GROUP_ID).first()
    if not tgchat:
        return False
    if trace:
        exc = sys.exc_info()
        if None not in exc:
            text += '\n' + escape('\n'.join(traceback.format_exception(*exc)))
    assert isinstance(tgchat, TgChat)
    reply_markup = InlineKeyboardMarkup()
    reply_markup.add(InlineKeyboardButton('Fixed', callback_data='/error_fixed'))
    text = ('@%s:\n' % settings.TELEGRAM_BOT_NAME) + text
    if len(text) > 4096:
        text = text[:4096]
    return tgchat.send_message(text, reply_markup=reply_markup, **kwargs)


def un_camel(string: str) -> str:
    output = [string[0].lower()]
    for c in string[1:]:
        if c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            output.append('_')
            output.append(c.lower())
        else:
            output.append(c)
    return str.join('', output)


def get_dict(o):
    d = {}
    if isinstance(o, list):
        o_iter = enumerate(o)
    else:
        o_iter = o.items() if isinstance(o, dict) else o.__dict__.items()
    for x, y in o_iter:
        if hasattr(y, '__dict__'):
            d[x] = get_dict(y)
        elif isinstance(y, list):
            d[x] = []
            for k in y:
                d[x].append(get_dict(k) if hasattr(k, '__dict__') or isinstance(k, dict) else k)
        elif y is not None:
            d[x] = y
    return d


def to_json(o, **kwargs):
    data = dict(allow_nan=False, sort_keys=True, indent=4, ensure_ascii=False)
    data.update(kwargs)
    return json.DjangoJSONEncoder(**data).encode(get_dict(o))


def split(text: str, seps: iter or str = ' '):
    seps = tuple(seps)
    default_sep = seps[0]
    for sep in seps[1:]:
        text = text.replace(sep, default_sep)
    return [i.strip() for i in text.split(default_sep)]


def my_int(value, default=None):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def batch_qs(qs: QuerySet, batch_size=1000):
    """
    Returns a (start, end, total, queryset) tuple for each batch in the given
    queryset.

    Usage:
        # Make sure to order your querset
        article_qs = Article.objects.order_by('id')
        for start, end, total, qs in batch_qs(article_qs):
            print "Now processing %s - %s of %s" % (start + 1, end, total)
            for article in qs:
                print article.body
    """
    total = qs.count()
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        yield (qs[start:end], start, end, total)


def has_number(string: str) -> bool:
    return any(char.isdigit() for char in string)


def remove_not_numbers(string: str) -> str:
    return ''.join([char for char in string if char.isdigit()])


def as_list(item) -> list:
    if isinstance(item, (list, tuple, iter)):
        return list(item)
    return [item]


def lock(key: str, timeout=10):
    path = os.path.join(tempfile.gettempdir(), settings.BASE_DIR[1:])
    os.makedirs(path, exist_ok=True)
    return filelock.FileLock(os.path.join(path, key + '.lock'), timeout=timeout)


def unique(items: list or tuple):
    seen = set()
    seen_add = seen.add
    return [x for x in items if not (x in seen or seen_add(x))]


def chunks(l: list, n: int):
    """Yield successive n-sized chunks from l."""
    if n < 1:
        raise AttributeError('n = %s' % n)
    n = max(1, n)
    for i in range(0, len(l), n):
        yield l[i:i + n]


def func_name(n=0):
    # noinspection PyProtectedMember
    return sys._getframe(n + 1).f_code.co_name


class Memoized(object):
    def __init__(self, ttl=300):
        self.cache = {}
        self.ttl = ttl

    def __call__(self, func):
        def _memoized(*args):
            self.func = func
            import time
            now = time.time()
            try:
                value, last_update = self.cache[args]
                age = now - last_update
                if age > self.ttl:
                    raise AttributeError

                return value

            except (KeyError, AttributeError):
                value = self.func(*args)
                self.cache[args] = (value, now)
                return value

            except TypeError:
                return self.func(*args)

        return _memoized


def execute_command(module: object, *args, **options):
    s = io.StringIO()
    call_command(module.__name__.split('.')[-1], stdout=s, *args, **options)
    s.seek(0)
    return s.read()


def monkeypatch_method(cls):
    def decorator(func):
        setattr(cls, func.__name__, func)
        return func

    return decorator


def join(*items, sep=' '):
    return sep.join(map(str, items))


def delattr_safe(obj, name):
    if hasattr(obj, name):
        delattr(obj, name)


def get_ids(items: iter):
    return [item.id for item in items]


def real_urlsafe_b64encode(s):
    return base64.urlsafe_b64encode(s).strip(b'=')


def real_urlsafe_b64decode(s):
    s += b'=' * (4 - (len(s) % 4))
    return base64.urlsafe_b64decode(s)


def mytime(seconds: int or time or timedelta, with_seconds=False) -> str:
    if isinstance(seconds, time):
        # noinspection PyTypeChecker
        seconds = seconds.hour * 3600 + seconds.minute * 60
    elif isinstance(seconds, timedelta):
        seconds = seconds.seconds
    seconds = seconds and int(seconds) or 0
    h = seconds // 3600
    m = (seconds - h * 3600) // 60
    if with_seconds:
        return '%02d:%02d:%02d' % (h, m, seconds - h * 3600 - m * 60)
    return '%02d:%02d' % (h, m)
