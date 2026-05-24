#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为天津、河北、山西、河南、江西、福建、安徽35所高校生成AI评价并插入数据库"""

import sys
import os
import json
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

CATEGORIES = CONFIG["categories"]
ALL_TAGS = CONFIG["tags"]

def calc_scores_from_answers(answers):
    category_scores = {}
    for cat_key, cat_info in CATEGORIES.items():
        question_scores = []
        for q in cat_info["questions"]:
            if q["id"] in answers:
                is_yes = answers[q["id"]]
                score = q["yes_score"] if is_yes else q["no_score"]
                question_scores.append(score)
        if question_scores:
            category_scores[cat_key] = round(sum(question_scores) / len(question_scores), 2)
        else:
            category_scores[cat_key] = 0
    total_weight = sum(
        cat_info["weight"]
        for cat_key, cat_info in CATEGORIES.items()
        if category_scores.get(cat_key, 0) > 0
    )
    if total_weight == 0:
        overall = 0
    else:
        overall = sum(
            category_scores.get(cat_key, 0) * cat_info["weight"]
            for cat_key, cat_info in CATEGORIES.items()
            if category_scores.get(cat_key, 0) > 0
        ) / total_weight
    return category_scores, round(overall, 2)

DATABASE = os.path.join(BASE_DIR, CONFIG["database"])
db = sqlite3.connect(DATABASE)
db.row_factory = sqlite3.Row

# ── 学校类型 → 允许的专业大类 ──
TYPE_CATEGORIES = {
    "综合": ["哲学", "经济学", "法学", "教育学", "文学", "历史学", "理学", "工学", "农学", "医学", "管理学", "艺术学"],
    "理工": ["经济学", "法学", "文学", "理学", "工学", "管理学"],
    "师范": ["哲学", "经济学", "法学", "教育学", "文学", "历史学", "理学", "管理学", "艺术学"],
    "医药": ["医学"],
    "农林": ["经济学", "法学", "文学", "理学", "工学", "农学", "管理学"],
    "财经": ["经济学", "法学", "文学", "管理学"],
    "政法": ["法学", "文学"],
    "民族": ["哲学", "经济学", "法学", "教育学", "文学", "历史学", "理学", "工学", "农学", "医学", "管理学", "艺术学"],
    "语言": ["文学", "管理学"],
    "艺术": ["文学", "艺术学"],
    "体育": ["教育学"],
}

RESTRICTED_CATEGORIES = {
    "理工": {
        "法学": ["知识产权"],
        "文学": ["英语", "日语", "翻译"],
    }
}

all_majors = db.execute("SELECT id, name, category FROM majors ORDER BY category, name").fetchall()

def get_majors_by_category(category):
    return [m for m in all_majors if m["category"] == category]

def get_allowed_majors(school_type):
    allowed_cats = TYPE_CATEGORIES.get(school_type, [])
    result = []
    for cat in allowed_cats:
        majors_in_cat = get_majors_by_category(cat)
        if school_type in RESTRICTED_CATEGORIES and cat in RESTRICTED_CATEGORIES[school_type]:
            allowed_names = RESTRICTED_CATEGORIES[school_type][cat]
            majors_in_cat = [m for m in majors_in_cat if m["name"] in allowed_names]
        result.extend(majors_in_cat)
    return result

def make_answers(base_score_profile, variations=None):
    profiles = {
        "academic": {
            "high": {"forced_run": False, "forced_study": False, "hard_course_select": False,
                     "system_crash": False, "bad_curriculum": False, "forced_lecture": False,
                     "bad_exam_schedule": False},
            "mid": {"forced_run": True, "forced_study": False, "hard_course_select": True,
                    "system_crash": False, "bad_curriculum": True, "forced_lecture": True,
                    "bad_exam_schedule": False},
            "low": {"forced_run": True, "forced_study": True, "hard_course_select": True,
                    "system_crash": True, "bad_curriculum": True, "forced_lecture": True,
                    "bad_exam_schedule": True},
        },
        "dormitory": {
            "high": {"private_bathroom": True, "has_ac": True, "power_limit": False,
                     "has_curfew": False, "bunk_bed": False, "over_6_room": False,
                     "room_check": False, "hot_water_24h": True, "laundry_access": True},
            "mid": {"private_bathroom": False, "has_ac": True, "power_limit": True,
                    "has_curfew": True, "bunk_bed": True, "over_6_room": False,
                    "room_check": True, "hot_water_24h": False, "laundry_access": True},
            "low": {"private_bathroom": False, "has_ac": False, "power_limit": True,
                    "has_curfew": True, "bunk_bed": True, "over_6_room": True,
                    "room_check": True, "hot_water_24h": False, "laundry_access": False},
        },
        "cafeteria": {
            "high": {"bad_food": False, "expensive_food": False, "food_safety_issue": False,
                     "limited_variety": False, "no_delivery": False, "no_nearby_food": False},
            "mid": {"bad_food": False, "expensive_food": True, "food_safety_issue": False,
                    "limited_variety": True, "no_delivery": True, "no_nearby_food": False},
            "low": {"bad_food": True, "expensive_food": True, "food_safety_issue": True,
                    "limited_variety": True, "no_delivery": True, "no_nearby_food": True},
        },
        "cost": {
            "high": {"expensive_utilities": False, "hidden_fees": False, "bad_internet": False,
                     "forced_internship_fee": False, "unclear_fees": False, "campus_monopoly": False},
            "mid": {"expensive_utilities": True, "hidden_fees": False, "bad_internet": True,
                    "forced_internship_fee": False, "unclear_fees": False, "campus_monopoly": True},
            "low": {"expensive_utilities": True, "hidden_fees": True, "bad_internet": True,
                    "forced_internship_fee": True, "unclear_fees": True, "campus_monopoly": True},
        },
        "environment": {
            "high": {"remote_location": False, "small_campus": False, "poor_facilities": True,
                     "no_transit": False, "bad_security": False, "multi_campus": False},
            "mid": {"remote_location": False, "small_campus": True, "poor_facilities": True,
                    "no_transit": False, "bad_security": False, "multi_campus": True},
            "low": {"remote_location": True, "small_campus": True, "poor_facilities": False,
                    "no_transit": True, "bad_security": True, "multi_campus": True},
        },
        "employment": {
            "high": {"fake_employment_rate": False, "forced_sign": False, "useless_career_center": False,
                     "bad_job_fair": False, "low_recognition": False, "trap_major": False,
                     "forced_factory": False},
            "mid": {"fake_employment_rate": True, "forced_sign": False, "useless_career_center": True,
                    "bad_job_fair": True, "low_recognition": False, "trap_major": False,
                    "forced_factory": False},
            "low": {"fake_employment_rate": True, "forced_sign": True, "useless_career_center": True,
                    "bad_job_fair": True, "low_recognition": True, "trap_major": True,
                    "forced_factory": True},
        },
        "admin": {
            "high": {"slow_admin": False, "bad_counselor": False, "formalism": False,
                     "unfair_scholarship": False, "no_feedback_channel": False,
                     "random_plan_change": False, "bureaucracy": False},
            "mid": {"slow_admin": True, "bad_counselor": False, "formalism": True,
                    "unfair_scholarship": True, "no_feedback_channel": True,
                    "random_plan_change": False, "bureaucracy": True},
            "low": {"slow_admin": True, "bad_counselor": True, "formalism": True,
                    "unfair_scholarship": True, "no_feedback_channel": True,
                    "random_plan_change": True, "bureaucracy": True},
        },
        "mental": {
            "high": {"no_counseling": False, "no_room_change": False, "bad_club": False},
            "mid": {"no_counseling": True, "no_room_change": True, "bad_club": False},
            "low": {"no_counseling": True, "no_room_change": True, "bad_club": True},
        },
    }
    answers = {}
    for cat, level in base_score_profile.items():
        if level in profiles.get(cat, {}):
            answers.update(profiles[cat][level])
    if variations:
        answers.update(variations)
    return answers

