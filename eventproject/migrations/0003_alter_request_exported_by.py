# Generated by Django 3.2.13 on 2022-04-23 16:13

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("eventproject", "0002_operator_workplace"),
    ]

    operations = [
        migrations.AlterField(
            model_name="request",
            name="exported_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="exported_operator",
                to="eventproject.operator",
            ),
        ),
    ]
