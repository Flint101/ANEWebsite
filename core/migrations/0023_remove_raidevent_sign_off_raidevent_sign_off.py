# Generated by Django 4.0.2 on 2022-02-03 15:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_remove_raidevent_roster'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='raidevent',
            name='sign_off',
        ),
        migrations.AddField(
            model_name='raidevent',
            name='sign_off',
            field=models.CharField(default='placeholder', max_length=20),
            preserve_default=False,
        ),
    ]