# ── 省/级别评分调整 ──
PROVINCE_ADJUSTMENTS = {
    "天津": {"dormitory": 0.2, "cafeteria": 0.1, "employment": 0.1},
    "河北": {"dormitory": 0.0, "cafeteria": 0.0, "employment": 0.0},
    "山西": {"dormitory": -0.1, "cafeteria": 0.0, "employment": -0.1},
    "河南": {"dormitory": 0.0, "cafeteria": 0.1, "employment": 0.0},
    "江西": {"dormitory": 0.0, "cafeteria": 0.0, "employment": 0.0},
    "福建": {"dormitory": 0.2, "cafeteria": 0.1, "employment": 0.1},
    "安徽": {"dormitory": 0.2, "cafeteria": 0.1, "employment": 0.1},
}

LEVEL_BONUS = {
    "985/211": 0.4,
    "985": 0.4,
    "211": 0.2,
    "双一流": 0.1,
    "普通": 0.0,
}

def apply_adjustments(category_scores, overall_score, province, level):
    """Apply province and level adjustments to scores."""
    adj = PROVINCE_ADJUSTMENTS.get(province, {})
    adjusted_cat = dict(category_scores)
    for cat, bonus in adj.items():
        if cat in adjusted_cat:
            adjusted_cat[cat] = round(adjusted_cat[cat] + bonus, 2)

    # Recalculate overall with adjusted category scores
    total_weight = sum(
        cat_info["weight"]
        for cat_key, cat_info in CATEGORIES.items()
        if adjusted_cat.get(cat_key, 0) > 0
    )
    if total_weight > 0:
        new_overall = sum(
            adjusted_cat.get(cat_key, 0) * cat_info["weight"]
            for cat_key, cat_info in CATEGORIES.items()
            if adjusted_cat.get(cat_key, 0) > 0
        ) / total_weight
    else:
        new_overall = overall_score

    # Add level bonus to overall
    lb = LEVEL_BONUS.get(level, 0.0)
    new_overall = round(new_overall + lb, 2)

    return adjusted_cat, new_overall


# ====================================================================
# 评价数据 — 35所高校
# ====================================================================
SCHOOL_REVIEWS = {}

# ==================== 天津 (6所) ====================

