# Generated by Django 4.2.16 on 2025-02-24 11:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0022_semester_inbus_semester_id'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='submit',
            name='ip_address_hash',
        ),
        migrations.AddField(
            model_name='submit',
            name='ip_address',
            field=models.GenericIPAddressField(null=True, verbose_name='IP address'),
        ),
    ]
