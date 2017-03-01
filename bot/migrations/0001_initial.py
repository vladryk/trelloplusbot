# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import bitfield.models
import dirtyfields.dirtyfields


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='MessageLink',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('chat_id', models.BigIntegerField()),
                ('original_message_id', models.BigIntegerField()),
                ('new_chat_id', models.BigIntegerField(db_index=True)),
                ('new_message_id', models.BigIntegerField(db_index=True)),
                ('extra', models.CharField(max_length=255, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='TgChat',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tg_id', models.BigIntegerField(unique=True)),
                ('active', models.BooleanField(default=True, verbose_name='Активен?')),
                ('type', models.CharField(max_length=10)),
                ('title', models.CharField(max_length=255)),
            ],
            options={
                'verbose_name_plural': '4. TgChat',
                'verbose_name': 'TgChat',
            },
            bases=(dirtyfields.dirtyfields.DirtyFieldsMixin, models.Model),
        ),
        migrations.CreateModel(
            name='TgMessage',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('tg_id', models.BigIntegerField(default=0, db_index=True)),
                ('from_tg_id', models.BigIntegerField(default=0)),
                ('message_id', models.BigIntegerField()),
                ('chat_type', models.CharField(max_length=100)),
                ('requests_made', models.IntegerField(default=0)),
                ('fnc', models.CharField(max_length=80, default='', db_index=True)),
                ('result', models.CharField(max_length=100, default='', db_index=True)),
                ('text', models.TextField()),
                ('message', models.TextField()),
                ('date', models.DateTimeField()),
                ('created_at', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('tgchat', models.ForeignKey(to='bot.TgChat', on_delete=django.db.models.deletion.SET_NULL, null=True)),
            ],
            options={
                'verbose_name_plural': '2. TgMessage',
                'verbose_name': 'TgMessage',
            },
        ),
        migrations.CreateModel(
            name='TgUser',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tg_id', models.BigIntegerField(unique=True)),
                ('active', models.BooleanField(default=True, verbose_name='Активен?')),
                ('username', models.CharField(max_length=255, blank=True)),
                ('first_name', models.CharField(max_length=255)),
                ('last_name', models.CharField(max_length=255, default='', blank=True)),
                ('last_active_at', models.DateTimeField(blank=True, null=True)),
                ('dialog', models.CharField(max_length=255, default='', editable=False, blank=True)),
                ('flags', bitfield.models.BitField((), blank=True, default=None)),
            ],
            options={
                'verbose_name_plural': '1. TgUser',
                'verbose_name': 'TgUser',
            },
            bases=(dirtyfields.dirtyfields.DirtyFieldsMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Trello',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('token', models.CharField(max_length=100)),
                ('token_created_at', models.DateTimeField()),
                ('tguser', models.OneToOneField(verbose_name='TgUser', to='bot.TgUser')),
            ],
        ),
        migrations.AddField(
            model_name='tgmessage',
            name='tguser',
            field=models.ForeignKey(to='bot.TgUser', on_delete=django.db.models.deletion.SET_NULL, null=True),
        ),
    ]
