# Generated by Django 4.0.2 on 2022-02-02 15:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('players', '0018_alter_raidevent_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='raidevent',
            name='sign_off',
            field=models.ManyToManyField(null=True, to='players.CurrentUser'),
        ),
    ]
