from django.db import models


class Sex(models.Model):
    name_kaz = models.CharField(max_length=128)
    name_rus = models.CharField(max_length=128)
    name_eng = models.CharField(max_length=128)
    sex_code = models.CharField(max_length=20)


class Country(models.Model):
    country_code = models.CharField(max_length=20)
    name_kaz = models.CharField(max_length=128)
    name_rus = models.CharField(max_length=128)
    name_eng = models.CharField(max_length=128)
    cis_flag = models.BooleanField(default=False)
    country_iso = models.CharField(max_length=20)

    def __str__(self):
        return self.name_rus


class DocumentType(models.Model):
    doc_code = models.CharField(max_length=20)
    name_kaz = models.CharField(max_length=128)
    name_rus = models.CharField(max_length=128)
    name_eng = models.CharField(max_length=128)

    def __str__(self):
        return self.name_rus


class City(models.Model):
    city_code = models.CharField(max_length=20)
    index = models.CharField(max_length=20)
    name_kaz = models.CharField(max_length=128)
    name_rus = models.CharField(max_length=128)
    name_eng = models.CharField(max_length=128)

    def __str__(self):
        return self.name_rus


class Category(models.Model):
    category_code = models.CharField(max_length=20)
    index = models.CharField(max_length=20)
    name_kaz = models.CharField(max_length=128)
    name_rus = models.CharField(max_length=128)
    name_eng = models.CharField(max_length=128)

    def __str__(self):
        return self.name_rus
