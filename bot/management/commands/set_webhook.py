import logging

import telebot
from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse

from django.conf import settings
from base.utils import site_url

telebot.logger.setLevel(logging.INFO)


class Command(BaseCommand):
    help = 'Установить webhook боту'

    def handle(self, *args, **options):
        tgbot = telebot.TeleBot(settings.TELEGRAM_BOT_TOKEN)
        tgbot.remove_webhook()
        url = reverse('bot_webhook', kwargs={'token_hash': settings.TELEGRAM_TOKEN_HASH})
        url = site_url(url)
        allowed_updates = ['message', 'callback_query']
        response = tgbot.set_webhook(url, allowed_updates=allowed_updates)
        telebot.logger.info(response)
