# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-09-29 06:32
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0261_auto_20210928_1532'),
    ]

    operations = [
        migrations.AddField(
            model_name='applicationfee',
            name='fee_items_additional_aa',
            field=models.ManyToManyField(related_name='application_fees_additional_aa', to='mooringlicensing.FeeItem'),
        ),
    ]