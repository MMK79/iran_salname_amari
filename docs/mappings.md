# Term mapping (source wording -> normalised dimension)

Generated from `etl/terms.py` (`RULES`), also loaded into the `term_map` table. Matching is on
`norm()`-ed text with spaces removed; within a dimension the first matching rule wins, so the
order below is significant. `domain` scopes a rule to K-12 (`k12`) or higher education (`he`);
a table's domain is decided once from its title (`classify_domain`), which is what keeps the
two levels apart. The source wording is kept next to every normalised value (`level_source`,
`degree_level_source`, `row_label`, `col_header`).

| # | dim | value | pattern | how | domain | note |
|---|---|---|---|---|---|---|
| 0 | gender | total | جمع | exact | any |  |
| 1 | gender | total | مرد و زن | exact | any |  |
| 2 | gender | total | دختر و پسر | exact | any |  |
| 3 | gender | total | پسر و دختر | exact | any |  |
| 4 | gender | total | کل | exact | any |  |
| 5 | gender | total | جمع کل | exact | any |  |
| 6 | gender | male | مرد | exact | any |  |
| 7 | gender | male | پسر | exact | any |  |
| 8 | gender | male | مردان | exact | any |  |
| 9 | gender | male | پسران | exact | any |  |
| 10 | gender | female | زن | exact | any |  |
| 11 | gender | female | دختر | exact | any |  |
| 12 | gender | female | زنان | exact | any |  |
| 13 | gender | female | دختران | exact | any |  |
| 14 | area | urban | نقاط شهری | exact | any |  |
| 15 | area | urban | شهری | exact | any |  |
| 16 | area | rural | نقاط روستایی | exact | any |  |
| 17 | area | rural | روستایی | exact | any |  |
| 18 | area | nomadic | عشایری | exact | any |  |
| 19 | sector | public | دولتی | exact | k12 |  |
| 20 | sector | nonpublic | غیر دولتی | exact | k12 |  |
| 21 | sector | nonpublic | غیردولتی | exact | k12 |  |
| 22 | sector | nonpublic | غیر انتفاعی | exact | k12 |  |
| 23 | sector | nonpublic | غیرانتفاعی | exact | k12 |  |
| 24 | level | pre_university | پیش دانشگاهی | contains | k12 |  |
| 25 | level | preschool | پیش دبستانی | contains | k12 |  |
| 26 | level | preschool | آمادگی | contains | k12 |  |
| 27 | level | preschool | کودکستان | contains | k12 |  |
| 28 | level | lower_secondary | دوره اول متوسطه | contains | k12 | new 6-3-3 system (from 1391-92): grades 7-9 |
| 29 | level | lower_secondary | متوسطه اول | contains | k12 | new 6-3-3 system: grades 7-9 |
| 30 | level | upper_secondary | دوره دوم متوسطه | contains | k12 | new system: grades 10-12 |
| 31 | level | lower_secondary | متوسطه دوره اول | contains | k12 | 1393-94 yearbooks' word order |
| 32 | level | upper_secondary | متوسطه دوره دوم | contains | k12 | 1393-94 yearbooks' word order |
| 33 | level | upper_secondary | متوسطه دوم | contains | k12 | new system: grades 10-12 |
| 34 | level | lower_secondary | راهنمایی | contains | k12 | old 5-3-4 system: guidance school, grades 6-8 |
| 35 | level | lower_secondary | عمومی شبانه | contains | k12 | evening guidance (1370s) |
| 36 | level | primary | ابتدایی | contains | k12 | 5 grades until 1390-91, 6 grades from 1391-92 |
| 37 | level | primary | دبستان | contains | k12 |  |
| 38 | level | upper_secondary | متوسطه | contains | k12 | old system high school (3 grades + pre-university) |
| 39 | level | upper_secondary | دبیرستان | contains | k12 |  |
| 40 | level | upper_secondary | هنرستان | contains | k12 |  |
| 41 | level | upper_secondary | کاردانش | contains | k12 |  |
| 42 | level | upper_secondary | آموزش فنی | contains | k12 |  |
| 43 | level | upper_secondary | آموزش حرفه ای | contains | k12 |  |
| 44 | level | upper_secondary | تکمیلی شبانه | contains | k12 |  |
| 45 | level | all_levels | کلیه دوره | contains | k12 |  |
| 46 | level | all_levels | دوره های تحصیلی | contains | k12 |  |
| 47 | level | all_levels | دوره های مختلف | contains | k12 |  |
| 48 | programme | special_needs | استثنایی | contains | k12 |  |
| 49 | programme | adult | بزرگسال | contains | k12 |  |
| 50 | programme | adult | شبانه | contains | k12 |  |
| 51 | programme | adult | متفرقه | contains | k12 |  |
| 52 | branch | theoretical | نظری | contains | k12 |  |
| 53 | branch | theoretical | متوسطه عمومی | contains | k12 |  |
| 54 | branch | technical_vocational | فنی و حرفه ای | contains | k12 |  |
| 55 | branch | technical | آموزش فنی | contains | k12 |  |
| 56 | branch | vocational | آموزش حرفه ای | contains | k12 |  |
| 57 | branch | kardanesh | کاردانش | contains | k12 |  |
| 58 | branch | kardanesh | کار و دانش | contains | k12 |  |
| 59 | metric | teachers | معلم | exact | k12 |  |
| 60 | metric | teachers | معلمان | exact | k12 |  |
| 61 | metric | teachers | گروه معلم | exact | k12 |  |
| 62 | metric | mgmt_quality_staff | مدیریت و کیفیت بخشی | contains | k12 | from 1394: non-teacher educational staff |
| 63 | metric | clerical_admin_staff | دفتری و اداری | exact | k12 |  |
| 64 | metric | educational_staff | آموزشی | exact | k12 | before 1394: 'educational staff' (teachers + principals etc.) |
| 65 | metric | staff_permanent_contract | رسمی و پیمانی | contains | k12 | 1370s: educational+clerical staff, permanent/contract |
| 66 | metric | staff_hourly | حق التدریسی | contains | k12 | 1370s: hourly-paid/contract |
| 67 | metric | educational_staff | کارکنان آموزشی | exact | k12 |  |
| 68 | metric | students | دانش آموز | contains | k12 |  |
| 69 | metric | students | نوآموز | contains | k12 |  |
| 70 | metric | students | کودکان | contains | k12 |  |
| 71 | metric | schools | آموزشگاه | contains | k12 |  |
| 72 | metric | schools | مدرسه | contains | k12 |  |
| 73 | metric | schools | مدارس | exact | k12 |  |
| 74 | metric | classes | کلاس | contains | k12 |  |
| 75 | metric | graduates | فارغ التحصیل | contains | k12 |  |
| 76 | metric | passed | قبول شد | contains | k12 |  |
| 77 | branch | math_physics | ریاضی فیزیک | contains | k12 |  |
| 78 | branch | experimental_sciences | علوم تجربی | contains | k12 |  |
| 79 | branch | humanities | علوم انسانی | contains | k12 |  |
| 80 | branch | islamic_studies | معارف اسلامی | contains | k12 |  |
| 81 | branch | kardanesh | کار دانش | contains | k12 |  |
| 82 | staffgroup | staff | کارکنان | contains | any |  |
| 83 | staffgroup | facilities | امکانات | contains | any |  |
| 84 | staffgroup | faculty_group | هیات علمی | exact | he |  |
| 85 | employment | fulltime_and_hourly | تمام وقت و حق التدریس | contains | he |  |
| 86 | employment | fulltime_and_hourly | تمام وقت و پاره وقت | contains | he |  |
| 87 | employment | fulltime | تمام وقت | contains | he |  |
| 88 | employment | hourly | حق التدریس | contains | he |  |
| 89 | employment | hourly | پاره وقت | contains | he |  |
| 90 | degree_level | master | کارشناسی ارشد | contains | he |  |
| 91 | degree_level | master | فوق لیسانس | contains | he |  |
| 92 | degree_level | professional_doctorate | دکترای حرفه ای | contains | he |  |
| 93 | degree_level | professional_doctorate | دکتری حرفه ای | contains | he |  |
| 94 | degree_level | professional_doctorate | دکترای عمومی | contains | he |  |
| 95 | degree_level | phd | دکترای تخصصی | contains | he |  |
| 96 | degree_level | phd | دکتری تخصصی | contains | he |  |
| 97 | degree_level | phd | ph.d | contains | he |  |
| 98 | degree_level | associate | کاردانی | contains | he |  |
| 99 | degree_level | associate | فوق دیپلم | contains | he |  |
| 100 | degree_level | bachelor | کارشناسی | contains | he |  |
| 101 | degree_level | bachelor | لیسانس | contains | he |  |
| 102 | degree_level | doctorate_unspecified | دکترا | contains | he | older yearbooks do not split professional/PhD |
| 103 | degree_level | doctorate_unspecified | دکتری | contains | he |  |
| 104 | university_type | payame_noor | پیام نور | contains | he |  |
| 105 | university_type | azad | آزاد اسلامی | contains | he |  |
| 106 | university_type | azad | دانشگاه آزاد | contains | he |  |
| 107 | university_type | applied_science | علمی کاربردی | contains | he |  |
| 108 | university_type | applied_science | علمی و کاربردی | contains | he |  |
| 109 | university_type | technical_vocational_univ | فنی و حرفه ای | contains | he |  |
| 110 | university_type | farhangian_teacher_training | فرهنگیان | contains | he |  |
| 111 | university_type | farhangian_teacher_training | تربیت معلم | contains | he |  |
| 112 | university_type | public_mohme | وزارت بهداشت | contains | he | medical universities |
| 113 | university_type | public_msrt | وزارت علوم | contains | he |  |
| 114 | university_type | public_msrt | وزارت فرهنگ و آموزش عالی | contains | he |  |
| 115 | university_type | public_other | سایر دستگاه | contains | he |  |
| 116 | university_type | private_nonprofit | غیر انتفاعی | contains | he |  |
| 117 | university_type | private_nonprofit | غیرانتفاعی | contains | he |  |
| 118 | university_type | public_all | دولتی | exact | he |  |
| 119 | field_group | medical | پزشکی | exact | he |  |
| 120 | field_group | medical | علوم پزشکی | exact | he |  |
| 121 | field_group | humanities | علوم انسانی | exact | he |  |
| 122 | field_group | basic_sciences | علوم پایه | exact | he |  |
| 123 | field_group | engineering | فنی و مهندسی | exact | he |  |
| 124 | field_group | engineering | فنی مهندسی | exact | he |  |
| 125 | field_group | agri_vet | کشاورزی و دامپزشکی | exact | he |  |
| 126 | field_group | agriculture | کشاورزی | exact | he |  |
| 127 | field_group | veterinary | دامپزشکی | exact | he |  |
| 128 | field_group | art | هنر | exact | he |  |
| 129 | rank | instructor_assistant | مربی آموزشیار | exact | he |  |
| 130 | rank | professor | استاد | exact | he |  |
| 131 | rank | associate_professor | دانشیار | exact | he |  |
| 132 | rank | assistant_professor | استادیار | exact | he |  |
| 133 | rank | instructor | مربی | exact | he |  |
| 134 | rank | non_faculty | غیر هیات علمی | contains | he | full-time instructors who are not faculty members |
| 135 | metric | new_entrants | ثبت نام شدگان جدید | contains | he |  |
| 136 | metric | new_entrants | پذیرفته شد | contains | he |  |
| 137 | metric | new_entrants | پذیرفه شد | contains | he | typo in 1353 source |
| 138 | metric | graduates | دانش آموخت | contains | he |  |
| 139 | metric | graduates | فارغ التحصیل | contains | he |  |
| 140 | metric | academic_staff | آموزشگران | contains | he | academic staff (faculty + non-faculty instructors); see employment dim |
| 141 | metric | academic_staff | هیات علمی | contains | he |  |
| 142 | metric | academic_staff | استادان | contains | he |  |
| 143 | metric | academic_staff | کادر آموزشی | contains | he |  |
| 144 | metric | academic_staff | کارکنان آموزشی | contains | he |  |
| 145 | metric | students | دانشجو | contains | he |  |
| 146 | metric | institutions | تعداد دانشگاه | contains | he |  |
| 147 | metric | institutions | مراکز آموزش عالی | exact | he |  |

