# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2017-05-26 20:27
from __future__ import unicode_literals

import datetime
from django.db import migrations, models
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('trans', '0004_auto_20170512_0548'),
    ]

    operations = [
        migrations.RenameField(
            model_name='translation',
            old_name='freezed',
            new_name='frozen',
        ),
        migrations.RemoveField(
            model_name='user',
            name='digit_font_base64',
        ),
        migrations.AddField(
            model_name='contest',
            name='enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='task',
            name='frozen',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='user',
            name='text_font_name',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='contentversion',
            name='create_time',
            field=models.DateTimeField(default=datetime.datetime(2017, 5, 26, 20, 27, 8, 93174, tzinfo=utc)),
        ),
        migrations.AlterField(
            model_name='task',
            name='enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='versionparticle',
            name='create_time',
            field=models.DateTimeField(default=datetime.datetime(2017, 5, 26, 20, 27, 8, 96649, tzinfo=utc)),
        ),
    ]