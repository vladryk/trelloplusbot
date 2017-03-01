# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0002_auto_20170228_1252'),
    ]

    operations = [
        migrations.CreateModel(
            name='Timer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('board_id', models.CharField(max_length=50)),
                ('list_id', models.CharField(max_length=50)),
                ('card_id', models.CharField(max_length=50, db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('message_id', models.BigIntegerField(unique=True)),
                ('tguser', models.ForeignKey(to='bot.TgUser', verbose_name='TgUser')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
