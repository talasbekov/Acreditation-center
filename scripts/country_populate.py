import os
import sys
import pathlib

# Скрипт живёт в scripts/ — добавляем корень проекта в sys.path, чтобы импортировать settings.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventproject.settings')

import django
django.setup()
from directories.models import Country

# CSV лежит рядом со скриптом — путь не зависит от текущей директории запуска.
_CSV = pathlib.Path(__file__).resolve().parent / "countries.csv"

# For an explanation of what is going on here, please refer to the TwD book.

def populate():
	file = open(_CSV, "r")
	lines = file.readlines()
	for line in lines:
		elements = line.split(',')
		print(elements[1], elements[2], elements[3], elements[4], elements[7], elements[8])
		c = Country(country_code = elements[1])
		c.name_kaz = elements[4]
		c.name_rus = elements[3]
		c.name_eng = elements[7]
		c.cis_flag = elements[8]
		c.save()
	file.close()




# Start execution here!
if __name__ == '__main__':
    print('Country population script...')
    populate()

