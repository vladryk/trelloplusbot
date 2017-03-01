# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Token',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, verbose_name='ID', primary_key=True)),
                ('token', models.CharField(db_index=True, max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AlterModelOptions(
            name='tgchat',
            options={'verbose_name': 'TgChat', 'verbose_name_plural': 'TgChat'},
        ),
        migrations.AlterModelOptions(
            name='tgmessage',
            options={'verbose_name': 'TgMessage', 'verbose_name_plural': 'TgMessage'},
        ),
        migrations.AlterModelOptions(
            name='tguser',
            options={'verbose_name': 'TgUser', 'verbose_name_plural': 'TgUser'},
        ),
    ]
