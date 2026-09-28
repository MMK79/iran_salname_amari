from etl.normalize import norm, parse_academic_year, to_number


def test_digits_and_separators():
    assert to_number("۱٬۲۳۴") == 1234
    assert to_number("٥٦٧") == 567
    assert to_number("12,345") == 12345
    assert to_number("886(1)") == 886


def test_missing():
    for s in ["-", "…", "×", "××", "", "000"]:
        assert to_number(s) is None


def test_decimal_rtl_swap():
    assert to_number("7/28") == 28.7  # docx stores 28.7 as 7/28
    assert to_number("28/7", slash_swapped=False) == 28.7


def test_yeh_kaf_variants():
    assert norm("كاركنان آموزشي") == norm("کارکنان آموزشی")
    assert norm("دانش‌آموز") == norm("دانش آموز")
    assert norm("هيأت علمي") == norm("هیئت علمی")


def test_academic_year():
    assert parse_academic_year("99-1398") == 1398
    assert parse_academic_year("1398-1399") == 1398
    assert parse_academic_year("81-1380(2)") == 1380
    assert parse_academic_year("66-1365..") == 1365
    assert parse_academic_year("۱۳۹۸-۱۳۹۹") == 1398
    assert parse_academic_year("تهران") is None
    assert parse_academic_year("آبان 1375") is None
