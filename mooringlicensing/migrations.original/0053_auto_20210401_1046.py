# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-04-01 02:46
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0052_merge_20210401_1042'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='vesselsizecategory',
            name='created',
        ),
        migrations.RemoveField(
            model_name='vesselsizecategory',
            name='updated',
        ),
        migrations.RemoveField(
            model_name='vesselsizecategorygroup',
            name='created',
        ),
        migrations.RemoveField(
            model_name='vesselsizecategorygroup',
            name='updated',
        ),
    ]