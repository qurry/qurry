# Generated by Django 3.1.2 on 2020-10-14 11:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='score',
        ),
        migrations.AddField(
            model_name='user',
            name='points',
            field=models.IntegerField(default=0, verbose_name='points'),
        ),
    ]
