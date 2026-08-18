import datetime
import os
import shutil
import time


def remove_webdriver_cache():
    tmp_directory = "/tmp";
    
    for dir_obj in os.listdir(tmp_directory):
        cache_dir_path = os.path.join(tmp_directory, dir_obj)

        if os.path.isdir(cache_dir_path) and dir_obj.startswith(".com.google.Chrome."):
            # creation_date = datetime.datetime.fromtimestamp(os.path.getctime(cache_dir_path))
            # current_date = datetime.datetime.now()

            # time_difference = (current_date - creation_date).days

            # if time_difference >= 25:
            print(f"[+] Removing {cache_dir_path}")
            shutil.rmtree(cache_dir_path)
            time.sleep(1)

remove_webdriver_cache()
