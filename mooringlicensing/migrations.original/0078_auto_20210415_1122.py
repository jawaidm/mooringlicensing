# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-04-15 03:22
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0077_dcvpermit_submitter'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dcvpermit',
            name='lodgement_number',
            field=models.CharField(blank=True, default='', max_length=10),
        ),
    ]