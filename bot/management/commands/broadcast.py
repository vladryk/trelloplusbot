import logging

from django.core.management.base import BaseCommand, CommandParser

from bot.models import TgUser

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Рассылка'

    def add_arguments(self, parser: CommandParser):
        super().add_arguments(parser)
        assert isinstance(parser, CommandParser)
        parser.add_argument('--text', '-t', dest='text', metavar='str', nargs='+', type=str, help='Custom text'),

    def handle(self, *args, **options):
        text = ['Доступ к боту открыт!']
        text = ' '.join(options.get('text') or text)  # sorry
        total = 0
        tgusers = TgUser.objects.filter(active=True)
        for tguser in tgusers:
            result = tguser.send_message(text, keyboard=tguser.keyboards.Start)
            if options['verbosity'] >= 2:
                print(tguser, bool(result))
            total += 1
        return 'Total: %d' % total
