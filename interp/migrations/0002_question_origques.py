# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-11-01 08:04
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('interp', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='origques',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='interp.Origques'),
        ),
    ]
