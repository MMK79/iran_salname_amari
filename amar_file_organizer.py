import copy
import os
import shutil
import sys
from os import listdir
from os.path import exists, isfile, join
import json
import csv
from copy import deepcopy

from requests_html import HTMLSession


def script_directory():
    """Show where script is located"""
    directory = os.path.dirname(os.path.abspath(sys.argv[0]))
    return directory


def get_files(path=r"/Volumes/MASOUD/Salname"):
    """Return ( path, files, folder ) within 'path'"""
    onlyfiles = [f for f in listdir(path) if isfile(join(path, f))]
    onlyfolders = set(listdir(path)) - set(onlyfiles)
    return path, onlyfiles, onlyfolders


def get_file_info(i):
    """Return file name and file format for given full file name"""
    count = 0
    for j in i:
        if j == ".":
            break
        count += 1
    file_name = i[:count]
    file_format = i[count:]
    return file_name, file_format


def delete_dsstore():
    """Delete .DS_Store File"""
    extra_file = ".DS_Store"
    path, onlyfiles, _ = get_files()
    if extra_file in onlyfiles:
        os.remove(join(path, ".DS_Store"))


def file_rename():
    """Change all files name within path to a format that only contain their year"""
    delete_dsstore()
    download_path, onlyfiles, _ = get_files()
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
    """Checkout which year missing report"""
    delete_dsstore()
    download_path, onlyfiles, _ = get_files()
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
    _, onlyfiles, _ = get_files()
    files = []
    for i in onlyfiles:
        _, file_format = get_file_info(i)
        target_format = [".zip", ".rar"]
        if file_format in target_format:
            files.append(i)
    return files


def extract():
    """Extract files within the path to folder with their own name (year of report) and move the main file to the folder too"""
    # you need a software to unrar, for mac:
    # brew install --cask rar
    from patoolib import extract_archive

    path, _, _ = get_files()
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
    """Create folder for pdf files with their name and move them to it"""
    path, onlyfiles, _ = get_files()
    for i in onlyfiles:
        src = join(path, i)
        dst = join(path, get_file_info(i)[0])
        if not os.path.exists(dst):
            os.makedirs(dst)
            shutil.move(src, dst)


def create_url():
    """Create amar.org.ir URL base on the site structure"""
    # https://amar.org.ir/salnameh-amari/agentType/ViewType/PropertyTypeID/615 = 615 = Kole Keshvar
    # 616-646 province range
    # https://amar.org.ir/salnameh-amari/agentType/ViewSearch/CustomFieldIDs/65/SearchValues/1394/PropertyTypeID/618
    from pprint import pprint

    year = None
    province = None
    for i in range(616, 647):
        city_i_code_urls = []
        for j in range(1345, 1403):
            year = i
            province = j
            base = f"https://amar.org.ir/salnameh-amari/agentType/ViewSearch/CustomFieldIDs/65/SearchValues/{year}/PropertyTypeID/{province}"
            city_i_code_urls.append(base)
        print(len(city_i_code_urls))
        pprint(city_i_code_urls)
        break


def scrap_province():
    """Return: csvfile with format:
    province_code_amar_site, province_persian_name, number_of_documents"""
    csvfile_name = "province_code_amar_site.csv"
    if exists(csvfile_name):
        return csvfile_name

    url = "https://amar.org.ir/salnameh-amari/agentType/ViewType/PropertyTypeID/615"
    session = HTMLSession()
    r = session.get(url)
    html = r.html
    options = html.find("option")
    provinces_site_code = {}

    for option in options:
        problematic_selections = ["<انتخاب دسته‌بندی>", "کل کشور (523)"]
        year_selection = "<انتخاب سال>"
        if option.text == year_selection:
            break
        elif option.text not in problematic_selections:
            provinces_site_code[option.attrs["value"]] = option.text

    # clean province word from data
    for k, v in provinces_site_code.items():
        v_split = v.split(" ")
        v_split.remove("استان")
        new_v = " ".join(v_split)
        new_v = new_v.split("(")
        new_v[1] = new_v[1].replace(")", "")
        provinces_site_code[k] = new_v

    with open(csvfile_name, mode="w", newline="") as csvfile:
        account = csv.writer(csvfile, delimiter=",")
        account.writerow(
            ["amar.org.ir code", "province persian name", "number of documents"]
        )
        for k, v in provinces_site_code.items():
            account.writerow([k, v[0], v[1]])
        return csvfile_name


def scrap_wikipedia():
    """Return csvfile of wikipedia table about provinces:
    'province', 'abbreviation', 'capital', 'population ', 'area ', 'population density ', 'counties'
    """

    csvfile_name = "wikipedia_provinces_english_data.csv"
    if exists(csvfile_name):
        return csvfile_name

    url = "https://en.wikipedia.org/wiki/Provinces_of_Iran"
    session = HTMLSession()
    r = session.get(url)
    html = r.html
    test = html.find("main", first=True)
    tables = test.find("table")
    provinces_table = tables[2]
    provinces_table_headers = provinces_table.find("tr", first=True)
    headers = provinces_table_headers.text.lower().split("\n")
    headers_list = []
    provinces = {}
    for header in headers[0 : len(headers) - 2]:
        header = header.split("(")
        header = "".join(header[0])
        headers_list.append(header)

    # {'province': ['abbreviation', 'capital', 'population ', 'area ', 'population density ', 'counties']}
    rows = provinces_table.find("tr")
    for i in range(1, len(rows) - 1):
        text = rows[i].text
        text = text.split("\n")
        text.pop()
        provinces[text[0]] = text[1:]

    with open(csvfile_name, mode="w", newline="") as csvfile:
        account = csv.writer(csvfile, delimiter=",")
        account.writerow(headers_list)
        for k, v in provinces.items():
            account.writerow([k] + v)
    return csvfile_name


def get_province_name():
    """
    Return: province_name in english and persian list
    """
    province_persian = scrap_province()
    province_english = scrap_wikipedia()
    province_persian_names = []
    province_english_names = []
    with open(province_english, "r") as english_csv_file:
        rows = csv.reader(english_csv_file, delimiter=",")
        for row in rows:
            province_english_names.append(row[0])
        province_english_names.reverse()
        province_english_names.pop()
        province_english_names.reverse()

    with open(province_persian, "r") as persian_csv_file:
        rows = csv.reader(persian_csv_file, delimiter=",")
        for row in rows:
            province_persian_names.append(row[1])
        province_persian_names.reverse()
        province_persian_names.pop()
        province_persian_names.reverse()

    return province_english_names, province_persian_names


def matching_game():
    csvfile_name = "persian_english_province_name_match.csv"
    if exists(csvfile_name):
        return csvfile_name

    count = 0
    english, persian = get_province_name()
    translation = {}
    persian_tracker = copy.deepcopy(persian)
    for i in persian:
        print(f"persian_before : {len(persian_tracker)}")
        print(f"english_before : {len(english)}")
        for j in range(len(english)):
            print(f"{j}: {english[j]}")
        print()
        print(i)
        user = int(
            input("which english is a match with your persian? enter the number:")
        )
        translation[i] = english[user]
        english.pop(user)
        persian_tracker.remove(i)
        print(f"persian_after : {len(persian_tracker)}")
        print(f"english_after : {len(english)}")
        print(translation)

    with open(csvfile_name, mode="w", newline="") as csvfile:
        account = csv.writer(csvfile, delimiter=",")
        account.writerow(["Persian", "English"])
        for k, v in translation.items():
            account.writerow([k, v])
    return csvfile_name


# scrap_province()
# scrap_wikipedia()
# matching_game()
