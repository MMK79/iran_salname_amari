import os
import shutil
import sys
from os import listdir
from os.path import exists, isfile, join
import csv
from typing import List, Optional, Tuple

from requests_html import HTMLSession, AsyncHTMLSession
from tqdm.asyncio import tqdm_asyncio
import asyncio
from pprint import pprint


def script_directory() -> str:
    """Return the directory that the script is located in."""
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def check_path(path) -> str:
    """Check and Return path."""
    if path is None:
        return script_directory()
    else:
        return path


def get_files(path=None) -> Tuple[str, List[str], List[str]]:
    """Return (path, files_within_path, folder_within_path)."""
    path = check_path(path)

    files = []
    folders = []

    for name in os.listdir(path):
        full = os.path.join(path, name)
        if os.path.isfile(full):
            files.append(name)
        else:
            folders.append(name)
    return path, files, folders


def get_file_info(full_file_name: str) -> Tuple[str, str]:
    """Get full file name, Return file_name, file_format"""
    return os.path.splitext(full_file_name)


def delete_dsstore(path: Optional[str] = None) -> None:
    """Recursively delete .DS_Store files under path."""
    path = check_path(path)
    for root, _, files in os.walk(path):
        if ".DS_Store" in files:
            os.remove(join(root, ".DS_Store"))


def extract_year_prefix(text: str) -> str:
    """Return leading digits from a filename."""
    year = ""
    for char in text:
        if char.isdigit():
            year += char
        else:
            break
    return year


def file_rename(file_name: str, path: Optional[str] = None) -> None:
    """
    Do change files name within path to a format that only contain their year
    Return None
    """
    path = check_path(path)

    name, ext = get_file_info(file_name)
    new_name = extract_year_prefix(name)

    src = join(path, file_name)
    dst = join(path, new_name + ext)
    if not exists(dst):
        os.rename(src, dst)


def files_rename(path: Optional[str] = None) -> None:
    """
    Change files name within given path.
    Return None.
    """
    path = check_path(path)

    delete_dsstore()

    path, files, _ = get_files(path)
    for file in files:
        file_rename(file, path)


def find_missing_years(path: Optional[str] = None) -> List[int]:
    """Checkout & Return missing report years."""
    path = check_path(path)

    delete_dsstore()

    _, files, folders = get_files(path)
    # list of years -> this range can be scrap from the site for more automation
    valid_year_range = set(range(1345, 1403))
    available_years = set()
    path, files, folders = get_files(path)

    for f in files:
        year = extract_year_prefix(get_file_info(f)[0])
        if year.isdigit():
            available_years.add(int(year))

    for f in folders:
        if f.isdigit():
            available_years.add(int(f))

    missing_years = sorted(valid_year_range - available_years)
    return missing_years


def get_compressed_files(path: Optional[str] = None) -> List[str]:
    path = check_path(path)

    _, files, _ = get_files(path)
    return [f for f in files if get_file_info(f)[1] in (".zip", ".rar")]


def extract(
    compresed_files: List[str], path: Optional[str] = None, remove_archive: bool = False
) -> None:
    """
    Extract each archive into a folder named after its base filename (without ext).
    - compressed_files: list of filenames (not full paths) inside `path`.
    - path: directory where these files live. Defaults to script_directory().
    - remove_archive: if True, delete the archive after extraction; otherwise leave it.
    Uses patoolib.extract_archive (patool must be installed).
    """
    # you need a software to unrar, for mac:
    # brew install --cask rar
    path = check_path(path)
    try:
        from patoolib import extract_archive
    except Exception as e:
        raise RuntimeError(
            "patoolib is required for extract(). Install via `pip install patool`"
        ) from e

    for fname in compresed_files:
        src = join(path, fname)
        base_name, _ = get_file_info(fname)
        dst = join(path, base_name)
        if not exists(src):
            print(f"[extract] skip missing file: {src}")

        os.makedirs(dst, exist_ok=True)

        try:
            extract_archive(src, outdir=dst)
        except Exception as e:
            print(f"[extract] failed to extract {src}: {e}")
            continue

        if remove_archive:
            try:
                os.remove(src)
            except Exception:
                pass
        else:
            archive_store = join(path, "_archives")
            os.makedirs(archive_store, exist_ok=True)
            try:
                shutil.move(src, join(archive_store, fname))
            except Exception as e:
                print(
                    f"[extract] warning: couldn't move {src} into {archive_store}: {e}"
                )


def create_folders_for_files(path: Optional[str] = None) -> None:
    """
    For each file in `path`, create a folder named after the file's base (no ext) and move the file there.
    - safe: if folder exists, file will be moved into it (overwrites if same filename exists in destination).
    - path: directory to operate on; defaults to script_directory().
    """
    path = check_path(path)

    _, files, _ = get_files(path)
    for f in files:
        src = join(path, f)
        base_name, _ = get_file_info(f)
        dst_folder = join(path, base_name)
        try:
            os.makedirs(dst_folder, exist_ok=True)
            shutil.move(src, join(dst_folder, f))
        except Exception as e:
            print(
                f"[create_folders_for_files] failed to move {src} -> {dst_folder}: {e}"
            )
            continue


