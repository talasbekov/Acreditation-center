import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eventproject.settings")

import django

django.setup()
from directories.models import DocumentType

# For an explanation of what is going on here, please refer to the TwD book.


def populate():
    file = open("docs.csv", "r")
    lines = file.readlines()
    for line in lines:
        line = line.replace('"', "")
        elements = line.split(";")
        print(elements[1], elements[2], elements[3], elements[4], elements[5])
        d = DocumentType()
        d.doc_code = elements[1]
        d.name_kaz = elements[4]
        d.name_rus = elements[3]
        d.name_eng = elements[5]
        d.save()
        print(d.name_rus, d.name_eng, d.name_kaz, d.doc_code)
    file.close()


# Start execution here!
if __name__ == "__main__":
    print("Document population script...")
    populate()
