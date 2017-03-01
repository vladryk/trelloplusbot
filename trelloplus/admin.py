from django.contrib.admin import site
from django.utils.safestring import mark_safe

from bot.utils import bot_url
from django.conf import settings


def init_admin():
    bot_link = '<a href="%s" target="_blank">@%s</a>' % (bot_url(), settings.TELEGRAM_BOT_NAME)
    site.site_header = mark_safe('Администрирование ' + bot_link)
    site.site_url = None
    site.index_title = site.site_title = 'Trello Plus Bot'
