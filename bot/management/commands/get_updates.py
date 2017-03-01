import logging
import sys
import time
from collections import OrderedDict

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import autoreload
from telebot import logger

logger.setLevel(logging.INFO)


class Command(BaseCommand):
    help = 'Загрузить обновления бота'
    tgbot = None
    verbosity = 1

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity')
        from bot.handlers import tgbot
        self.tgbot = tgbot
        self.tgbot.remove_webhook()
        autoreload.main(self.inner_handle)

    def print_handlers_counter(self):
        handlers = ['message', 'callback_query', 'edited_message', 'channel_post', 'edited_channel_post', 'inline', 'chosen_inline']
        count = OrderedDict()
        for handler in handlers:
            hd = getattr(self.tgbot, handler + '_handlers')
            if len(hd):
                count[handler] = len(hd)
        if count:
            logger.info('\nHandlers: %s' % ', '.join(['%s - %d' % (k, v) for k, v in count.items()]))
            if self.verbosity > 1:
                commands = []
                for message_handler in self.tgbot.message_handlers:
                    if message_handler['filters']['commands']:
                        commands.extend(message_handler['filters']['commands'])
                commands = set(commands)
                commands = sorted(commands)
                logger.info('All commands: %s', commands)

    def inner_handle(self, *args, **options):
        if settings.DEBUG:
            self.print_handlers_counter()
        self.tgbot.polling(True, 0, 30)
        while 1:
            try:
                time.sleep(100)
            except KeyboardInterrupt:
                sys.exit(0)
