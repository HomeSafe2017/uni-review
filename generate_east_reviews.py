#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为上海、浙江、江苏55所高校生成AI评价并插入数据库"""

import sys
import os
import json
import sqlite3
import uuid
from datetime import datetime

# ── 加载app.py的环境 ──
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

# ── 辅助函数：生成回答 ──
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


# ====================================================================
# 评价数据
# ====================================================================
SCHOOL_REVIEWS = {}

# ==================== 上海 ====================

# 31 复旦大学 (综合, 985/211)
SCHOOL_REVIEWS[31] = [
    {"major": "经济学", "comment": "复旦经济学院学术氛围浓厚，教授很多是行业大牛。邯郸校区本部宿舍确实老，无预装空调但可以租赁，江湾新校区19层宿舍楼条件好多了。旦苑食堂的红烧肉是招牌，就是选课系统抢课太激烈了。实习机会多，陆家嘴和五角场就业资源丰富。",
     "tags": ["老师超好", "就业无忧", "内卷严重"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"hard_course_select": True, "has_ac": False}},
    {"major": "法学", "comment": "复旦法学院在上海首屈一指，师资雄厚。本部宿舍条件一般，无空调需租赁，但新江湾校区是19层高层电梯宿舍。食堂选择多但本部比较挤。江湾大草原环境极好，适合散步思考人生。就业方面律所和金融圈遍布复旦校友。",
     "tags": ["老师超好", "校园巨美", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"has_ac": False, "multi_campus": True}},
    {"major": "计算机科学与技术", "comment": "复旦计算机在张江校区，实验室设备新。张江宿舍条件好，独立卫浴。不断电是最大福音，码农随便熬夜。校园网速度不错。就业方面很多去互联网大厂和外资企业，复旦牌子在上海横着走。",
     "tags": ["宿舍豪华", "WiFi飞起", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "mid", "cost": "high", "environment": "high", "employment": "high", "admin": "high", "mental": "high"},
     "variations": {"power_limit": False, "has_curfew": False, "multi_campus": True}},
    {"major": "新闻学", "comment": "复旦新闻学院全国前三，资源好到爆。本部宿舍条件一般但习惯了。光华楼前的草坪是上海高校最浪漫的地方。实习机会太多了，上海各大媒体都有复旦实习生。就是本部的宿舍空调要自己租有点烦。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"has_ac": False, "bunk_bed": True}},
    {"major": "临床医学", "comment": "复旦上海医学院全国顶尖，附属中山华山医院就在旁边。枫林校区宿舍翻新后条件好了很多。学业压力非常大但值得。食堂一般但医学院旁边好吃的太多。就业完全不愁，三甲医院抢着要。",
     "tags": ["老师超好", "内卷严重", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"bad_exam_schedule": True, "forced_study": True}},
]

# 32 上海交通大学 (理工, 985/211)
SCHOOL_REVIEWS[32] = [
    {"major": "计算机科学与技术", "comment": "交大计算机实力强劲，ACM班全国闻名。闵行校区宿舍上床下桌独立卫浴，3-4人间配置在上海高校里数一数二。食堂很多，二餐的吉姆丽德和哈乐餐厅口碑好。就业极强，大厂管培生随便投。就是闵行偏了点进市区一小时。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "mid", "employment": "high", "admin": "high", "mental": "high"},
     "variations": {"remote_location": True, "hard_course_select": True}},
    {"major": "软件工程", "comment": "交大软院就业率在上海高校里排前列。闵行校区虽然偏但校园超大，有校内公交。宿舍条件极好，上床下桌独卫浴。食堂的麻辣香锅和铁板烧绝了。学术氛围很卷但也很自由，创业氛围浓。",
     "tags": ["宿舍豪华", "食堂神仙", "校园巨美"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True, "small_campus": False}},
    {"major": "机械工程", "comment": "交大机械是传统强项，实验室设备一流。闵行住宿条件上海顶尖，独立卫浴配置拉满。食堂选择太多，四餐的重庆小面三餐的麻辣烫都好吃。校园大到需要骑车，植物园里散步很惬意。就是闵行确实远。",
     "tags": ["宿舍豪华", "食堂神仙", "校园巨美"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True, "multi_campus": True}},
    {"major": "英语", "comment": "交大外国语学院虽然不如综合性大学外语系大，但交大平台好。宿舍条件极好，上床下桌独立卫浴。闵行虽然偏但环境好、设施新。就业方面，交大牌子+英语能力，外企咨询公司抢着要。",
     "tags": ["宿舍豪华", "就业无忧", "食堂神仙"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "high", "admin": "high", "mental": "high"},
     "variations": {"remote_location": True}},
]

# 33 同济大学 (理工, 985/211)
SCHOOL_REVIEWS[33] = [
    {"major": "土木工程", "comment": "同济土木世界第一。四平路校区西北片区宿舍条件很好，有空调暖气。学苑食堂和北苑食堂都不错。学校的樱花大道每年春天美炸了。就业方面，设计院和房地产企业抢着要。就是功课难到秃头。",
     "tags": ["老师超好", "校园巨美", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"bad_exam_schedule": True}},
    {"major": "建筑学", "comment": "同济建筑全国前三，熬夜通宵画图是常态但值得。西北片区宿舍条件好，空调暖气齐全。学校在四平路，去哪都方便。食堂三好坞的牛肉面和西苑的糖醋小排超赞。同济的创业氛围也很浓。",
     "tags": ["老师超好", "校园巨美", "食堂神仙"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"bad_exam_schedule": True, "hard_course_select": True}},
    {"major": "计算机科学与技术", "comment": "同济计算机近年发展很快。嘉定校区宿舍条件好，独立卫浴空调齐全。就是嘉定到本部通勤有点远。食堂嘉定不错但不如本部丰富。就业在上海认可度高，互联网和汽车行业都有。",
     "tags": ["宿舍豪华", "空调自由", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "remote_location": True}},
    {"major": "自动化", "comment": "同济自动化在嘉定校区，设施新。宿舍条件好，四人上床下桌独卫。同济的工科底蕴深厚。就业不错，车企和自动化公司很爱招同济的。就是嘉定太偏了，去市区实习不太方便。",
     "tags": ["宿舍豪华", "老师超好", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "remote_location": True}},
]

# 34 华东师范大学 (师范, 985/211)
SCHOOL_REVIEWS[34] = [
    {"major": "教育学", "comment": "华师大学前教育全国第一。中山北路校区宿舍四人间有独卫条件还行。食堂河西的麻辣香锅和河东的排骨年糕是招牌。闵行校区虽然偏但宿舍条件更新。上海当老师华师大就是金字招牌。",
     "tags": ["老师超好", "就业无忧", "食堂神仙"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "mid", "employment": "high", "admin": "high", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "汉语言文学", "comment": "华师大中文系底蕴深厚，很多著名作家教授。中山北路校区在市区位置好。宿舍四人间有空调独卫。丽娃河和文史楼很有韵味。食堂选择多，华闵和秋实阁都不错。就业方面，当老师和考公都很稳。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "high", "mental": "high"},
     "variations": {"small_campus": True}},
    {"major": "心理学", "comment": "华师大心理与认知科学学院全国前列。闵行校区宿舍四人间无独卫，但设施还算新。学校环境很好，樱桃河畔适合散步。学术资源丰富，实验设备先进。就业方面心理咨询和企业HR方向都不错。",
     "tags": ["老师超好", "校园巨美", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "private_bathroom": False}},
    {"major": "数学与应用数学", "comment": "华师大数学系很强，师范数学全国顶尖。中山北路校区位置好，去哪里都方便。宿舍有四人间独卫。图书馆的数学藏书丰富。就业方面当数学老师很吃香，上海重点中学抢着要。",
     "tags": ["老师超好", "就业无忧", "图书馆霸位"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 35 上海财经大学 (财经, 211)
SCHOOL_REVIEWS[35] = [
    {"major": "金融学", "comment": "上财金融在上海仅次于复旦交大。虹口校区虽小但位置巨好，靠近五角场商圈。宿舍条件一般，六人间上下铺，但想想在上海市中心能住学校宿舍已经不错了。食堂绿叶餐厅的葱油拌面是一绝。就业太强了，券商基金银行大批去。",
     "tags": ["就业无忧", "内卷严重", "校园荒凉"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"bunk_bed": True, "over_6_room": True, "small_campus": True}},
    {"major": "会计学", "comment": "上财会计全国顶尖，四大会计师事务所校招重镇。校区小但精致，位置好在市区。宿舍条件一般但上海211都这样。食堂选择不多但味道还行。就业是最大亮点，上财在上海金融圈校友太多了。就是学业压力很大。",
     "tags": ["就业无忧", "内卷严重", "电梯便利"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"bunk_bed": True, "small_campus": True}},
    {"major": "经济学", "comment": "上财经济学院学术氛围浓。学校在虹口区，出门就是大学路和五角场。宿舍条件偏旧但生活便利。上财最大的优势是就业，每年校招季名企扎堆。就是学校小了点，从宿舍到教室五分钟走完。",
     "tags": ["就业无忧", "内卷严重", "电梯便利"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"bunk_bed": True, "small_campus": True, "hard_course_select": True}},
    {"major": "财务管理", "comment": "上财财务专业就业率极高。学校虽小但地理位置无敌，五角场吃喝玩乐应有尽有。宿舍确实一般但习惯了。教学实用性强，很多老师有业界背景。上海金融企业看上财的牌子。",
     "tags": ["就业无忧", "电梯便利", "内卷严重"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"bunk_bed": True, "small_campus": True}},
]

# 36 上海外国语大学 (语言, 211)
SCHOOL_REVIEWS[36] = [
    {"major": "英语", "comment": "上外英语专业实力强劲。松江校区建筑很有特色，各国风格的教学楼。宿舍四人间有空调。食堂的泰晤士餐厅很有情调。学校小而精，语言氛围浓厚。就业方面，外企、翻译、教育行业都很认上外牌子。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True}},
    {"major": "翻译", "comment": "上外高翻全国顶尖，联合国合作项目多。松江校区环境优美，图书馆像宫殿。宿舍条件中规中矩。食堂各国美食窗口很有特色。就业面广，外交部、大型会议口译、跨国公司都是出路。上外人语言能力真是没得说。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "日语", "comment": "上外日语专业很强，日企就业有优势。松江校区建筑风格各国风情，日式庭院拍照打卡热门。宿舍空调独卫都有。食堂日料窗口做得挺地道。日本交换项目丰富。就是松江到市区远了点。",
     "tags": ["校园巨美", "老师超好", "社团丰富"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True}},
]

# 37 华东理工大学 (理工, 211)
SCHOOL_REVIEWS[37] = [
    {"major": "化学工程与工艺", "comment": "华理化工全国顶尖，金山石化基地合作多。奉贤新校区宿舍条件很好，四人间上床下桌独卫。徐汇校区老但位置好。食堂一食堂的红烧肉很出名。就业方面化工行业和制药企业很认华理。奉贤虽然偏但环境好。",
     "tags": ["宿舍豪华", "老师超好", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "remote_location": True}},
    {"major": "计算机科学与技术", "comment": "华理计算机在上海211里不错。奉贤校区虽然偏但宿舍条件好，四人上床下桌。徐汇校区旧些但市口好。校园网还可以。就业方面上海互联网和制造业都认华理牌子。就是奉贤进城太远了。",
     "tags": ["宿舍豪华", "WiFi飞起", "校园荒凉"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "remote_location": True}},
    {"major": "材料科学与工程", "comment": "华理材料在上海有特色。奉贤新校区宿舍条件绝对一流，独立卫浴新装修。食堂选择多价格实惠。就业方面化工材料类企业很认可。就是奉贤海湾旅游区太偏了，进市区实习两小时通勤。",
     "tags": ["宿舍豪华", "空调自由", "就业困难"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "high", "environment": "low", "employment": "mid", "admin": "mid", "mental": "mid"},
     "variations": {"remote_location": True, "no_transit": True}},
]

# 38 上海大学 (综合, 211)
SCHOOL_REVIEWS[38] = [
    {"major": "计算机科学与技术", "comment": "上大计算机在宝山校区，校园超大，有泮池和草坪。宿舍四人间有空调。食堂选择多，益新尔美山明水秀四大餐厅各有特色。上大政策灵活，可以跨专业选课。就业在上海本地认可度不错，互联网企业校招都有。",
     "tags": ["校园巨美", "食堂神仙", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"small_campus": False}},
    {"major": "金融学", "comment": "上大经济学院发展很快。宝山校区很大，有校内巴士。宿舍四人上床下桌有空调。食堂选择多，水秀和山明的石锅饭很赞。上海大学在上海就业市场上认可度逐年提高，上海人眼中上大口碑好。",
     "tags": ["校园巨美", "食堂神仙", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "社会学", "comment": "上大社会学有底蕴，部分专业全国知名。宝山校区很美，泮池边黑天鹅很治愈。宿舍条件中上。上大推行三学期制，节奏快但灵活。就业方面考公和事业单位比较多。",
     "tags": ["校园巨美", "老师超好", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"bad_exam_schedule": True, "multi_campus": True}},
    {"major": "通信工程", "comment": "上大通信在宝山校区，实验室设备新。宿舍四人间有空调。学校环境非常好，适合学习。宝山虽然偏但是有地铁直达。就业方面上海通信和电子企业有校招，学校就业指导还算给力。",
     "tags": ["校园巨美", "空调自由", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True}},
]

# 39 东华大学 (理工, 211)
SCHOOL_REVIEWS[39] = [
    {"major": "服装与服饰设计", "comment": "东华服装设计全国顶尖！延安路校区在市中心，宿舍条件一般但位置无敌。食堂的浇头面很有名。东华的时尚活动超多，每年上海时装周都有东华人。就业方面服装行业和时尚圈很认可东华。",
     "tags": ["老师超好", "就业无忧", "电梯便利"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"bunk_bed": True, "small_campus": True}},
    {"major": "计算机科学与技术", "comment": "东华计算机在松江校区，校园很大风景好。松江宿舍四人间上床下桌有空调。食堂选择多，二楼风味餐厅不错。就是松江到市区远了点。就业方面IT和纺织信息化都有路子。",
     "tags": ["宿舍豪华", "校园巨美", "校园荒凉"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "remote_location": True}},
    {"major": "材料科学与工程", "comment": "东华材料以纺织材料为特色，国内独一份。松江校区环境好设施新，宿舍条件不错。食堂价格便宜量足。就业方面纺织化纤行业很认东华，新型材料企业也有需求。",
     "tags": ["宿舍豪华", "校园巨美", "老师超好"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "high", "environment": "high", "employment": "mid", "admin": "mid", "mental": "mid"},
     "variations": {"multi_campus": True, "remote_location": True}},
]

# 40 上海海洋大学 (农林, 普通)
SCHOOL_REVIEWS[40] = [
    {"major": "水产养殖学", "comment": "上海海洋水产养殖全国第一。临港新校区很新很漂亮，宿舍四人间上床下桌空调独卫。食堂的海鲜窗口新鲜又便宜。就是临港离市区太远了，但16号线通了后方便一些。就业方面水产和海洋相关企业很认。",
     "tags": ["宿舍豪华", "食堂神仙", "校园巨美"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True}},
    {"major": "食品科学与工程", "comment": "上海海洋食品专业不错。临港校区设施新，住宿条件上海普通院校里算好的。大学生活费不高，食堂便宜。学校以海洋为特色，相关学科有优势。就业方面食品检测和海洋相关单位有出路。",
     "tags": ["宿舍豪华", "食堂神仙", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "high", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True}},
    {"major": "计算机科学与技术", "comment": "海洋大学计算机偏向海洋信息化方向。临港校区住宿好，有独卫空调。校园环境好空气清新。虽然学校不是重点，但在临港这个区域算是最好的学校了。就业可以往IT方向走，就是名气一般。",
     "tags": ["宿舍豪华", "校园巨美", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "low", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True, "low_recognition": True}},
]

# 41 上海理工大学 (理工, 普通)
SCHOOL_REVIEWS[41] = [
    {"major": "机械工程", "comment": "上理工机械有底蕴。军工路校区在杨浦，靠近复兴岛。宿舍条件一般，六人间上下铺有空调。食堂还行，思餐厅的麻辣香锅是招牌。学校不大但工科氛围浓。就业上海本地制造企业有校招。",
     "tags": ["空调自由", "食堂神仙", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"bunk_bed": True, "small_campus": True}},
    {"major": "光学工程", "comment": "上理工光学在全国有知名度。军工路校区不大但紧邻黄浦江。宿舍六人间上下铺条件一般。学校学习氛围尚可。就业方面光学和仪器仪表企业有对口，上海的制造业就业机会还是比较多的。",
     "tags": ["老师超好", "空调自由", "就业困难"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "mid"},
     "variations": {"bunk_bed": True}},
    {"major": "计算机科学与技术", "comment": "上理工计算机在上海普通院校里中等偏上。学校在杨浦区，靠近五角场。宿舍条件一般但周围吃喝玩乐方便。就业主要靠个人能力，上海IT市场机会多。学校确实不够有名，但好在有地域优势。",
     "tags": ["电梯便利", "佛系养身", "就业困难"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "low", "admin": "mid", "mental": "mid"},
     "variations": {"bunk_bed": True, "low_recognition": True}},
]

# 42 上海师范大学 (师范, 普通)
SCHOOL_REVIEWS[42] = [
    {"major": "教育学", "comment": "上师大是上海中小学教师主要来源之一。徐汇校区在桂林路，位置不错。宿舍四人间有空调。食堂的香锅和酸菜鱼很受欢迎。就业方面当老师非常稳，上海的中小学对上师大毕业生很认可。",
     "tags": ["老师超好", "就业无忧", "食堂神仙"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "汉语言文学", "comment": "上师大中文系底蕴不错。奉贤校区远但宿舍新，徐汇市区方便但宿舍旧。学校师范类氛围浓。就业当语文老师很稳。上海师范类本科就业率一直不错。就是奉贤校区太远了。",
     "tags": ["老师超好", "就业无忧", "校园荒凉"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "remote_location": True}},
    {"major": "心理学", "comment": "上师大应用心理学在师范类有特色。徐汇校区位置好，校园有历史感。宿舍条件校区不同差异大。学校对师范生培养用心。就业方面中小学心理老师和教育机构是主要去向。",
     "tags": ["老师超好", "校园巨美", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 43 上海中医药大学 (医药, 双一流)
SCHOOL_REVIEWS[43] = [
    {"major": "中医学", "comment": "上中医在浦东张江，药谷核心区。宿舍条件不错，四人间有空调。食堂有药膳窗口很养生。学术资源丰富，附属医院多。学中医真的要背很多经典，考试月很痛苦但值得。就业方面中医院和养生机构都抢着要。",
     "tags": ["老师超好", "食堂神仙", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"forced_study": True}},
    {"major": "药学", "comment": "上中医药学偏向中药方向。张江校区环境好，实验室设备新。宿舍条件可以。食堂药膳是特色。就业方面中药企业、药监局和医院药剂科都有。学校虽是双一流但声誉不错。",
     "tags": ["老师超好", "食堂神仙", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "mid"},
     "variations": {"remote_location": True}},
]

# 44 上海音乐学院 (艺术, 普通)
SCHOOL_REVIEWS[44] = [
    {"major": "音乐表演", "comment": "上音是中国音乐最高学府之一。汾阳路校区在市中心，位置绝佳。宿舍老校区条件一般但学音乐的更在乎琴房。琴房条件很好，施坦威钢琴随便练。淮海路旁边，文化氛围浓厚。就业方面各大乐团和音乐学院抢着要。",
     "tags": ["老师超好", "电梯便利", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "low", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"small_campus": True, "bunk_bed": True}},
    {"major": "音乐表演", "comment": "上音师资力量太强了，很多国际大师。老校区虽然小但地理位置好，出门就是淮海路。宿舍确实比较老，但学艺术的不太计较这些。上音的名气在音乐界就是金字招牌，毕业不愁出路。",
     "tags": ["老师超好", "电梯便利", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "low", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"small_campus": True, "bunk_bed": True, "expensive_food": True}},
]

# 241 上海体育大学 (体育, 双一流)
SCHOOL_REVIEWS[241] = [
    {"major": "体育教育", "comment": "上海体育大学在杨浦区长海路。体育设施全国一流，有国家级训练基地。宿舍条件中规中矩。食堂运动员伙食标准高。上体的运动康复和体育教育专业很强。就业方面体育老师和健身行业都抢手。",
     "tags": ["老师超好", "校园巨美", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"bunk_bed": True, "poor_facilities": True, "forced_run": False}},
    {"major": "体育教育", "comment": "上体是中国体育类院校中的佼佼者。绿瓦大楼是上海地标建筑。运动设施全国顶尖，游泳馆健身房随便用。就业很稳，上海体育局和中小学体育老师都认上体。就是宿舍条件一般。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"bunk_bed": True, "has_curfew": True}},
]

# ==================== 浙江 ====================

# 76 浙江大学 (综合, 985/211)
SCHOOL_REVIEWS[76] = [
    {"major": "计算机科学与技术", "comment": "浙大计算机全国前三。紫金港校区条件超好，宿舍四人间上床下桌有空调，新宿舍楼甚至带电梯。亚洲第二大食堂不是吹的，风味餐厅和休闲餐厅选择太多。玉泉校区老但学术氛围浓。就业方面阿里网易就在旁边，太方便了。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "high", "admin": "high", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "经济学", "comment": "浙大经济学院发展很快。紫金港宿舍条件极好，新装的空调给力。食堂选择太多四年都吃不完，大西区新食堂更赞。学术资源丰富，出国交换机会多。就业方面杭州金融和互联网圈浙大校友太多了。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "high", "admin": "high", "mental": "high"},
     "variations": {"hard_course_select": True, "multi_campus": True}},
    {"major": "临床医学", "comment": "浙大医学院全国前列。紫金港校区住宿好，食堂好吃。华家池校区老但学术传统深厚。学业压力巨大，医学生考试月天天通宵。附属浙一浙二医院是顶级医院，实习资源好。就业完全不愁。",
     "tags": ["宿舍豪华", "食堂神仙", "内卷严重"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"multi_campus": True, "bad_exam_schedule": True}},
    {"major": "机械工程", "comment": "浙大机械实力很强。玉泉校区虽然老但学术氛围浓厚。宿舍条件玉泉不如紫金港，但紫金港新宿舍很好。食堂太多太好吃了，浙大真是被学术耽误的美食大学。就业长三角制造业龙头随便选。",
     "tags": ["食堂神仙", "就业无忧", "老师超好"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "软件工程", "comment": "浙大软件在玉泉校区，靠近阿里网易。宿舍玉泉老些但紫金港新宿舍很香。食堂亚洲第二大名副其实。就业率几乎100%，杭州互联网大厂的黄埔军校。就是校内太卷了，人人都是卷王。",
     "tags": ["食堂神仙", "内卷严重", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "high", "admin": "high", "mental": "mid"},
     "variations": {"multi_campus": True, "hard_course_select": True}},
]

# 77 浙江工业大学 (理工, 普通)
SCHOOL_REVIEWS[77] = [
    {"major": "计算机科学与技术", "comment": "浙工大计算机在浙江省内普通院校里算强的。屏峰校区环境好，宿舍四人间空调独卫。食堂家和堂的麻辣香锅很赞。就业杭州IT企业校招时浙工大是主力目标，阿里网易都有工大校友。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True}},
    {"major": "化学工程与工艺", "comment": "浙工大化工是传统强项，浙江省化工人才主要来源。屏峰校区宿舍条件不错有空调。食堂便宜好吃。学校在杭州，实习就业机会多。化工企业每年校招首选浙工大。",
     "tags": ["老师超好", "就业无忧", "宿舍豪华"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "机械工程", "comment": "浙工大机械在省内不错。屏峰校区环境优美，宿舍条件好。食堂家和堂选择丰富。学校在杭州地理位置好，实习机会多。就业方面省内制造业和机械企业很认可工大学生。",
     "tags": ["宿舍豪华", "校园巨美", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "软件工程", "comment": "浙工大软件学院在杭州就业很好。学校环境好，宿舍条件好有独卫。杭州互联网氛围浓厚，实习机会多。虽然不是211但浙工大在浙江就业竞争力很强，很多学长去了大厂。",
     "tags": ["宿舍豪华", "就业无忧", "WiFi飞起"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"hard_course_select": True}},
]

# 78 浙江师范大学 (师范, 普通)
SCHOOL_REVIEWS[78] = [
    {"major": "教育学", "comment": "浙师大在金华，虽然不在杭州但在浙江省内师范类排名第一。宿舍四人间空调独卫条件不错。食堂的菜很便宜，一天20块能吃饱。校园很大，初阳湖挺美。就业方面浙江中小学教师很大一部分来自浙师大。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "汉语言文学", "comment": "浙师大中文系在省内有口碑。金华校区校园很美，图文信息中心很气派。宿舍新楼条件好。食堂便宜大碗。当语文老师的话浙师大的牌子在浙江很好使，各地教育局校招必来。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "数学与应用数学", "comment": "浙师大数学在浙江省内很强。学校环境好性价比高。宿舍条件中上。学费低生活费便宜。当数学老师的话浙师大毕业生在浙江中小学很受欢迎，就业率很高。",
     "tags": ["老师超好", "就业无忧", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 79 宁波大学 (综合, 双一流)
SCHOOL_REVIEWS[79] = [
    {"major": "经济学", "comment": "宁大在宁波江北，校园很大环境好。宿舍四人间空调独卫。食堂选择多，甬江餐厅的宁波汤圆是特色。双一流身份让宁大的认可度提升不少。就业方面宁波本地企业很认宁大，去杭州上海的也不少。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
    {"major": "临床医学", "comment": "宁大医学院发展快。附属宁波一院和李惠利医院实习资源好。宿舍条件不错。校园靠近甬江，环境宜人。宁波虽然不如一线城市大，但生活舒适。就业宁波各大医院都有宁大校友。",
     "tags": ["宿舍豪华", "老师超好", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "mid"},
     "variations": {"bad_exam_schedule": True}},
    {"major": "计算机科学与技术", "comment": "宁大计算机在双一流身份加持下发展不错。校园绿化好，白鹭林是特色。宿舍有空调独卫。宁波IT企业虽然不如杭州多但也在增长。就业方向本地企业为主。",
     "tags": ["宿舍豪华", "校园巨美", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 80 杭州电子科技大学 (理工, 普通)
SCHOOL_REVIEWS[80] = [
    {"major": "计算机科学与技术", "comment": "杭电计算机在浙江普通院校里顶尖，IT氛围浓厚。下沙校区宿舍四人间空调独卫。食堂三楼美食广场选择多。杭电在杭州IT圈口碑好，华为每年校招定点来杭电。ACM竞赛成绩亮眼。",
     "tags": ["宿舍豪华", "就业无忧", "WiFi飞起"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"hard_course_select": True}},
    {"major": "软件工程", "comment": "杭电软件学院实力强，就业率接近98%。下沙校区生活方便，宿舍条件好。食堂三楼可以点菜聚餐。在杭州就业市场杭电计算机类比很多211还好使，大厂实习机会多。",
     "tags": ["宿舍豪华", "就业无忧", "老师超好"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"hard_course_select": True, "bad_exam_schedule": True}},
    {"major": "电子信息工程", "comment": "杭电电子信息是传统强项。下沙校区在钱塘江边，环境不错。宿舍有空调独卫。实验室设备好，竞赛氛围浓。就业杭州电子类企业首选杭电，海康大华每年大批招人。",
     "tags": ["宿舍豪华", "老师超好", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"remote_location": True}},
]

# 81 浙江工商大学 (财经, 普通)
SCHOOL_REVIEWS[81] = [
    {"major": "金融学", "comment": "浙工商金融在浙江财经类院校里不错。下沙校区宿舍四人间空调独卫。食堂行云流水的菜品和流水的美食坊很有名。学校管理比较人性化。就业方面银行和证券公司在浙江招人，浙工商是重点目标。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
    {"major": "会计学", "comment": "浙工商会计专业省内知名，四大会计师事务所每年校招。下沙校区宿舍条件好。食堂选择丰富，流水苑的南昌拌粉一绝。就业在杭州金融业认可度高。学校虽然普通但财经特色突出。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"hard_course_select": True}},
    {"major": "经济学", "comment": "浙工商经济学院师资不错。下沙校园很大，有鸽子广场。宿舍有空调独卫条件好。食堂便宜味道好。就业方面考公有优势，浙江选调生很多浙工商毕业生。",
     "tags": ["宿舍豪华", "校园巨美", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
]

# 82 温州大学 (综合, 普通)
SCHOOL_REVIEWS[82] = [
    {"major": "汉语言文学", "comment": "温大在温州瓯海，校园环境不错。宿舍四人间有空调。食堂的温州特色小吃很好吃。温大在温州本地就业不错，当老师和考公是主要方向。学校虽然名气不太大但学习氛围尚可。",
     "tags": ["食堂神仙", "佛系养身", "老师超好"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
    {"major": "化学", "comment": "温大化学有特色学科。校园在茶山高教园区，环境好空气清新。宿舍条件中上。温州创业氛围浓厚，学校也鼓励创新创业。就业方向化工和材料类企业为主。",
     "tags": ["校园巨美", "老师超好", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "low", "admin": "mid", "mental": "mid"},
     "variations": {}},
]

# 83 浙江理工大学 (理工, 普通)
SCHOOL_REVIEWS[83] = [
    {"major": "纺织工程", "comment": "浙理工纺织全国有名。下沙校区宿舍四人间空调独卫。食堂桂花园的煲仔饭很香。学校以纺织服装为特色，相关专业就业好。在杭州地理位置不错，实习机会多。",
     "tags": ["宿舍豪华", "老师超好", "食堂神仙"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True}},
    {"major": "计算机科学与技术", "comment": "浙理工计算机在省内还可以。下沙校区设施新，住宿好。学校工科氛围不错。就业杭州IT企业有校招，但和浙工大杭电比稍弱一些。好在杭州互联网市场大，机会不缺。",
     "tags": ["宿舍豪华", "就业无忧", "WiFi飞起"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"hard_course_select": True}},
    {"major": "设计学", "comment": "浙理工设计学院以服装设计为特色，业内知名。下沙校区宿舍条件好。学校艺术氛围浓，时装秀很多。就业服装和时尚行业很认可浙理工，杭州女装企业很多理工校友。",
     "tags": ["宿舍豪华", "社团丰富", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
]

# 212 浙江中医药大学 (医药, 普通)
SCHOOL_REVIEWS[212] = [
    {"major": "中医学", "comment": "浙中医在杭州滨江，校园不大但精致。宿舍四人间空调独卫。食堂药膳窗口有特色。学医很辛苦，背经典背方剂考试压力大。附属浙江省中医院实习条件好。就业浙江中医类医院认浙中医牌子。",
     "tags": ["老师超好", "食堂神仙", "内卷严重"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "mid"},
     "variations": {"forced_study": True}},
    {"major": "临床医学", "comment": "浙中医的西医结合专业有特色。滨江校区靠近钱塘江，环境好。宿舍条件不错。学医确实累但很有成就感。就业浙江省内医院认浙中医，就是竞争也激烈。",
     "tags": ["老师超好", "宿舍豪华", "内卷严重"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "mid"},
     "variations": {"bad_exam_schedule": True}},
]

# 213 温州医科大学 (医药, 普通)
SCHOOL_REVIEWS[213] = [
    {"major": "临床医学", "comment": "温医大眼视光全国第一！茶山校区在温州瓯海，环境好。宿舍四人间空调独卫。学医真的苦但眼视光是王牌专业，毕业去眼科医院直接抢人。食堂味道还行价格适中。",
     "tags": ["老师超好", "就业无忧", "宿舍豪华"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"forced_study": True}},
    {"major": "药学", "comment": "温医大药学有特色。校园环境不错，在茶山脚下。宿舍条件中上。附属医院实习条件好。就业方面温州医药企业和医院药房有需求。学医类学校整体学业压力大但出路好。",
     "tags": ["老师超好", "校园巨美", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "mid"},
     "variations": {"bad_exam_schedule": True}},
]

# 259 浙江海洋大学 (农林, 普通)
SCHOOL_REVIEWS[259] = [
    {"major": "水产养殖学", "comment": "浙海大在舟山定海，海洋特色鲜明。宿舍有空调独卫，海景房不是梦。食堂海鲜新鲜又便宜。学校以海洋学科为核心，水产和海洋科学在华东有名。就业浙江海洋渔业和水产企业有对口。",
     "tags": ["宿舍豪华", "食堂神仙", "校园巨美"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True}},
    {"major": "食品科学与工程", "comment": "浙海大食品偏海洋食品方向。舟山环境优美空气清新，适合学习。宿舍条件不错有空调。食堂海鲜便宜。就业方面海洋食品加工和质检企业有需求。就是舟山离大陆远了点。",
     "tags": ["宿舍豪华", "食堂神仙", "校园巨美"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True}},
]

# 260 浙江科技大学 (理工, 普通)
SCHOOL_REVIEWS[260] = [
    {"major": "计算机科学与技术", "comment": "浙科大（原名浙江科技学院）在小和山，环境清幽。宿舍条件不错有空调。食堂一般。学校以应用型人才培养为主。就业杭州IT企业有校招，但学校知名度有待提高。",
     "tags": ["宿舍豪华", "校园巨美", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "low", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True, "low_recognition": True}},
    {"major": "机械工程", "comment": "浙科大机械应用型强。小和山环境好适合读书。宿舍条件中上。学校德国合作项目有特色。就业浙江制造业企业有校招，就是竞争激烈。",
     "tags": ["校园巨美", "老师超好", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "low", "admin": "mid", "mental": "mid"},
     "variations": {"remote_location": True}},
]

# 261 湖州师范学院 (师范, 普通)
SCHOOL_REVIEWS[261] = [
    {"major": "教育学", "comment": "湖师院在湖州，校园不大但温馨。宿舍四人间空调独卫。食堂便宜好吃，湖州馄饨很有名。师范类专业是主打，浙江中小学教师来源之一。湖州生活节奏慢适合读书。",
     "tags": ["宿舍豪华", "食堂神仙", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
    {"major": "汉语言文学", "comment": "湖师院中文系培养中小学语文老师为主。学校环境清幽，学习氛围好。宿舍条件不错有空调。学费便宜，性价比高。就业当老师很稳，湖州及周边中小学都来校招。",
     "tags": ["老师超好", "佛系养身", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
]

# 298 绍兴文理学院 (综合, 普通)
SCHOOL_REVIEWS[298] = [
    {"major": "汉语言文学", "comment": "绍兴文理在绍兴市区，鲁迅故里旁边文化氛围浓。宿舍四人间有空调。食堂的绍兴臭豆腐和梅干菜扣肉很正宗。师范类是传统强项。就业绍兴及周边中小学老师为主，生活成本低。",
     "tags": ["食堂神仙", "校园巨美", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
    {"major": "会计学", "comment": "绍兴文理学院经管专业不错。校园有江南水乡特色。宿舍条件尚可有空调。绍兴本地企业校招多。学校虽然不是重点但在绍兴及浙东地区就业有基础。",
     "tags": ["校园巨美", "佛系养身", "老师超好"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
]

# 299 台州学院 (综合, 普通)
SCHOOL_REVIEWS[299] = [
    {"major": "小学教育", "comment": "台州学院在临海和椒江两个校区。宿舍四人间空调独卫。食堂便宜量大。师范类毕业生台州中小学欢迎。学校虽然不是名牌但在台州本地就业认可度不错，生活成本低。",
     "tags": ["宿舍豪华", "佛系养身", "食堂神仙"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "high", "cost": "high", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "机械工程", "comment": "台州学院工科服务台州制造业。椒江校区设施较新。宿舍条件不错。台州民营经济活跃，实习机会较多。就业方面本地制造企业校招多。学校虽普通但在台州够用。",
     "tags": ["宿舍豪华", "佛系养身", "就业困难"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "low", "admin": "mid", "mental": "mid"},
     "variations": {"multi_campus": True}},
]

# 300 丽水学院 (综合, 普通)
SCHOOL_REVIEWS[300] = [
    {"major": "教育学", "comment": "丽水学院在丽水莲都，山清水秀空气好。宿舍四人间空调独卫。食堂便宜实惠。丽水生活节奏慢，适合安心读书。师范类毕业生在浙西南地区当老师很稳。",
     "tags": ["宿舍豪华", "校园巨美", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True}},
    {"major": "汉语言文学", "comment": "丽水学院中文系培养语文老师为主。学校在瓯江边环境优美。宿舍条件不错有空调。生活成本很低。就业丽水及周边地区中小学有校招。学校名气虽不大但当地认可度好。",
     "tags": ["校园巨美", "佛系养身", "老师超好"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True}},
]

# ==================== 江苏 ====================

# 59 南京大学 (综合, 985/211)
SCHOOL_REVIEWS[59] = [
    {"major": "计算机科学与技术", "comment": "南大计算机在华东很强，人工智能方向顶尖。仙林校区宿舍四人间上床下桌独立卫浴，条件一流。食堂六食堂的煲仔饭和九食堂的麻辣香锅是招牌。鼓楼校区老但有底蕴。就业方面BAT华为每年大批招，南京软件谷好去处。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "high", "admin": "high", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "经济学", "comment": "南大经济学院学术能力强。仙林校区宿舍条件好，四人上床下桌独卫。食堂选择多，四五六食堂各有特色。校园超大，杜厦图书馆是南大标志。就业方面投行咨询都有南大人，长三角认可度极高。",
     "tags": ["宿舍豪华", "图书馆霸位", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "high", "admin": "high", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "物理学", "comment": "南大物理全国顶尖，有国家重点实验室。仙林宿舍好，鼓楼老宿舍旧些。校园风景好，仙林安静适合做科研。学术氛围浓厚，出国深造比例高。就业学术界和半导体企业都认南大物理。",
     "tags": ["宿舍豪华", "校园巨美", "老师超好"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "high", "admin": "high", "mental": "high"},
     "variations": {"multi_campus": True, "hard_course_select": True}},
    {"major": "软件工程", "comment": "南大软件学院就业非常好。仙林校区条件极好，宿舍独卫空调。食堂选择太多，每天都纠结吃什么。南京IT企业聚集，实习机会多。南大在长三角就业简直就是王者。",
     "tags": ["宿舍豪华", "就业无忧", "食堂神仙"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"hard_course_select": True}},
]

# 60 东南大学 (理工, 985/211)
SCHOOL_REVIEWS[60] = [
    {"major": "土木工程", "comment": "东南土木全国第一。九龙湖校区宿舍四人间上床下桌独卫空调，条件很好。食堂桃园和橘园餐厅都不错。四牌楼校区老校区非常有民国风情，梧桐大道太美了。就业设计院和地产公司抢着要。",
     "tags": ["宿舍豪华", "校园巨美", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "bad_exam_schedule": True}},
    {"major": "计算机科学与技术", "comment": "东南计算机近年来发展迅猛。九龙湖校区宿舍条件好，新宿舍有电梯。食堂选择多，桃园餐厅的牛肉面不错。学校很大需要骑车。就业长三角IT企业很认东南牌子，华为中兴定点招。",
     "tags": ["宿舍豪华", "就业无忧", "WiFi飞起"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "remote_location": True}},
    {"major": "建筑学", "comment": "东南建筑全国前三，老四校之一。四牌楼校区太美了，中央大道像是欧洲。宿舍老校区条件一般但九龙湖新校区好。学建筑通宵画图是常态。就业建筑设计院和地产公司都认东南建筑。",
     "tags": ["校园巨美", "老师超好", "内卷严重"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"multi_campus": True, "bad_exam_schedule": True}},
    {"major": "电子信息工程", "comment": "东南电子在射频和毫米波方向全国领先。九龙湖校区设施新。宿舍条件好，四人上床下桌。就业华为中兴每年在东南招很多人，通信行业校友遍布。",
     "tags": ["宿舍豪华", "就业无忧", "老师超好"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 61 南京航空航天大学 (理工, 211)
SCHOOL_REVIEWS[61] = [
    {"major": "航空航天工程", "comment": "南航航空航天特色鲜明，御风园飞机真机展示。将军路校区宿舍四人间空调独卫。食堂翠屏和慧园餐厅不错。明故宫校区老但在市中心。就业航天科工和中航工业大量招南航毕业生。",
     "tags": ["老师超好", "就业无忧", "校园巨美"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "计算机科学与技术", "comment": "南航计算机在211里不错。将军路校区大，宿舍条件好。食堂还行。南航在南京IT就业市场认可度高，华为中兴每年都来。学校航空航天背景也有特色。",
     "tags": ["宿舍豪华", "就业无忧", "校园巨美"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "机械工程", "comment": "南航机械有航空航天特色。将军路校区设施新，宿舍条件好。学校有飞行器真机展示很酷。就业航空航天企业首选南航，薪资待遇好。就是课业负担比较重。",
     "tags": ["宿舍豪华", "老师超好", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"multi_campus": True}},
]

# 62 南京理工大学 (理工, 211)
SCHOOL_REVIEWS[62] = [
    {"major": "计算机科学与技术", "comment": "南理工计算机在江苏211里强势。孝陵卫校区在紫金山脚下，环境好。宿舍四人间空调独卫条件中上。食堂明苑的煲仔饭和二三食堂不错。就业方面军工背景有优势，互联网大厂也认。",
     "tags": ["校园巨美", "就业无忧", "老师超好"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "材料科学与工程", "comment": "南理工材料有兵器特色。校园在紫金山麓，二月兰花海是南理工名片。宿舍条件中上。食堂总有几个窗口排队很长。就业军工系统和材料企业很认南理工。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "自动化", "comment": "南理工自动化在军工领域有优势。孝陵卫校区位置好，靠近中山陵。宿舍条件中上。食堂饭菜实惠。就业方面军工企业和自动化公司都有需求。",
     "tags": ["校园巨美", "就业无忧", "空调自由"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
]

# 63 苏州大学 (综合, 211)
SCHOOL_REVIEWS[63] = [
    {"major": "临床医学", "comment": "苏大医学院在江苏实力强，附属医院多。天赐庄校区本部在古城里，建筑美得像园林。宿舍条件分校区，独墅湖新校区条件好。食堂方塔的烤鸭泡饭是经典。苏州城市宜居，就业苏南各大医院抢着要。",
     "tags": ["校园巨美", "食堂神仙", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "bad_exam_schedule": True}},
    {"major": "计算机科学与技术", "comment": "苏大计算机发展很快。独墅湖校区宿舍条件好，有独卫空调。校园像大公园。苏州工业园区IT企业多，实习方便。就业长三角IT市场苏大牌子好使。",
     "tags": ["校园巨美", "宿舍豪华", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "法学", "comment": "苏大王健法学院有底蕴。天赐庄校区太美了，红砖建筑像哈利波特城堡。宿舍独墅湖新校区条件好。苏州经济发达法律市场大。就业长三角律所和法检系统认苏大。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "金融学", "comment": "苏大金融在苏州就业很好。独墅湖校区环境好设施新。苏州工业园区金融企业集聚。实习机会多。虽然不是985但苏大在长三角认可度很高，江苏考生心中的好学校。",
     "tags": ["宿舍豪华", "校园巨美", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 64 河海大学 (理工, 211)
SCHOOL_REVIEWS[64] = [
    {"major": "水利工程", "comment": "河海水利全国第一，没有之一。西康路校区在鼓楼，位置好。宿舍条件一般，六人间上下铺。食堂还行，水利馆旁的餐厅推荐。就业水利部、各大水利设计院点名要河海的。江宁校区设施更新。",
     "tags": ["老师超好", "就业无忧", "宿舍破旧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "bunk_bed": True}},
    {"major": "计算机科学与技术", "comment": "河海计算机在南京211里中等。江宁校区宿舍条件好，四人间独卫空调。食堂新食堂不错。学校水利信息化方向有特色。就业互联网也有但不如水利对口行业稳。",
     "tags": ["宿舍豪华", "就业无忧", "校园荒凉"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "remote_location": True}},
    {"major": "土木工程", "comment": "河海土木有水利背景。江宁校区新宿舍条件好。食堂选择多。就业方面中建中铁每年大批招河海土木毕业生。虽然比不上东南同济的土木，但性价比很高。",
     "tags": ["宿舍豪华", "就业无忧", "老师超好"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"multi_campus": True}},
]

# 65 中国矿业大学 (理工, 211)
SCHOOL_REVIEWS[65] = [
    {"major": "采矿工程", "comment": "矿大在徐州，采矿全国第一。南湖校区宿舍条件超好，四人间上床下桌空调独卫，徐州高校里最好的宿舍之一。食堂很多，桃苑餐厅的米线一绝。就业煤炭和矿业央企国企稳定铁饭碗。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True}},
    {"major": "计算机科学与技术", "comment": "矿大计算机在徐州不错。南湖校区校园超大，环境优美。宿舍条件极好。食堂便宜好吃。就业互联网大厂有校招但不如一线城市学校方便。好在211牌子硬，校友在行业里多。",
     "tags": ["宿舍豪华", "校园巨美", "食堂神仙"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True}},
    {"major": "机械工程", "comment": "矿大机械有矿业特色。南湖校区是新校区，设施一流。宿舍条件好得不像211。食堂便宜大碗。就业徐工集团和各大工程机械企业很认矿大。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True}},
]

# 66 南京师范大学 (师范, 211)
SCHOOL_REVIEWS[66] = [
    {"major": "教育学", "comment": "南师大教育学前全国前列。随园校区太美了，东方最美校园名不虚传。宿舍随园老校区条件一般，仙林新校区好很多。食堂的鸭血粉丝汤很正宗。就业江苏中小学教师主力来源，南师大在江苏就业无敌。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "汉语言文学", "comment": "南师大中文系百年底蕴。随园校区金陵女子大学旧址太美了。宿舍条件分校区，仙林好随园旧。食堂东区的麻辣香锅好吃。就业当语文老师南师大是江苏省第一选择。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True, "bunk_bed": True}},
    {"major": "心理学", "comment": "南师大心理学院在师范类中有特色。仙林校区宿舍条件好。随园校区有历史味道。就业中小学心理老师和教育咨询是主流。南师大牌子在江苏省教育系统非常好用。",
     "tags": ["校园巨美", "老师超好", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 67 江南大学 (综合, 211)
SCHOOL_REVIEWS[67] = [
    {"major": "食品科学与工程", "comment": "江南大学食品科学全国第一！无锡蠡湖校区校园太美了，有小桥流水。宿舍四人间空调独卫。食堂二食堂的酱排骨和四食堂的馄饨好吃到哭。就业食品行业龙头企业和质检机构抢着要江南大学毕业生。",
     "tags": ["校园巨美", "食堂神仙", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {}},
    {"major": "计算机科学与技术", "comment": "江南大学计算机在211里中等偏上。蠡湖校区环境优美，曲水流觞的设计很有特色。宿舍条件好。食堂太好吃了，江南大学是干饭人的天堂。就业长三角IT企业认江南大学211牌子。",
     "tags": ["校园巨美", "食堂神仙", "宿舍豪华"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
    {"major": "设计学", "comment": "江南大学设计学院全国闻名，工业设计很强。蠡湖校区环境激发设计灵感。宿舍条件好。就业设计公司和互联网大厂设计部都有江南大学人。无锡宜居，生活舒适。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {}},
]

# 68 南京农业大学 (农林, 211)
SCHOOL_REVIEWS[68] = [
    {"major": "农学", "comment": "南农农学全国领先。卫岗校区在紫金山南，环境好。宿舍四人间空调独卫。食堂的南农烧鸡和酸奶是南京人的回忆。就业农业科研院所和种业企业抢着要。学校学术氛围朴实。",
     "tags": ["食堂神仙", "老师超好", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "食品科学与工程", "comment": "南农食品科学很强。卫岗校区位置好，靠近中山陵。宿舍条件中上。食堂南农烧鸡和酸奶是金字招牌。就业食品行业认可度很高。211农学类院校里南农性价比很高。",
     "tags": ["食堂神仙", "就业无忧", "校园巨美"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "动物医学", "comment": "南农动医是王牌专业。学校环境好，宠物医院实习机会多。宿舍条件中上。食堂便宜好吃。就业宠物医院和畜牧企业很缺南农毕业生，就业率高。",
     "tags": ["老师超好", "就业无忧", "食堂神仙"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 69 中国药科大学 (医药, 211)
SCHOOL_REVIEWS[69] = [
    {"major": "药学", "comment": "药大药学全国第一。江宁校区宿舍四人间空调独卫，条件好。食堂的吉祥馄饨和药膳窗口有特色。学术氛围非常好，实验课多到爆。就业制药企业和药监局抢着要药大人，就业率极高。",
     "tags": ["宿舍豪华", "老师超好", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"forced_study": True}},
    {"major": "临床医学", "comment": "药大临床药学特色突出。江宁校区设施新，宿舍条件好。课业很重，考试月泡图书馆是常态。食堂药膳窗口养生。就业医院药剂科和药企临床部门急需药大人。",
     "tags": ["宿舍豪华", "内卷严重", "就业无忧"],
     "profile": {"academic": "high", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"forced_study": True, "bad_exam_schedule": True}},
]

# 70 南京邮电大学 (理工, 双一流)
SCHOOL_REVIEWS[70] = [
    {"major": "通信工程", "comment": "南邮通信在华东通信界有黄埔军校之称。仙林校区宿舍四人间空调独卫条件好。食堂选择多，一楼快餐实惠。南邮在通信行业校友遍布，华为中兴每年大招。就业率在江苏双一流里非常高。",
     "tags": ["宿舍豪华", "就业无忧", "老师超好"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "计算机科学与技术", "comment": "南邮计算机在双一流加持下越来越强。仙林校区宿舍好食堂多。南邮在IT圈校友众多，学长内推很方便。就业华为中兴小米每年定点招，薪资可观。",
     "tags": ["宿舍豪华", "就业无忧", "WiFi飞起"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"hard_course_select": True}},
    {"major": "电子信息工程", "comment": "南邮电子在通信领域有优势。仙林校区条件好。学校虽然偏但学习氛围浓。就业很好，通信电子企业校招南邮是必到站。就是女生少点，理工科院校通病。",
     "tags": ["宿舍豪华", "就业无忧", "内卷严重"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"multi_campus": True}},
]

# 71 南京信息工程大学 (理工, 双一流)
SCHOOL_REVIEWS[71] = [
    {"major": "大气科学", "comment": "南信大气象学全国第一。龙王山校区有气象雷达站。宿舍四人间空调独卫。食堂中苑新食堂很赞。中国气象局定点招人，就业不要太稳。双一流后学校发展加速。",
     "tags": ["老师超好", "就业无忧", "宿舍豪华"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "计算机科学与技术", "comment": "南信大计算机有气象信息化特色。校园很大，气象楼是标志。宿舍条件不错。食堂中苑新食堂干净好吃。就业除了气象信息化方向，互联网大厂也有校招。双一流身份提升了认可度。",
     "tags": ["宿舍豪华", "校园巨美", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
]

# 72 扬州大学 (综合, 普通)
SCHOOL_REVIEWS[72] = [
    {"major": "汉语言文学", "comment": "扬大中文系有底蕴。瘦西湖校区在景区里，上课路上都像在旅游。宿舍条件分校区荷花池好一些。食堂的扬州炒饭和狮子头很正宗。师范类专业就业不错，扬州及苏北当老师稳。",
     "tags": ["校园巨美", "食堂神仙", "老师超好"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "动物医学", "comment": "扬大动医在江苏知名。文汇路校区设施还行。宿舍条件一般。扬州生活节奏慢适合读书。就业江苏畜牧兽医系统很多扬大校友。",
     "tags": ["老师超好", "佛系养身", "校园巨美"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "经济学", "comment": "扬大经济学院规模大。学校综合性强跨学科选课方便。宿舍条件分校区。食堂扬大酸奶是一绝。就业苏中苏北地区企业校招多，性价比高。",
     "tags": ["食堂神仙", "佛系养身", "校园巨美"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 73 江苏大学 (综合, 普通)
SCHOOL_REVIEWS[73] = [
    {"major": "机械工程", "comment": "江大机械在镇江有传统优势。校园很大，图书馆很气派。宿舍四人间空调独卫条件不错。食堂一食堂的锅盖面正宗。就业长三角制造企业有校招。江大虽然不是211但在江苏认可度不错。",
     "tags": ["宿舍豪华", "图书馆霸位", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
    {"major": "医学检验技术", "comment": "江大医学检验全国有名。医学院实力不错。宿舍条件中上。镇江生活成本低。就业医院检验科和第三方检验机构抢着要江大毕业生。",
     "tags": ["老师超好", "就业无忧", "宿舍豪华"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "计算机科学与技术", "comment": "江苏大学计算机在镇江还可以。校园大环境好。宿舍条件中上。就业主要靠江大在长三角的校友网络。虽然不是211但整体实力在普通院校中不错。",
     "tags": ["校园巨美", "佛系养身", "图书馆霸位"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
]

# 74 南京工业大学 (理工, 普通)
SCHOOL_REVIEWS[74] = [
    {"major": "化学工程与工艺", "comment": "南工大化工全国有名。江浦校区在江北，校园超大需要坐校车。宿舍四人间空调独卫。食堂象山和浦江不错。就业化工企业和新材料公司很认南工大。学校虽然普通但化工实力不输211。",
     "tags": ["宿舍豪华", "校园巨美", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True}},
    {"major": "计算机科学与技术", "comment": "南工大计算机工科氛围浓。江浦校区大环境好。宿舍条件好。就业南京IT企业和化工信息化方向都有。学校不是211但在南京就业还行。",
     "tags": ["宿舍豪华", "校园巨美", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"remote_location": True}},
    {"major": "土木工程", "comment": "南工大土木不错。江浦校区环境好，适合学习。宿舍条件好有空调。食堂价格适中。就业建筑企业和设计院有校招。南京工地多实习机会多。",
     "tags": ["宿舍豪华", "校园巨美", "老师超好"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "mid"},
     "variations": {"remote_location": True}},
]

# 75 南京林业大学 (农林, 双一流)
SCHOOL_REVIEWS[75] = [
    {"major": "园林", "comment": "南林园林全国有名。玄武湖边的校园，樱花大道春天美哭。宿舍老校区条件一般但新校区好。食堂的香樟苑餐厅选择多。就业园林设计和林业局抢着要南林毕业生。双一流后更热门了。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "林学", "comment": "南林林学是传统王牌。学校在紫金山脚下环境好。宿舍条件中上。就业林业系统和生态环保单位很认南林。双一流身份对学校提升很大。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 209 徐州医科大学 (医药, 普通)
SCHOOL_REVIEWS[209] = [
    {"major": "临床医学", "comment": "徐医大麻醉学全国第一！主校区在徐州云龙湖畔。宿舍四人间有空调。麻醉专业是王牌中的王牌，全国医院麻醉科主任很多是徐医大毕业的。食堂的徐州地锅鸡不错。就业各大医院抢徐医大麻醉毕业生。",
     "tags": ["老师超好", "就业无忧", "宿舍豪华"],
     "profile": {"academic": "high", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "high", "admin": "mid", "mental": "mid"},
     "variations": {"forced_study": True}},
    {"major": "药学", "comment": "徐医大药学不错。云龙湖畔校园环境优美。宿舍条件中上。学医考试压力大。就业苏北医院药房和医药企业有渠道。性价比高的医药类院校。",
     "tags": ["校园巨美", "老师超好", "内卷严重"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "mid"},
     "variations": {"forced_study": True}},
]

# 210 南通大学 (综合, 普通)
SCHOOL_REVIEWS[210] = [
    {"major": "临床医学", "comment": "通大医学院在苏中有名。启秀校区在濠河边环境好。宿舍条件中上。食堂南通特色小吃多。就业南通及苏中医院有通大校友。张謇创办的学校有百年底蕴。",
     "tags": ["校园巨美", "老师超好", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "mid"},
     "variations": {"multi_campus": True}},
    {"major": "汉语言文学", "comment": "通大中文系有师范传统。学校在濠河风景区环境优美。宿舍条件中上。食堂实惠好吃。就业南通中小学老师主力来源。南通经济发展好就业机会多。",
     "tags": ["校园巨美", "老师超好", "佛系养身"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 211 常州大学 (理工, 普通)
SCHOOL_REVIEWS[211] = [
    {"major": "化学工程与工艺", "comment": "常大化工有石油石化特色。武进校区宿舍四人间空调独卫。食堂二楼风味餐厅不错。常州化工企业多实习方便。就业中石化中石油每年招常大毕业生。",
     "tags": ["宿舍豪华", "老师超好", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "计算机科学与技术", "comment": "常大计算机虽然不如化工强但在发展。武进校区宿舍条件好。常州智能制造产业发达，IT需求大。就业常州本地IT企业有校招。学校普通但胜在常州城市不错。",
     "tags": ["宿舍豪华", "佛系养身", "就业困难"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "low", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 242 南京艺术学院 (艺术, 普通)
SCHOOL_REVIEWS[242] = [
    {"major": "美术学", "comment": "南艺美术学在华东有影响力。草场门校区在南京市中心。宿舍老校区条件一般但艺术院校氛围浓。食堂的鸭血粉丝汤不错。艺术氛围太好了，经常有展览演出。就业艺术界和教育行业认可南艺。",
     "tags": ["老师超好", "校园巨美", "社团丰富"],
     "profile": {"academic": "high", "dormitory": "low", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"small_campus": True, "bunk_bed": True}},
    {"major": "设计学", "comment": "南艺设计学院实力强。学校在南京市中心的北京西路。宿舍条件一般但艺术生更在乎工作室环境。食堂小而精。南京的艺术设计公司很多南艺校友。就业设计行业认可度不错。",
     "tags": ["老师超好", "校园巨美", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "low", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"small_campus": True}},
]

# 256 江苏师范大学 (师范, 普通)
SCHOOL_REVIEWS[256] = [
    {"major": "教育学", "comment": "江苏师大在徐州，苏北师范类第一。泉山校区宿舍四人间空调独卫。食堂便宜量大，徐州特色小吃多。江苏中小学教师苏北地区很多来自江苏师大。当老师很稳，学费低性价比高。",
     "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "high", "cost": "high", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "汉语言文学", "comment": "江苏师大中文系培养语文老师为主。泉山校区环境清幽。宿舍条件不错。食堂价格便宜。就业苏北中小学教师有大量需求。虽然不在南京但在当地认可度高。",
     "tags": ["老师超好", "佛系养身", "食堂神仙"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
]

# 257 南京财经大学 (财经, 普通)
SCHOOL_REVIEWS[257] = [
    {"major": "金融学", "comment": "南财金融在江苏财经类不错。仙林校区宿舍四人间空调独卫。食堂北苑的羊肉面很赞。校园在仙林大学城学习氛围好。就业江苏银行和金融机构招人，南财毕业生是主力。",
     "tags": ["宿舍豪华", "就业无忧", "食堂神仙"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {}},
    {"major": "会计学", "comment": "南财会计在江苏普通院校里不错。仙林校区环境好宿舍条件好。食堂中苑选择多。就业四大会计师事务所每年校招南财。虽然非211但在江苏财经界有基础。",
     "tags": ["宿舍豪华", "就业无忧", "老师超好"],
     "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
     "variations": {"hard_course_select": True}},
]

# 258 盐城工学院 (理工, 普通)
SCHOOL_REVIEWS[258] = [
    {"major": "机械工程", "comment": "盐城工学院以工科为主。希望大道校区新，宿舍四人间空调独卫。食堂便宜大碗。盐城生活成本低。就业盐城及苏北制造业企业有校招。学校普通但胜在务实。",
     "tags": ["宿舍豪华", "佛系养身", "食堂神仙"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "mid", "employment": "low", "admin": "mid", "mental": "high"},
     "variations": {"multi_campus": True}},
    {"major": "计算机科学与技术", "comment": "盐工计算机在盐城够用。新校区设施新宿舍好。食堂便宜。学校学习氛围一般。就业盐城本地IT企业和制造业信息化部门。适合想留苏北发展的同学。",
     "tags": ["宿舍豪华", "佛系养身", "就业困难"],
     "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "high", "environment": "mid", "employment": "low", "admin": "mid", "mental": "mid"},
     "variations": {"multi_campus": True}},
]


# ── 主程序 ──
def main():
    print("=" * 60)
    print("学之声 - 上海/浙江/江苏 55所高校AI评价生成器")
    print("=" * 60)
    
    # 不清空已有评价，只统计已有的
    existing = db.execute("SELECT COUNT(*) as cnt FROM reviews").fetchone()["cnt"]
    print(f"📊 数据库中现有评价数: {existing}")
    print("⚠️  保留已有评价（包含北京的33所），仅添加新评价")
    
    total = 0
    skipped_existing = 0
    
    for school_id, reviews in SCHOOL_REVIEWS.items():
        school = db.execute("SELECT * FROM schools WHERE id = ?", (school_id,)).fetchone()
        if not school:
            print(f"❌ 学校ID {school_id} 不存在，跳过")
            continue
        
        print(f"\n📌 {school['name']} ({school['type']}, {school['level']})")
        
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
            
            # 检查是否已有相同school_id+major_id的AI评价
            device_id = f"ai-generator-east-{school_id}-{i}"
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
            
            # 计算分数
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
            
            category_scores, overall_score = calc_scores_from_answers(answers)
            
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
    rows = db.execute("""
        SELECT s.province, COUNT(r.id) as cnt, ROUND(AVG(r.overall_score), 2) as avg
        FROM schools s
        LEFT JOIN reviews r ON s.id = r.school_id
        WHERE s.province IN ('上海','浙江','江苏')
        GROUP BY s.province
        ORDER BY s.province
    """).fetchall()
    for row in rows:
        print(f"   {row['province']}: {row['cnt']}条评价, 均分{row['avg']}")
    
    print(f"\n📊 各学校评价数:")
    rows = db.execute("""
        SELECT s.name, s.level, s.province, COUNT(r.id) as cnt, ROUND(AVG(r.overall_score), 2) as avg
        FROM schools s
        LEFT JOIN reviews r ON s.id = r.school_id
        WHERE s.province IN ('上海','浙江','江苏')
        GROUP BY s.id
        ORDER BY s.province, s.level, s.name
    """).fetchall()
    for row in rows:
        level_tag = f"[{row['level']}]" if row['level'] else ""
        print(f"   {level_tag} {row['name']:16s} ({row['province']}): {row['cnt']}条, 均分{row['avg']}")


if __name__ == "__main__":
    main()
