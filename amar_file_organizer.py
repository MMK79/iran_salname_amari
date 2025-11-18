import copy
import os
import shutil
import sys
from os import listdir
from os.path import exists, isfile, join
import csv
from copy import deepcopy

from requests_html import HTMLSession, AsyncHTMLSession
from tqdm import tqdm
from pprint import pprint


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


def code_matching_english():
    translate_file_name = matching_game()
    persian_file = scrap_province()
    with (
        open(translate_file_name, mode="r") as translate,
        open(persian_file, mode="r") as persian,
    ):
        # load persian data
        persian_reader = csv.reader(persian)
        persian = {}
        i_counter = 0
        for i in persian_reader:
            if i_counter == 0:
                i_counter += 1
            else:
                persian[i[0]] = i[1]
                i_counter += 1

        # load english data
        english = {}
        translate_reader = csv.reader(translate)
        j_counter = 0
        for j in translate_reader:
            if j_counter == 0:
                j_counter += 1
            else:
                english[j[0]] = j[1]
                j_counter += 1

        bridge = {}
        for k, v in persian.items():
            bridge[k] = english[v]

        return bridge


def generate_urls():
    """Create amar.org.ir URL base on the site structure"""
    # https://amar.org.ir/salnameh-amari/agentType/ViewType/PropertyTypeID/615 = 615 = Kole Keshvar
    # 616-646 province range
    # https://amar.org.ir/salnameh-amari/agentType/ViewSearch/CustomFieldIDs/65/SearchValues/1394/PropertyTypeID/618
    year = None
    province = None
    bridge = code_matching_english()
    csvfile_name = "generated_urls.csv"
    if exists(csvfile_name):
        return csvfile_name

    urls = {}
    for k, v in bridge.items():
        for j in range(1345, 1403):
            year = j
            province = int(k)
            base = f"https://amar.org.ir/salnameh-amari/agentType/ViewSearch/CustomFieldIDs/65/SearchValues/{year}/PropertyTypeID/{province}"
            urls[v, year] = base

    with open(csvfile_name, mode="w", newline="") as csvfile:
        account = csv.writer(csvfile, delimiter=",")
        account.writerow(["Province Name", "Year", "URL"])
        for k, v in urls.items():
            account.writerow([k[0], k[1], v])
    return csvfile_name


def check_url_availability():
    # add logging
    # add async
    # break 1800 url into smaller pieces and smaller csv then concatenate csvs
    csvfile_name = "url_availability.csv"
    urls_csvfile = generate_urls()
    if exists(csvfile_name):
        with open(csvfile_name, "r") as main, open(urls_csvfile, "r") as reference:
            reference_reader = csv.reader(reference)
            main_reader = csv.reader(main)
            row_count_reference = len(list(reference_reader))
            row_count_main = len(list(main_reader))
            if row_count_reference == row_count_main:
                return csvfile_name

    with (
        open(urls_csvfile, newline="") as urls,
        open(csvfile_name, mode="w") as csvfile,
    ):
        reader = csv.reader(urls)
        writer = csv.writer(csvfile, delimiter=",")
        count = 0
        header = None
        # 1798 url = 30 min run
        # do it async
        for url in tqdm(reader):
            if count == 0:
                header = url + ["Status"]
                writer.writerow(header)
                count += 1
            else:
                single_url = url[2]
                session = HTMLSession()
                r = session.get(single_url)
                try:
                    if r.status_code == 200:
                        html = r.html
                        fail_massage = "هيچ نتيجه اي مطابق با معيارهاي شما يافت نشد."
                        response = html.find(
                            "div.DnnModule.DnnModule-PropertyAgent.DnnModule-6200",
                            first=True,
                        ).text.split("\n")[0]
                        if response == fail_massage:
                            url = url + ["0"]
                            writer.writerow(url)
                        else:
                            url = url + ["1"]
                            writer.writerow(url)
                    else:
                        url = url + [str(r.status_code)]
                        writer.writerow(url)
                    return csvfile_name
                except Exception as e:
                    url = url + [str(e)]
                    writer.writerow(url)


def missing_year_checker():
    delete_dsstore()
    all_years = [i for i in range(1345, 1403)]
    csvfile = check_url_availability()
    missing_year_counter = 0
    eng, _ = get_province_name()
    with open(csvfile, mode="r") as file:
        rows = csv.reader(file)
        counter = 0
        missing_year_dic = {k: [] for k in eng}
        for row in rows:
            if counter == 0:
                counter += 1
            else:
                if row[-1] == "0":
                    missing_year_dic[row[0]].append(row[1])
                    missing_year_counter += 1
                    counter += 1
                else:
                    counter += 1
    print(missing_year_counter)
    pprint(missing_year_dic)
    just_number = {k: f"{len(v)}/58" for k, v in missing_year_dic.items()}
    pprint(just_number)


# scrap_province()
# scrap_wikipedia()
# matching_game()
# code_matching_english()
# generate_urls()
# check_url_availability()
missing_year_checker()
