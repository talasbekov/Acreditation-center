import os
import shutil
from distutils.dir_util import copy_tree

from django.http import HttpResponse


def download_photos_async(event_id):
    if os.path.exists("event_" + str(event_id) + ".zip"):
        os.remove("event_" + str(event_id) + ".zip")
        print("The file has been deleted successfully")
    else:
        print("The file does not exist!")
    dir_name = "media/event_" + str(event_id)
    print("event")
    if not os.path.isdir(dir_name):
        print("error! no dir")
        return HttpResponse("No photos uploaded yet")
    output_filename = "output/event_" + str(event_id) + "/event_" + str(event_id)
    print("output")
    if os.path.exists(output_filename):
        # checking whether the folder is empty or not
        if len(os.listdir(output_filename)) == 0:
            # removing the file using the os.remove() method
            os.rmdir(output_filename)
        else:
            # messaging saying folder not empty
            print("Folder is not empty")
    else:
        # file not found message
        print("File not found in the directory")
    copy_tree(dir_name, output_filename)
    print("copied")
    zip_address = "output/event_" + str(event_id)
    file = open(zip_address + "/test.txt", "w")
    file.close()
    archieve = "event_" + str(event_id)
    print("archieve name")
    shutil.make_archive(archieve, "zip", zip_address)
    print("zip made")
