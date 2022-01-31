# Generated by Django 4.0.1 on 2022-01-31 18:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('players', '0008_alter_player_rank'),
    ]

    operations = [
        migrations.CreateModel(
            name='Roster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=20)),
                ('rank', models.IntegerField(choices=[(0, 'GM'), (1, 'Officer'), (2, 'Officer Alt'), (3, 'Raider'), (4, 'Second Main'), (5, 'Alt')])),
            ],
        ),
    ]