## Normalised K-12 levels

| level | meaning | notes |
|---|---|---|
| preschool | پیش‌دبستانی / آمادگی / کودکستان | 1 year before primary |
| primary | ابتدایی / دبستان | 5 grades until 1390-91, 6 grades from 1391-92 |
| lower_secondary | راهنمایی تحصیلی (old, grades 6-8) / دوره اول متوسطه (new, grades 7-9) | `school_system` column tells which; 1391-1393 is the transition (guidance school phased out) |
| upper_secondary | متوسطه (old, 3 grades, incl. نظری/فنی و حرفه‌ای/کاردانش) / دوره دوم متوسطه (new, grades 10-12) | pre-university became grade 12 in the new system |
| pre_university | پیش‌دانشگاهی | old system only (to ~1397) |
| all_levels | table or row covers all levels | never summed with the per-level rows |

`programme` (regular / adult / special_needs) is kept separate from `level`.

## Normalised higher-education degree levels

| degree_level | Persian | note |
|---|---|---|
| associate | کاردانی (فوق دیپلم) | |
| bachelor | کارشناسی (لیسانس) | |
| master | کارشناسی ارشد (فوق لیسانس) | |
| professional_doctorate | دکترای حرفه‌ای (e.g. MD, DVM, PharmD) | |
| phd | دکترای تخصصی | |
| doctorate_unspecified | دکترا | older tables that do not split the two |

## University types

| university_type | Persian | note |
|---|---|---|
| all_reported | the table's own total | coverage in `coverage` (incl_azad / excl_uast ...) |
| excl_azad | total *excluding* Islamic Azad University | footnote «به استثنای دانشگاه آزاد», yearbooks <= 1392 |
| azad | دانشگاه آزاد اسلامی | |
| payame_noor | دانشگاه پیام نور | |
| applied_science | دانشگاه جامع علمی-کاربردی (UAST) | |
| technical_vocational_univ | دانشگاه فنی و حرفه‌ای | |
| farhangian_teacher_training | دانشگاه فرهنگیان (teacher-training) | |
| public_msrt | universities of the Ministry of Science (MSRT) | |
| public_mohme | universities of the Ministry of Health (medical) | |
| public_other | other executive bodies | |
| private_nonprofit | غیردولتی-غیرانتفاعی | |