# 123 南开大学 (综合, 985/211)
SCHOOL_REVIEWS[123] = [
    {"major": "经济学", "comment": "南开经济学院在全国排得上号，学术氛围浓厚。八里台校区宿舍四人间无独卫，津南新校区好很多，上床下桌空调暖气全齐。食堂二食堂的麻辣香锅和实习餐厅的牛肉面是招牌。就业在天津和北京金融圈认可度很高。",
     "tags": ["老师超好", "就业无忧", "宿舍豪华"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "计算机科学与技术", "comment": "南开计算机近年发展不错，AI方向有布局。津南校区宿舍条件极好，4人间上床下桌空调暖气，有独立淋浴间。食堂选择多，文科食堂的重庆小面很赞。就业可以去大厂，南开牌子在北京天津都好使。",
     "tags": ["宿舍豪华", "空调自由", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "化学", "comment": "南开化学全国顶尖，国家重点实验室。津南校区宿舍条件一流，新区配套设施完善。学术资源丰富，出国深造比例高。食堂津南新校区选择多。就业方面学术界和化工企业都认可南开化学。",
     "tags": ["宿舍豪华", "老师超好", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "bad_exam_schedule": True}},
]

# 124 天津大学 (理工, 985/211)
SCHOOL_REVIEWS[124] = [
    {"major": "计算机科学与技术", "comment": "天大计算机发展快，新工科建设不错。北洋园新校区宿舍四人间上床下桌独立卫浴，条件很好。食堂学一的酱牛肉和学三的麻辣烫很受欢迎。卫津路老校区鹏翔宿舍6人间条件差些，但北洋园是真香。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "土木工程", "comment": "天大土木建筑老八校之一，实力强劲。北洋园新校区环境优美，宿舍条件一流。老校区鹏翔公寓条件一般但靠近市区。就业方面设计院和施工单位抢着要，天大土木的牌子在行业里响当当。",
     "tags": ["宿舍豪华", "老师超好", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "bunk_bed": True}},
    {"major": "电气工程及其自动化", "comment": "天大电气在天津是王牌。北洋园校区宿舍条件好，独立卫浴。食堂选择多，留园餐厅的清真食堂不错。就业国家电网每年大批招天大学生，电力行业校友遍布。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "化学工程与工艺", "comment": "天大化工全国第一！北洋园校区实验楼设备一流。宿舍条件好，四人上床下桌。食堂的桂花糯米藕和铁板饭不错。就业化工巨头和新能源企业抢着要天大化工毕业生，行业认可度极高。",
     "tags": ["老师超好", "宿舍豪华", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 125 天津医科大学 (医药, 211)
SCHOOL_REVIEWS[125] = [
    {"major": "临床医学", "comment": "天医大是天津最好的医学院。气象台路校区在市中心，宿舍四人间有空调。食堂不大但味道尚可。附属总医院和肿瘤医院实习资源好。学医压力大考试月很苦，但就业天津各大医院都认天医大牌子。",
     "tags": ["老师超好", "就业无忧", "内卷严重"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"forced_study": True, "bad_exam_schedule": True}},
    {"major": "药学", "comment": "天医药学在天津有优势。学校小而精，位置在市中心。宿舍有空调。食堂价格适中。做实验多，课业繁重。就业天津药企和医院药剂科有渠道。211身份在医药行业升学就业有优势。",
     "tags": ["老师超好", "佛系养身", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "mid"},
     "variations": {"forced_study": True}},
]

# 126 天津工业大学 (理工, 双一流)
SCHOOL_REVIEWS[126] = [
    {"major": "计算机科学与技术", "comment": "天工大计算机有纺织信息化特色。新校区宿舍四人间空调独卫条件不错。食堂芳缘餐厅的麻辣香锅很受欢迎。双一流身份后学校发展快。就业天津IT企业和纺织行业信息化都有路子。",
     "tags": ["宿舍豪华", "空调自由", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "机械工程", "comment": "天工大机械在天津普通院校里不错。新校区设施新宿舍好。食堂便宜实惠。学校以纺织起家但工科全面发展。就业天津制造业企业有校招。双一流身份对就业有帮助。",
     "tags": ["宿舍豪华", "老师超好", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 127 天津师范大学 (师范, 普通)
SCHOOL_REVIEWS[127] = [
    {"major": "教育学", "comment": "天津师大是天津中小学教师主要来源。主校区在宾水西道，宿舍四人间有空调。食堂二食堂的刀削面不错。师范类氛围浓，教育实习安排到位。天津当老师的话，天师大认可度很高，就业率不错。",
     "tags": ["老师超好", "就业无忧", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "汉语言文学", "comment": "天师大中文系有师范传统。学校在天津西青区，校园环境不错。宿舍条件中上。食堂便宜。当语文老师天师大是天津首选。学校虽然普通但在天津教育界校友众多。",
     "tags": ["老师超好", "就业无忧", "食堂神仙"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {}},
]

# 167 河北工业大学 (理工 — 在天津, 211)
SCHOOL_REVIEWS[167] = [
    {"major": "电气工程及其自动化", "comment": "河工大电气是王牌，电气工程全国有名。红桥校区宿舍条件一般但新校区好。食堂老校区偏旧但价格便宜。就业国家电网每年大量招河工大毕业生，电气在行业内口碑很好。虽是河北学校但在天津，地理位置好。",
     "tags": ["老师超好", "就业无忧", "宿舍破旧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "bunk_bed": True}},
    {"major": "计算机科学与技术", "comment": "河工大计算机211牌子在天津河北都好用。北辰校区宿舍条件不错有空调。食堂价格适中。就业京津冀IT企业校招都有。学校主校区在天津，享受天津的就业红利。",
     "tags": ["空调自由", "就业无忧", "老师超好"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "机械工程", "comment": "河工大机械在河北天津有口碑。北辰校区新，宿舍四人间空调独卫。食堂选择多。学校在天津就业有优势，京津冀制造业企业都认河工大211。",
     "tags": ["宿舍豪华", "就业无忧", "空调自由"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 236 中国民航大学 (理工, 普通)
SCHOOL_REVIEWS[236] = [
    {"major": "航空航天工程", "comment": "中航大是中国民航人才的摇篮。东丽校区有各种飞机真机展示，民航特色鲜明。宿舍四人间空调，北校区条件好于南校区。食堂民航人家餐厅的烤串不错。就业民航系统太稳了，国航东航南航定点招人。",
     "tags": ["老师超好", "就业无忧", "空调自由"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "电子信息工程", "comment": "中航大电子偏向航空电子方向。学校在天津滨海机场附近，每天看飞机起降。宿舍条件尚可。食堂民航特色食品不错。就业民航系统和空管局很认中航大，就业率非常高。",
     "tags": ["就业无忧", "老师超好", "空调自由"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "low", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"remote_location": True}},
]


# ==================== 河北 (5所) ====================

# 168 燕山大学 (理工, 普通)
SCHOOL_REVIEWS[168] = [
    {"major": "机械工程", "comment": "燕大机械全国闻名，源于哈工大重型机械系。校园在秦皇岛，面朝渤海。宿舍六人间上下铺条件一般但有空调。食堂燕大的大食堂和西区食堂不错，价格便宜。就业机械行业很认可燕大，三一重工中联重科每年招人。",
     "tags": ["老师超好", "就业无忧", "校园巨美"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"bunk_bed": True}},
    {"major": "计算机科学与技术", "comment": "燕大计算机在秦皇岛还不错。校园靠近海边，环境宜人。宿舍有空调。学校虽然不是211但机械背景扎实。就业互联网和制造业都有去，燕大校友在行业内挺多。",
     "tags": ["校园巨美", "老师超好", "空调自由"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
    {"major": "材料科学与工程", "comment": "燕大材料有亚稳材料国家重点实验室，实力强。秦皇岛环境优美适合做科研。宿舍条件一般但有空调。学术氛围不错。就业材料类企业有校招，考研深造比例也高。",
     "tags": ["老师超好", "校园巨美", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"bunk_bed": True, "bad_exam_schedule": True}},
]

# 169 河北大学 (综合, 普通)
SCHOOL_REVIEWS[169] = [
    {"major": "汉语言文学", "comment": "河大中文系百年底蕴，在河北省内文科强校。本部在保定，校园环境古朴。宿舍四人间有空调。食堂便宜实惠，保定驴肉火烧校外就有。就业河北中小学老师和考公有优势，省内认可度不错。",
     "tags": ["老师超好", "佛系养身", "食堂神仙"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "计算机科学与技术", "comment": "河大计算机在河北普通院校里还行。新校区宿舍条件好有空调。校园环境不错。食堂价格便宜。就业保定本地IT企业和北京外溢就业机会都有。学校虽然是综合大学但计算机在省内够用。",
     "tags": ["空调自由", "佛系养身", "食堂神仙"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "low", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 170 河北师范大学 (师范, 普通)
SCHOOL_REVIEWS[170] = [
    {"major": "教育学", "comment": "河北师大是河北中小学教师的摇篮。新校区在石家庄南二环，宿舍六人间上下铺有空调。食堂国培大厦的麻辣香锅好吃。师范类专业就业率高，河北各地市教育局校招必来。学费低性价比高。",
     "tags": ["老师超好", "就业无忧", "空调自由"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"bunk_bed": True}},
    {"major": "数学与应用数学", "comment": "河北师大数学系有师范传统。校园在石家庄，宿舍有空调。食堂便宜实惠。当数学老师河北师大是河北省内首选。就业率不错，河北师范类就业市场很认可。",
     "tags": ["老师超好", "就业无忧", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"bunk_bed": True}},
]

# 205 河北医科大学 (医药, 普通)
SCHOOL_REVIEWS[205] = [
    {"major": "临床医学", "comment": "河北医大是河北省最好的医学院。中山校区在石家庄市中心，宿舍六人间上下铺条件一般。食堂便宜。附属二院省医院实习条件好。学医压力大但出路好，河北各大医院主力来自河北医大。",
     "tags": ["老师超好", "内卷严重", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "low", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"forced_study": True, "bunk_bed": True}},
    {"major": "护理学", "comment": "河北医大护理就业率很高。校区在石家庄，位置好。宿舍条件一般。学护理虽然辛苦但河北省内医院抢着要。学校虽然普通但医学类专业在省内很受认可。",
     "tags": ["老师超好", "就业无忧", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "low", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"bunk_bed": True}},
]

# 245 河北地质大学 (理工, 普通)
SCHOOL_REVIEWS[245] = [
    {"major": "计算机科学与技术", "comment": "河北地质大学在石家庄，原来叫石家庄经济学院。新校区宿舍四人间空调独卫条件不错。食堂便宜。计算机专业虽不是主打但够用。就业石家庄本地IT企业有校招，地质信息化方向有特色。",
     "tags": ["宿舍豪华", "空调自由", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "low", "admin": "mid", "mental": "high"},
     "variations": {}},
    {"major": "会计学", "comment": "河北地质大学会计有传统。学校前身是地质部院校，经管类有底蕴。宿舍新校区条件好。食堂便宜。就业地质系统和河北本地企业有渠道。普通院校里算性价比不错的。",
     "tags": ["宿舍豪华", "佛系养身", "老师超好"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]


# ==================== 山西 (4所) ====================

# 171 太原理工大学 (理工, 211)
SCHOOL_REVIEWS[171] = [
    {"major": "计算机科学与技术", "comment": "太原理工计算机在山西最强。明向校区宿舍四人间上床下桌空调暖气全齐，条件山西高校里最好之一。食堂明向新校区便宜好吃。就业山西IT企业和省外大厂都有，211身份在山西很能打。",
     "tags": ["宿舍豪华", "空调自由", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "机械工程", "comment": "太原理工机械山西第一。迎西校区在市中心，宿舍条件一般6人间。明向校区新宿舍好。机械在山西煤机行业很对口。就业太重集团和各大煤机企业很爱招。211牌子在山西找工作优势明显。",
     "tags": ["老师超好", "就业无忧", "宿舍破旧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "bunk_bed": True}},
    {"major": "电气工程及其自动化", "comment": "太原理工电气山西电网定点招人。明向校区宿舍条件好新装修。食堂不错。就业山西电力系统基本被太原理工包揽。211身份在山西就业就是金字招牌。",
     "tags": ["宿舍豪华", "就业无忧", "空调自由"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 172 山西大学 (综合, 双一流)
SCHOOL_REVIEWS[172] = [
    {"major": "物理学", "comment": "山大物理双一流学科，量子光学全国领先。坞城校区宿舍四人间有空调。食堂令德和文瀛都有特色菜。学术氛围好，考研深造比例高。双一流后学校发展提速。就业山西科研院所和高中物理老师是出路。",
     "tags": ["老师超好", "佛系养身", "空调自由"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"bad_exam_schedule": True}},
    {"major": "计算机科学与技术", "comment": "山大计算机在山西仅次于太原理工。坞城校区在太原市中心，生活方便。宿舍条件中上。食堂便宜。双一流身份对计算机专业有提升。就业山西IT企业和省外大厂都有路子。",
     "tags": ["老师超好", "空调自由", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "汉语言文学", "comment": "山大中文系百年老系底蕴深厚。校园在太原坞城路，环境好。宿舍有空调。食堂便宜实惠。就业山西中小学语文老师和考公有优势。百年学府的人文气息很浓。",
     "tags": ["老师超好", "校园巨美", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
]

# 173 中北大学 (理工, 普通)
SCHOOL_REVIEWS[173] = [
    {"major": "计算机科学与技术", "comment": "中北计算机有军工背景，信息安全方向有特色。主校区在太原尖草坪区，校园很大。宿舍六人间上下铺有空调。食堂便宜量大。就业军工企业和IT行业都有路子。虽然不是211但在国防领域有知名度。",
     "tags": ["老师超好", "空调自由", "校园巨美"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"bunk_bed": True, "remote_location": True}},
    {"major": "机械工程", "comment": "中北机械有兵器背景，军工特色鲜明。校园在二龙山下环境好。宿舍条件一般。食堂价格实在。就业军工央企和兵工企业每年招中北毕业生，就业稳定。",
     "tags": ["老师超好", "校园巨美", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"bunk_bed": True, "remote_location": True}},
]

# 247 山西农业大学 (农林, 普通)
SCHOOL_REVIEWS[247] = [
    {"major": "农学", "comment": "山西农大在太谷，校区有百年历史。宿舍六人间上下铺条件一般但有空调。食堂便宜好吃，山西面食一绝。农学专业山西农业系统认山西农大。就业基层农业技术服务和考研深造是主流。",
     "tags": ["老师超好", "佛系养身", "空调自由"],
     "profile": {"academic": "mid", "dormitory": "low", "cafeteria": "mid", "cost": "high", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"bunk_bed": True, "remote_location": True}},
    {"major": "动物医学", "comment": "山西农大动医在山西畜牧业中作用大。校园在太谷县城环境清幽。宿舍条件一般但有空调。食堂山西面食好吃不贵。就业山西畜牧兽医系统和宠物医院有渠道。可以说是山西农业人才基地。",
     "tags": ["老师超好", "佛系养身", "食堂神仙"],
     "profile": {"academic": "mid", "dormitory": "low", "cafeteria": "mid", "cost": "high", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"bunk_bed": True, "remote_location": True}},
]


# ==================== 河南 (5所) ====================

# 161 郑州大学 (综合, 211)
SCHOOL_REVIEWS[161] = [
    {"major": "计算机科学与技术", "comment": "郑大计算机是河南IT人才主要来源。主校区在科学大道，超大校园。宿舍条件分区域，柳园荷园四人间有空调，但松园菊园旧些。食堂很多，荷园一餐厅的烩面正宗。就业河南互联网和IT企业校招首选郑大。",
     "tags": ["食堂神仙", "就业无忧", "空调自由"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "临床医学", "comment": "郑大医学院河南第一。主校区在科学大道，附属一院是亚洲最大医院。宿舍新区条件好有空调。学医压力巨大但出路极好。食堂选择多，荷园商业街很热闹。就业河南省医院系统郑大毕业生占大半。",
     "tags": ["老师超好", "内卷严重", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"forced_study": True, "bad_exam_schedule": True}},
    {"major": "材料科学与工程", "comment": "郑大材料是双一流学科。主校区大，宿舍条件参差不齐。教学资源丰富，实验室设备好。食堂多到吃不过来。就业新材料企业和考研深造是主流。河南唯一211，省内就业无敌。",
     "tags": ["食堂神仙", "老师超好", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "法学", "comment": "郑大法学院在河南称霸。校园巨大从宿舍到教学楼要走半小时。宿舍新区不错。食堂选择多价格实惠。就业河南法检系统和律所郑大是主力军。作为河南唯一211，在省内就业优势明显。",
     "tags": ["食堂神仙", "老师超好", "校园巨美"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "small_campus": False}},
]

# 162 河南大学 (综合, 双一流)
SCHOOL_REVIEWS[162] = [
    {"major": "汉语言文学", "comment": "河大中文系百年名校底蕴深厚。明伦校区在开封，近代建筑群很美。宿舍老校区旧但新校区好有空调。食堂仁和公寓的炒面和中心食堂的烩饼是经典。就业河南中小学语文老师主力。双一流后学校热度大增。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "计算机科学与技术", "comment": "河大计算机在开封和郑州校区。郑州校区新条件好。宿舍新校区四人间有空调。双一流后计算机投入加大。就业河南IT企业有校招。河大百年名校品牌在省内有号召力。",
     "tags": ["校园巨美", "空调自由", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "经济学", "comment": "河大经济学院在河南有影响力。郑州龙子湖校区新设施好。宿舍条件不错。食堂选择多。双一流后学校发展快。就业河南金融机构和考公有优势。百年河大的人文底蕴很深厚。",
     "tags": ["老师超好", "校园巨美", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 165 河南农业大学 (农林, 普通)
SCHOOL_REVIEWS[165] = [
    {"major": "农学", "comment": "河南农大在郑州文化路。宿舍六人间上下铺条件一般但有空调。食堂便宜河南面食正宗。农学专业河南农业大省需求大。就业农业局和种业企业有渠道。学校不是211但在河南农业系统很认可。",
     "tags": ["老师超好", "佛系养身", "空调自由"],
     "profile": {"academic": "mid", "dormitory": "low", "cafeteria": "mid", "cost": "high", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"bunk_bed": True, "multi_campus": True}},
    {"major": "食品科学与工程", "comment": "河南农大食品在河南不错。龙子湖新校区宿舍条件好。食堂河南特色小吃多。河南食品工业发达，就业双汇三全思念等企业每年招农大毕业生。性价比高的农业院校。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 163 河南科技大学 (理工, 普通)
SCHOOL_REVIEWS[163] = [
    {"major": "机械工程", "comment": "河科大在洛阳，轴承专业全国闻名。开元校区宿舍四人间空调独卫。食堂的洛阳牛肉汤和胡辣汤是早餐标配。就业洛阳轴承企业和制造业抢着要河科大毕业生，机械行业校友遍布。",
     "tags": ["宿舍豪华", "老师超好", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "计算机科学与技术", "comment": "河科大计算机在洛阳不错。开元校区新宿舍条件好。食堂便宜河南面食丰富。就业洛阳本地IT企业和制造业信息化部门有需求。学校机械背景强大，计算机辅助制造方向有特色。",
     "tags": ["宿舍豪华", "食堂神仙", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "low", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 269 河南财经政法大学 (财经, 普通)
SCHOOL_REVIEWS[269] = [
    {"major": "金融学", "comment": "河南财大在郑州龙子湖，是河南财经类最强。宿舍四人间空调独卫新校区条件好。食堂一餐和二餐选择丰富。就业河南银行证券保险机构校招主力。虽然不是211但在河南财经界校友众多。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
    {"major": "会计学", "comment": "河南财大会计在河南认可度高。龙子湖校区环境好设施新。宿舍有空调条件好。食堂东苑西苑选择多。就业四大和河南本土事务所每年校招。在河南财经政法类院校里性价比很高。",
     "tags": ["宿舍豪华", "就业无忧", "老师超好"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"hard_course_select": True}},
]


# ==================== 江西 (5所) ====================

# 174 南昌大学 (综合, 211)
SCHOOL_REVIEWS[174] = [
    {"major": "计算机科学与技术", "comment": "昌大计算机在江西最强。前湖校区超大，宿舍四人间空调独卫条件不错。食堂一食堂的南昌拌粉和瓦罐汤非常正宗。就业江西IT企业和省外都有渠道。江西唯一211，省内就业有绝对优势。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "临床医学", "comment": "昌大医学院江西第一。前湖校区宿舍好。附属一附二医院实习资源丰富。学医压力大但出路好。食堂南昌拌粉和瓦罐汤天天吃都不腻。就业江西各大医院昌大毕业生占绝大多数。",
     "tags": ["宿舍豪华", "食堂神仙", "内卷严重"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"forced_study": True, "bad_exam_schedule": True}},
    {"major": "材料科学与工程", "comment": "昌大材料是双一流学科。前湖校区环境好宿舍条件好。食堂多选择丰富。学术资源不错，LED方向有特色。就业材料类企业和考研深造是主流。江西唯一211，材料学科全国有知名度。",
     "tags": ["宿舍豪华", "老师超好", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 176 江西师范大学 (师范, 普通)
SCHOOL_REVIEWS[176] = [
    {"major": "教育学", "comment": "江西师大是江西中小学教师主要来源。瑶湖校区校园很美，静湖和长胜园适合散步。宿舍四人间有空调。食堂三食堂的南昌炒粉很赞。就业江西各地教师编考试江西师大毕业生占比很大。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "汉语言文学", "comment": "江西师大中文系有师范传统。瑶湖校区环境优美，图书馆气派。宿舍有空调。食堂南昌拌粉和瓦罐汤便宜好吃。就业江西中小学语文老师主力。学校普通但在江西省内教育界影响力很大。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {}},
]

# 175 江西财经大学 (财经, 普通)
SCHOOL_REVIEWS[175] = [
    {"major": "金融学", "comment": "江财金融在江西财经界久负盛名。蛟桥园校区在南昌经开区，宿舍四人间有空调。食堂鼎食轩的煲仔饭和盖浇饭不错。就业银行证券保险机构在江西招人首选江财。虽然不是211但在财经领域校友众多。",
     "tags": ["老师超好", "就业无忧", "空调自由"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "会计学", "comment": "江财会计全国有名，四大会计师事务所每年校招。蛟桥园和麦庐园两个校区，宿舍有空调。食堂选择多。就业在华南和长三角地区江财牌子很好用。虽然普通院校但会计专业认可度超强。",
     "tags": ["老师超好", "就业无忧", "空调自由"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "hard_course_select": True}},
]

# 268 江西理工大学 (理工, 普通)
SCHOOL_REVIEWS[268] = [
    {"major": "机械工程", "comment": "江西理工在赣州，以有色金属为特色。红旗校区宿舍条件一般有空调。食堂便宜量大。赣州生活成本低。就业有色金属企业和制造业有优势，江西理工在冶金机械领域校友广泛。",
     "tags": ["老师超好", "空调自由", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "low", "cafeteria": "mid", "cost": "high", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"bunk_bed": True, "multi_campus": True}},
    {"major": "计算机科学与技术", "comment": "江西理工计算机在赣州够用。新校区宿舍条件好有空调。食堂便宜。学校以工科为主。就业江西本地IT企业和制造业信息化部门有需求。普通院校里计算机性价比尚可。",
     "tags": ["空调自由", "佛系养身", "宿舍豪华"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "mid", "employment": "low", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 267 华东交通大学 (理工, 普通)
SCHOOL_REVIEWS[267] = [
    {"major": "土木工程", "comment": "华东交大在南昌，铁路特色鲜明。南区宿舍四人间有空调。食堂北区列咖的盖浇饭好吃。就业铁路局和中铁建交建每年大量招人，华东交大在铁路系统校友遍布。虽然不是211但就业非常稳定。",
     "tags": ["老师超好", "就业无忧", "空调自由"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "计算机科学与技术", "comment": "华东交大计算机有轨道交通信息化特色。南昌校区环境不错。宿舍有空调。食堂选择多。就业除了铁路系统，互联网也有校招。学校虽普通但在铁路行业名气不小。",
     "tags": ["空调自由", "就业无忧", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]


# ==================== 福建 (5所) ====================

# 152 厦门大学 (综合, 985/211)
SCHOOL_REVIEWS[152] = [
    {"major": "计算机科学与技术", "comment": "厦大计算机在福建省最强。翔安校区宿舍条件厦门高校天花板，四人间上床下桌独卫浴海景房。食堂芙蓉餐厅的海蛎煎和沙茶面是一绝。思明本部宿舍旧些但芙蓉湖太美了。就业互联网大厂校招厦大是必到站。",
     "tags": ["宿舍豪华", "食堂神仙", "校园巨美"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "high", "admin": "high", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "经济学", "comment": "厦大经济学科全国前列。思明校区宿舍条件一般但芙蓉湖、情人谷太美了。食堂芙蓉三楼的海蛎煎和南光的沙茶面是厦大记忆。就业投行券商基金厦大校友很多，东南沿海金融圈认可度极高。",
     "tags": ["校园巨美", "食堂神仙", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "法学", "comment": "厦大法学院全国知名。思明校区面朝大海春暖花开。宿舍本部条件一般但翔安校区好。食堂沙茶面和海蛎煎永远的神。就业福建律所和东南沿海法检系统厦大是王牌。学术氛围和校园环境都是顶级。",
     "tags": ["校园巨美", "食堂神仙", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "临床医学", "comment": "厦大医学院年轻但发展快。翔安校区宿舍海景房条件一流。食堂翔安校区好。附属翔安医院和中山医院实习。学医压力大但厦大985牌子在福建医疗圈好用。",
     "tags": ["宿舍豪华", "校园巨美", "内卷严重"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"multi_campus": True, "forced_study": True}},
]

# 153 福州大学 (理工, 211)
SCHOOL_REVIEWS[153] = [
    {"major": "计算机科学与技术", "comment": "福大计算机在福建仅次于厦大。旗山校区宿舍四人间空调独卫，新宿舍很赞。食堂玫瑰园和紫荆园的选择多，福大美食 campus有名。就业福建IT企业和互联网公司校招首选福大。211牌子在福建很能打。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "电气工程及其自动化", "comment": "福大电气福建电网定点招人。旗山校区设施新宿舍好。食堂玫瑰园夜宵很出名。就业国家电网福建公司大量招福大毕业生。在福建福大电气就是王牌专业。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "化学工程与工艺", "comment": "福大化工是双一流学科。旗山校区新宿舍条件好。校园环境优美，福友阁的湖景很美。就业福建石化企业有对口。211化工在福建就业无忧。",
     "tags": ["宿舍豪华", "校园巨美", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 155 华侨大学 (综合, 普通)
SCHOOL_REVIEWS[155] = [
    {"major": "计算机科学与技术", "comment": "华侨大学在厦门和泉州，厦门校区靠海。宿舍四人间空调独卫，厦门条件好。食堂厦门校区紫荆和凤竹不错。境外生多文化多元。就业福建IT企业和东南沿海都有路子。不是211但在福建认可度不错。",
     "tags": ["宿舍豪华", "校园巨美", "社团丰富"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "经济学", "comment": "华大经济学院在福建不错。厦门校区靠海风景好。宿舍条件好有独卫。境外生多国际化氛围浓。就业福建金融企业和考公有优势。学校侨校特色，港澳台同学多。",
     "tags": ["宿舍豪华", "校园巨美", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 154 福建师范大学 (师范, 普通)
SCHOOL_REVIEWS[154] = [
    {"major": "教育学", "comment": "福建师大是福建中小学教师黄埔军校。旗山校区宿舍四人间空调独卫。食堂花香园和翠竹园的美味不可错过。校园很大溪源江畔很美。就业福建各地教育局校招必来福师大，当老师非常稳。",
     "tags": ["宿舍豪华", "食堂神仙", "校园巨美"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "汉语言文学", "comment": "福师大中文系百年底蕴，福建文科强校。旗山校区宿舍好。长安山老校区有历史感。食堂选择多。当语文老师福师大在福建最好使。学校虽然普通但在福建省内就业竞争力强。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 156 福建农林大学 (农林, 普通)
SCHOOL_REVIEWS[156] = [
    {"major": "农学", "comment": "福建农林在福州金山。宿舍四人间有空调。食堂八餐厅和九餐厅的荔枝肉和佛跳墙有特色。农学专业在福建农业系统认可度高。校园像植物园环境优美。不是211但在福建农林领域是老大。",
     "tags": ["校园巨美", "食堂神仙", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "食品科学与工程", "comment": "福建农林食品在福建有优势。校园植被丰富有观音湖。宿舍有空调。食堂茶人码头不错。就业福建食品企业如盼盼达利等有校招。农林类院校性价比不错。",
     "tags": ["校园巨美", "老师超好", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]


# ==================== 安徽 (5所) ====================

# 157 中国科学技术大学 (理工, 985/211)
SCHOOL_REVIEWS[157] = [
    {"major": "计算机科学与技术", "comment": "中科大计算机科研实力极强，AI方向全国顶尖。东校区宿舍上床下桌四人间空调暖气，西区新宿舍更好。食堂东区美食广场和西区金桔园都不错。学术氛围极浓，凌晨实验室灯火通明。就业深造比例极高，大厂和学术界抢着要。",
     "tags": ["宿舍豪华", "老师超好", "内卷严重"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "high", "admin": "high", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "物理学", "comment": "中科大物理全国顶级的地位不用多说。东校区宿舍条件好有暖气。食堂东西区各有特色。科研资源丰富，国家实验室就在校内。出国深造比例全国领先。在安徽读书却能享受全国顶级的教育资源。",
     "tags": ["宿舍豪华", "老师超好", "校园巨美"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "high", "admin": "high", "mental": "high"},
     "variations": {"bad_exam_schedule": True}},
    {"major": "数学与应用数学", "comment": "中科大数学全国顶尖，华罗庚班更是精英。宿舍条件好，学习氛围极卷。食堂便宜美味。学校以学术严谨著称，学生普遍深造。就业金融科技和学术界都认中科大数学。",
     "tags": ["宿舍豪华", "内卷严重", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "mid", "cost": "high", "environment": "high", "employment": "high", "admin": "high", "mental": "mid"},
     "variations": {"hard_course_select": True}},
    {"major": "化学", "comment": "中科大化学全国前几，有国家同步辐射实验室。宿舍条件好暖气空调齐全。食堂选择多。科研训练强度大但收获也大。深造率高，出国去名校的多。在合肥的生活成本低但教育质量极高。",
     "tags": ["宿舍豪华", "老师超好", "校园巨美"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "mid", "cost": "high", "environment": "high", "employment": "high", "admin": "high", "mental": "high"},
     "variations": {"bad_exam_schedule": True}},
]

# 158 合肥工业大学 (理工, 211)
SCHOOL_REVIEWS[158] = [
    {"major": "计算机科学与技术", "comment": "合工大计算机在安徽仅次于中科大。翡翠湖校区宿舍四人间空调独卫，新宿舍条件好。食堂一食堂和二食堂选择多。就业安徽IT企业和长三角大厂都有校招。工科底蕴深厚，计算机就业不错。",
     "tags": ["宿舍豪华", "就业无忧", "空调自由"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "车辆工程", "comment": "合工大车辆全国有名，汽车行业黄埔军校。屯溪路老校区宿舍条件一般但学术氛围浓。翡翠湖新校区好。就业江淮蔚来奇瑞等车企每年大批招合工大毕业生。汽车行业校友遍布全国。",
     "tags": ["老师超好", "就业无忧", "宿舍破旧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "bunk_bed": True}},
    {"major": "电气工程及其自动化", "comment": "合工大电气在安徽很强势。翡翠湖校区宿舍好。安徽电网校招首选合工大。食堂便宜实惠。工科底子扎实，就业面广。211身份在长三角就业竞争力强。",
     "tags": ["宿舍豪华", "就业无忧", "老师超好"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "机械工程", "comment": "合工大机械实力不凡。屯溪路校区老但有底蕴。翡翠湖校区新宿舍好。食堂东西不错。就业江淮汽车和长三角制造企业都认合工大。工科院校的务实风格很突出。",
     "tags": ["老师超好", "就业无忧", "空调自由"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 159 安徽大学 (综合, 211)
SCHOOL_REVIEWS[159] = [
    {"major": "计算机科学与技术", "comment": "安大计算机有国家级特色专业。磬苑校区宿舍四人间空调独卫条件好。食堂桔园和榴园的香锅不错。校园很大绿化好，鹅池里有黑天鹅。就业安徽IT企业有校招，211牌子好用。",
     "tags": ["宿舍豪华", "校园巨美", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "汉语言文学", "comment": "安大中文系有底蕴。磬苑校区环境优美，文典阁图书馆很有名。宿舍条件好有空调独卫。食堂选择多。就业安徽中小学语文老师和考公有优势。211文科在安徽省内就业竞争力强。",
     "tags": ["校园巨美", "宿舍豪华", "老师超好"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "经济学", "comment": "安大经济学院省内不错。磬苑校区宿舍条件好。食堂选择丰富。校园环境优美适合学习。就业安徽金融机构和考公有校友优势。211经济在省内好找工作，长三角也有竞争力。",
     "tags": ["宿舍豪华", "校园巨美", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 160 安徽师范大学 (师范, 普通)
SCHOOL_REVIEWS[160] = [
    {"major": "教育学", "comment": "安师大在芜湖，安徽中小学教师的摇篮。花津校区宿舍四人间空调独卫。食堂二食堂的牛肉面和麻辣香锅很赞。校园湖泊环绕风景优美。就业安徽各地教育局校招安师大是主力。当老师很稳。",
     "tags": ["宿舍豪华", "食堂神仙", "校园巨美"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "汉语言文学", "comment": "安师大中文系培养了大量安徽语文名师。花津校区环境好宿舍条件好。食堂便宜美味。芜湖生活节奏慢适合读书。就业当语文老师在安徽很稳。不是211但在安徽教育界口碑很好。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "high", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 262 安徽农业大学 (农林, 普通)
SCHOOL_REVIEWS[262] = [
    {"major": "农学", "comment": "安农大在合肥长江西路。宿舍四人间有空调，新公寓条件好。食堂学校里的小吃街很有生活气息。农学专业在安徽农业系统认可度高。校园里茶园和试验田是特色。就业安徽农业局和种业企业有渠道。",
     "tags": ["空调自由", "老师超好", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "食品科学与工程", "comment": "安农大食品在安徽不错。校园有茶学特色。宿舍有空调。食堂茶叶蛋和三河米饺不错。就业安徽食品企业有校招。农业院校性价比高生活成本低。",
     "tags": ["老师超好", "佛系养身", "空调自由"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]


# ── 主程序 ──
def main():
    print("=" * 60)
    print("学之声 - 天津/河北/山西/河南/江西/福建/安徽 35所高校AI评价生成器")
    print("=" * 60)

    existing = db.execute("SELECT COUNT(*) as cnt FROM reviews").fetchone()["cnt"]
    print(f"📊 数据库中现有评价数: {existing}")
    print("⚠️  保留已有评价，仅添加新评价")

    total = 0
    skipped_existing = 0

    for school_id, reviews in SCHOOL_REVIEWS.items():
        school = db.execute("SELECT * FROM schools WHERE id = ?", (school_id,)).fetchone()
        if not school:
            print(f"❌ 学校ID {school_id} 不存在，跳过")
            continue

        province = school["province"]
        level = school["level"]
        print(f"\n📌 {school['name']} ({school['type']}, {level}) [{province}]")

        allowed_majors = get_allowed_majors(school["type"])
        allowed_major_names = {m["name"]: m["id"] for m in allowed_majors}

        for i, review_data in enumerate(reviews):
            major_name = review_data["major"]
            major_id = allowed_major_names.get(major_name)

            if not major_id:
                major = db.execute("SELECT id FROM majors WHERE name = ?", (major_name,)).fetchone()
                if major:
                    major_id = major["id"]
                else:
                    print(f"   ❌ 专业 '{major_name}' 在数据库中不存在")
                    continue

            device_id = f"ai-generator-{province}-{school_id}-{i}"
            existing_review = db.execute(
                "SELECT id FROM reviews WHERE school_id = ? AND major_id = ? AND device_id = ?",
                (school_id, major_id, device_id)
            ).fetchone()
            if existing_review:
                skipped_existing += 1
                continue

            profile = review_data["profile"]
            variations = review_data.get("variations", {})

            answers = make_answers(profile, variations)

            # 计算基础分数
            category_scores, overall_score = calc_scores_from_answers(answers)

            # 确保所有类别都有回答
            cat_answered = {k: False for k in CATEGORIES.keys()}
            for q_id in answers:
                for cat_key, cat_info in CATEGORIES.items():
                    for q in cat_info["questions"]:
                        if q["id"] == q_id:
                            cat_answered[cat_key] = True

            for cat_key, answered in cat_answered.items():
                if not answered:
                    for q in CATEGORIES[cat_key]["questions"]:
                        if q["id"] not in answers:
                            if profile.get(cat_key) == "high":
                                answers[q["id"]] = q["yes_score"] > q["no_score"]
                            elif profile.get(cat_key) == "low":
                                answers[q["id"]] = q["yes_score"] < q["no_score"]
                            else:
                                answers[q["id"]] = q["id"] in ["poor_facilities", "laundry_access", "hot_water_24h", "has_ac", "private_bathroom"]
                            break

            # 重新计算
            category_scores, overall_score = calc_scores_from_answers(answers)

            # 应用省/级别调整
            category_scores, overall_score = apply_adjustments(category_scores, overall_score, province, level)

            comment = review_data["comment"]
            tags_json = json.dumps(review_data["tags"], ensure_ascii=False)
            answers_json = json.dumps(answers, ensure_ascii=False)
            cat_scores_json = json.dumps(category_scores, ensure_ascii=False)

            print(f"   📝 评价{i+1}: {major_name} | 综合: {overall_score:.1f}分")

            try:
                db.execute(
                    """INSERT INTO reviews 
                    (school_id, major_id, device_id, answers, category_scores, overall_score, comment, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (school_id, major_id, device_id, answers_json, cat_scores_json, overall_score, comment, tags_json)
                )
                db.commit()
                total += 1
            except sqlite3.IntegrityError as e:
                skipped_existing += 1
                print(f"   ⚠️ 已存在: {e}")

    print(f"\n{'=' * 60}")
    print(f"✅ 完成！共新增 {total} 条评价（跳过 {skipped_existing} 条已有）")

    count = db.execute("SELECT COUNT(*) as cnt FROM reviews").fetchone()["cnt"]
    print(f"📊 数据库中评价总数: {count}")

    print(f"\n📊 各省评价数:")
    provinces = ['天津', '河北', '山西', '河南', '江西', '福建', '安徽']
    for p in provinces:
        rows = db.execute("""
            SELECT s.province, COUNT(r.id) as cnt, ROUND(AVG(r.overall_score), 2) as avg
            FROM schools s
            LEFT JOIN reviews r ON s.id = r.school_id
            WHERE s.province = ?
            GROUP BY s.province
        """, (p,)).fetchall()
        for row in rows:
            print(f"   {row['province']}: {row['cnt']}条评价, 均分{row['avg']}")

    print(f"\n📊 各学校评价数:")
    for p in provinces:
        print(f"\n--- {p} ---")
        rows = db.execute("""
            SELECT s.name, s.level, COUNT(r.id) as cnt, ROUND(AVG(r.overall_score), 2) as avg
            FROM schools s
            LEFT JOIN reviews r ON s.id = r.school_id
            WHERE s.province = ?
            GROUP BY s.id
            ORDER BY s.name
        """, (p,)).fetchall()
        for row in rows:
            level_tag = f"[{row['level']}]" if row['level'] else ""
            print(f"   {level_tag} {row['name']}: {row['cnt']}条, 均分{row['avg']}")


if __name__ == "__main__":
    main()
