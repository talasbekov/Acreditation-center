import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eventproject.settings")

import django

django.setup()
from directories.models import Category

# For an explanation of what is going on here, please refer to the TwD book.


def populate():
    file = open("categories.csv", "r")
    lines = file.readlines()
    for line in lines:
        elements = line.split(";")
        # print(elements[0], elements[1], elements[2], elements[3], elements[4])
        c = Category(category_code=elements[0])
        c.index = elements[1]
        c.name_kaz = elements[3]
        c.name_rus = elements[2]
        c.name_eng = elements[4].replace("\n", "")
        print(c.name_eng)
        c.save()
        # c.cis_flag = elements[8]
    file.close()


# Start execution here!
if __name__ == "__main__":
    print("Category population script...")
    populate()
