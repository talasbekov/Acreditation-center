# Generated by Django 3.2 on 2022-04-18 16:03

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("directories", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentType",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("doc_code", models.CharField(max_length=20)),
                ("name_kaz", models.CharField(max_length=128)),
                ("name_rus", models.CharField(max_length=128)),
                ("name_eng", models.CharField(max_length=128)),
            ],
        ),
    ]