def scrap_province(
    out_csv: str = "province_code_amar_site.csv", cache: bool = True
) -> str:
    """
    Scrape amar.org.ir province selector and save CSV of (code, persian_name, count)
    Return path to CSV file
    """
    if cache and exists(out_csv):
        return out_csv

    url = "https://amar.org.ir/salnameh-amari/agentType/ViewType/PropertyTypeID/615"
    session = HTMLSession()
    try:
        r = session.get(url, timeout=20)
    except Exception as e:
        raise RuntimeError(f"[scrap_province] network error: {e}") from e

    options = r.html.find("option")  # pyright: ignore
    provinces = []

    for opt in options:
        text = (opt.text or "").strip()
        val = opt.attrs.get("value", "").strip()
        if not text or not val:
            continue
        if "انتخاب" in text or text.isdigit():
            continue

        try:
            cleaned = text.replace("استان", "").strip()
            if "(" in cleaned and ")" in cleaned:
                name_part = cleaned[: cleaned.rfind("(")].strip()
                doc_count_part = cleaned[cleaned.rfind("(") + 1 : cleaned.rfind(")")]
            else:
                name_part = cleaned
                doc_count_part = ""
            provinces.append((val, name_part, doc_count_part))
        except Exception:
            provinces.append((val, text, ""))

    with open(out_csv, mode="w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(
            ["amar.org.ir code", "province persian name", "number of documents"]
        )
        for row in provinces:
            writer.writerow(row)

    return out_csv


