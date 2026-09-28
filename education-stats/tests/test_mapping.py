from etl.coverage import flags, markers, parse_notes
from etl.terms import DIMS_HE, DIMS_K12, classify_domain, dims_of_header, dims_of_row_label, match


def test_domain_separation():
    assert classify_domain("۱۰-۱۷- دانش‌آموزان، كاركنان و امكانات آموزشي دوره ابتدايي") == "k12"
    assert classify_domain("14-15- دانش‌آموزان و امكانات آموزشي(1) دوره پيش‌دانشگاهي") == "k12"  # not HE!
    assert classify_domain("۲۸-۱۷- دانشجويان دوره‌هاي مختلف تحصيلي موسسات آموزش عالي") == "he"
    assert classify_domain("جمعيت ۶ ساله و بيش‌تر، تعداد باسوادان") == "other"


def test_rules_are_domain_scoped():
    # a higher-ed degree term is never read as a K-12 level and vice versa
    assert match("degree_level", "كارشناسي", "k12") is None
    assert match("level", "ابتدايي", "he") is None


def test_degree_order():
    assert dims_of_header("كارشناسي ارشد (فوق ليسانس) > زن", "he", DIMS_HE)["degree_level"][0] == "master"
    assert dims_of_header("كارشناسي (ليسانس) > مرد", "he", DIMS_HE)["degree_level"][0] == "bachelor"
    assert dims_of_header("دكتراي حرفه‌اي > مرد و زن", "he", DIMS_HE)["degree_level"][0] == "professional_doctorate"
    assert dims_of_header("دكتراي تخصصي > مرد و زن", "he", DIMS_HE)["degree_level"][0] == "phd"


def test_k12_levels_and_unmatched():
    assert dims_of_row_label("دوره اول متوسطه", "k12", DIMS_K12)["level"][0] == "lower_secondary"
    assert dims_of_row_label("راهنمايي تحصيلي", "k12", DIMS_K12)["level"][0] == "lower_secondary"
    d = dims_of_header("پايه دهم > پسر", "k12", DIMS_K12)
    assert "unmatched" in d  # grade columns are never read as a total
    assert dims_of_header("كاركنان آموزشي‌، دفتري و اداري > آموزشي", "k12", DIMS_K12)["metric"][0] == "educational_staff"


def test_gender_exact_not_substring():
    assert "gender" not in dims_of_row_label("زنجان", "k12", DIMS_K12)


def test_coverage_flags():
    assert flags(["به استثناي دانشگاه آزاد اسلامي."], 1386) == {"excl_azad"}
    assert flags(["آمار دانشگاه آزاد را نيز شامل مي‌شود."], 1398) == {"incl_azad"}
    assert "excl_uast" in flags(["آمار دانشگاه جامع علمي کاربردي را شامل نمي‌شود."], 1398)
    nums, _ = parse_notes(["1) الف", "ماخذ - وزارت", "2) ب"])
    assert nums == {1: "الف", 2: "ب"}
    assert markers("كاركنان آموزشي(1و2)") == {1, 2}
