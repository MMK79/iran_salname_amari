from etl.provinces import CURRENT, match_province


def test_31_current():
    assert len(CURRENT) == 31
    assert len({p.iso for p in CURRENT}) == 31


def test_aliases():
    assert match_province("آذربايجان شرقي ............") == "AZS"
    assert match_province("كهگيلويه و بويراحمد") == "KBA"
    assert match_province("كل كشور") == "IRN"
    assert match_province("خراسان‌") == "KHO"
    assert match_province("خراسان رضوي") == "KHR"
    assert match_province("پزشكي") is None