def scrap_wikipedia(
    out_csv: str = "wikipedia_provinces_english_data.csv",
    cache: bool = True,
) -> str:
    """
    Scrape English Wikipedia table for Provinces of Iran and save CSV.
    'province', 'abbreviation', 'capital', 'population ', 'area ', 'population density ', 'counties'
    Return path to CSV file.
    If Wikipedia change slightly this will break!
    """

    if cache and exists(out_csv):
        return out_csv

    url = "https://en.wikipedia.org/wiki/Provinces_of_Iran"
    session = HTMLSession()
    try:
        r = session.get(url, timeout=20)
    except Exception as e:
        raise RuntimeError(f"[scrape_wikipedia] network error: {e}") from e

    tables = r.html.find("table.wikitable")  # pyright: ignore
    provinces_table = tables[0]

    header_row = provinces_table.find("tr", first=True)
    headers = [
        h.strip().split("(")[0].strip().lower() for h in header_row.text.split("\n")
    ]
    headers = headers[: len(headers) - 2]
    provinces = []

    # {'province': ['abbreviation', 'capital', 'population ', 'area ', 'population density ', 'counties']}
    rows = provinces_table.find("tr")
    for tr in range(1, len(rows) - 1):
        row = rows[tr].text
        row = row.split("\n")
        row.pop()
        provinces.append(row)

    with open(out_csv, mode="w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(headers)
        for province in provinces:
            writer.writerow(province)
        country_row = ["Whole Country", "Iran", "IR", "0", "0", 0]
        writer.writerow(country_row)

    return out_csv


def get_province_name(
    persian_csv: str = scrap_province(), english_csv: str = scrap_wikipedia()
) -> Tuple[List[str], List[str]]:
    """
    Return: province_name in english and persian list
    """
    persian = []
    english = []

    with open(persian_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            persian.append(row["province persian name"])

    with open(english_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            english.append(row["province"])

    return english, persian


def per_eng_matching(
    out_csv: str = "persian_english_province_name_match.csv", cache: bool = True
) -> str:
    if cache and exists(out_csv):
        return out_csv

    english, persian = get_province_name()
    translation = []
    while persian and english:
        for per in persian:
            if per == "کل کشور":
                translation.append(["کل کشور", "Whole Country"])
                persian.remove(per)
                continue
            for i, j in enumerate(english):
                print(f"{i}: {j}")
            print()
            print(per)
            valid_range = len(english)
            user = int(
                input("which english is a match with your persian? enter the number: ")
            )
            while user > valid_range:
                user = int(input("invalid range, try again: "))

            translation.append([per, english[user]])
            persian.remove(per)
            english.pop(user)
            os.system("printf '\033c'")

    with open(out_csv, mode="w", newline="") as out:
        writer = csv.writer(out, delimiter=",")
        writer.writerow(["Persian", "English"])
        for row in translation:
            writer.writerow(row)
    return out_csv


def merge(
    out_csv: str = "merge.csv",
    persian_csv: str = scrap_province(),
    english_csv: str = scrap_wikipedia(),
    translation_csv: str = per_eng_matching(),
    cache: bool = True,
) -> str:
    if cache and exists(out_csv):
        return out_csv
    with (
        open(persian_csv) as persian,
        open(english_csv) as english,
        open(translation_csv) as translation,
    ):
        persian_reader = csv.DictReader(persian)
        english_reader = csv.DictReader(english)
        translation_reader = csv.DictReader(translation)
        p_l = [i for i in persian_reader]
        e_l = [i for i in english_reader]
        t_l = [i for i in translation_reader]
        m_l = []
        for p in p_l:
            persian_name = p["province persian name"]
            for t in t_l:
                english_name = t.get("English", persian_name)
                for e in e_l:
                    if e["province"] == english_name:
                        m_l.append(e | p)
                        t_l.remove(t)
                        e_l.remove(e)

    with open(out_csv, "w") as out:
        writer = csv.DictWriter(out, fieldnames=m_l[0].keys())
        writer.writeheader()
        for m in m_l:
            writer.writerow(m)
    return out_csv


def generate_urls(
    merge: str = "merge.csv", out_csv: str = "generated_urls.csv", cache: bool = True
) -> str:
    """Create amar.org.ir URL base on the site structure"""
    # https://amar.org.ir/salnameh-amari/agentType/ViewType/PropertyTypeID/615 = 615 = Kole Keshvar
    # 616-646 province range
    # https://amar.org.ir/salnameh-amari/agentType/ViewSearch/CustomFieldIDs/65/SearchValues/1394/PropertyTypeID/618
    # if cache and exists(csvfile):
    #     return csvfile
    if cache and exists(out_csv):
        return out_csv

    year = None
    urls = []
    with open(merge) as f:
        reader = csv.DictReader(f)
        for row in reader:
            code, eng_name = row["amar.org.ir code"], row["province"]
            for i in range(1345, 1403):
                year = i
                url = f"https://amar.org.ir/salnameh-amari/agentType/ViewSearch/CustomFieldIDs/65/SearchValues/{year}/PropertyTypeID/{code}"
                urls.append([eng_name, str(year), url])

    with open(out_csv, mode="w") as out:
        writer = csv.writer(out)
        writer.writerow(["province", "year", "url"])
        for e in urls:
            writer.writerow(e)
    return out_csv


async def _fetch_with_retries(
    session: AsyncHTMLSession, url: str, retries: int = 2, timeout: int = 15
):
    last_exc = None
    for attempt in range(retries + 1):
        try:
            r = await session.get(url, timeout=timeout)
            return r.status_code, r, None
        except Exception as e:
            last_exc = e
            await asyncio.sleep(1 + attempt * 0.5)
        return None, None, last_exc


async def check_url_availability_async(
    input_csv: str = "generated_urls.csv",
    output_csv: str = "url_availability_async.csv",
    concurrency: int = 20,
    fail_message: str = "هيچ نتيجه اي مطابق با معيارهاي شما يافت نشد.",
    cache: bool = True,
):
    if not exists(input_csv):
        raise FileNotFoundError(f"{input_csv} not found. Run generate_urls() first.")

    if cache and exists(output_csv):
        with open(output_csv) as outf, open(input_csv) as inf:
            in_reader = csv.reader(inf)
            out_reader = csv.reader(outf)
            if len(list(out_reader)) == len(list(in_reader)):
                return output_csv

    rows = []
    with open(input_csv) as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            rows.append(row)

    sem = asyncio.Semaphore(concurrency)
    session = AsyncHTMLSession()

    async def worker(row):
        async with sem:
            province, year, url = row
            status_code, response, exc = await _fetch_with_retries(session, url)
            if exc is not None:
                return [province, year, url, f"error:{exc}"]
            if status_code != 200:
                return [province, year, url, str(status_code)]
            try:
                box = response.html.find(
                    "div.DnnModule.DnnModule-PropertyAgent.DnnModule-6200"
                )
                result_text = box.text.split("\n")[0]
                if result_text.strip() == fail_message:
                    return [province, year, url, "0"]
                else:
                    return [province, year, url, "1"]
            except Exception as e:
                return [province, year, url, f"parse_exception:{e}"]

    tasks = [asyncio.create_task(worker(r)) for r in rows]
    results = []
    for fut in tqdm_asyncio(
        asyncio.as_completed(tasks), total=len(tasks), desc="Checking URLs"
    ):
        res = await fut
        results.append(res)

    # write output with header
    with open(output_csv, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["Province", "Year", "URL", "Status"])
        for r in results:
            writer.writerow(r)

    return output_csv


asyncio.run(check_url_availability_async())


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
    just_number_int = {k: f"{len(v)}/58" for k, v in missing_year_dic.items()}
    pprint(just_number)


path = r"/Volumes/MASOUD/Amar-Salname/Keshvari/"
