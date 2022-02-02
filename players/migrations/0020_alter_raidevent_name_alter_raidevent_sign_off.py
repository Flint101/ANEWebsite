# Generated by Django 4.0.2 on 2022-02-02 15:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('players', '0019_alter_raidevent_sign_off'),
    ]

    operations = [
        migrations.AlterField(
            model_name='raidevent',
            name='name',
            field=models.CharField(default='Raid', max_length=30),
        ),
        migrations.AlterField(
            model_name='raidevent',
            name='sign_off',
            field=models.ManyToManyField(blank=True, null=True, to='players.CurrentUser'),
        ),
    ]
