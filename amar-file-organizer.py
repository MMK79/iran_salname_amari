import os
import shutil
import sys
from os import listdir
from os.path import isfile, join


def script_directory():
    directory = os.path.dirname(os.path.abspath(sys.argv[0]))
    return directory


def get_files(download_path=r"/Users/masoudkord/Downloads"):
    onlyfiles = [f for f in listdir(download_path) if isfile(join(download_path, f))]
    return download_path, onlyfiles


def get_file_info(i):
    count = 0
    for j in i:
        if j == ".":
            break
        count += 1
    file_name = i[:count]
    file_format = i[count:]
    return file_name, file_format


def delete_dsstore():
    extra_file = ".DS_Store"
    path, onlyfiles = get_files()
    if extra_file in onlyfiles:
        os.remove(join(path, ".DS_Store"))


def file_rename():
    delete_dsstore()
    download_path, onlyfiles = get_files()
    for i in onlyfiles:
        source = join(download_path, i)
        dest = ""
        count = 0
        for j in i:
            if j == ".":
                break
            elif j in "1234567890":
                dest += j
            count += 1
        file_type = i[count:]
        # print(dest)
        dest = join(download_path, dest + file_type)
        # print(dest)
        # print(count)
        # print(source)
        # print("file type is:", file_type)
        os.rename(source, dest)


def find_missing_years():
    delete_dsstore()
    download_path, onlyfiles = get_files()
    all_years = [i for i in range(1345, 1403)]
    # print(all_years)
    have_years = []
    onlyfiles = [f for f in listdir(download_path) if isfile(join(download_path, f))]
    for i in onlyfiles:
        count = 0
        for j in i:
            if j == ".":
                break
            count += 1
        have_years.append(i[:count])
    have_years = sorted(map(int, have_years))
    # print(have_years)
    missing_years = []
    for i in all_years:
        if i not in have_years:
            missing_years.append(i)
    print(missing_years)


def get_rar_zip_files():
    download_path, onlyfiles = get_files()
    files = []
    for i in onlyfiles:
        _, file_format = get_file_info(i)
        target_format = [".zip", ".rar"]
        if file_format in target_format:
            files.append(i)
    return files


def extract():
    # you need a software to unrar, for mac:
    # brew install --cask rar
    from patoolib import extract_archive

    path, _ = get_files()
    compresed_files = get_rar_zip_files()
    for i in compresed_files:
        # print(join(path, i))
        # print(get_file_info(i)[0])
        # print(join(path, get_file_info(i)[0]))
        src = join(path, i)
        dst = join(path, get_file_info(i)[0])
        extract_archive(src, outdir=dst)
        shutil.move(src, dst)


def create_folder():
    path, onlyfiles = get_files()
    for i in onlyfiles:
        src = join(path, i)
        dst = join(path, get_file_info(i)[0])
        if not os.path.exists(dst):
            os.makedirs(dst)
            shutil.move(src, dst)


delete_dsstore()
print(script_directory())
# _, onlyfiles = get_files()
# for i in onlyfiles:
#     print(get_file_info(i))
