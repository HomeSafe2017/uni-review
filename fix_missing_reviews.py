#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补全因专业名不在数据库中而缺失的8条评价"""
import sys, os, json, sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
    CONFIG = json.load(f)
CATEGORIES = CONFIG["categories"]

def calc_scores_from_answers(answers):
    category_scores = {}
    for cat_key, cat_info in CATEGORIES.items():
        question_scores = []
        for q in cat_info["questions"]:
            if q["id"] in answers:
                score = q["yes_score"] if answers[q["id"]] else q["no_score"]
                question_scores.append(score)
        if question_scores:
            category_scores[cat_key] = round(sum(question_scores) / len(question_scores), 2)
        else:
            category_scores[cat_key] = 0
    total_weight = sum(cat_info["weight"] for cat_key, cat_info in CATEGORIES.items() if category_scores.get(cat_key, 0) > 0)
    overall = 0 if total_weight == 0 else round(sum(category_scores.get(cat_key, 0) * cat_info["weight"] for cat_key, cat_info in CATEGORIES.items() if category_scores.get(cat_key, 0) > 0) / total_weight, 2)
    return category_scores, overall

profiles = {
    "academic": {
        "high": {"forced_run": False, "forced_study": False, "hard_course_select": False, "system_crash": False, "bad_curriculum": False, "forced_lecture": False, "bad_exam_schedule": False},
        "mid": {"forced_run": True, "forced_study": False, "hard_course_select": True, "system_crash": False, "bad_curriculum": True, "forced_lecture": True, "bad_exam_schedule": False},
        "low": {"forced_run": True, "forced_study": True, "hard_course_select": True, "system_crash": True, "bad_curriculum": True, "forced_lecture": True, "bad_exam_schedule": True},
    },
    "dormitory": {
        "high": {"private_bathroom": True, "has_ac": True, "power_limit": False, "has_curfew": False, "bunk_bed": False, "over_6_room": False, "room_check": False, "hot_water_24h": True, "laundry_access": True},
        "mid": {"private_bathroom": False, "has_ac": True, "power_limit": True, "has_curfew": True, "bunk_bed": True, "over_6_room": False, "room_check": True, "hot_water_24h": False, "laundry_access": True},
        "low": {"private_bathroom": False, "has_ac": False, "power_limit": True, "has_curfew": True, "bunk_bed": True, "over_6_room": True, "room_check": True, "hot_water_24h": False, "laundry_access": False},
    },
    "cafeteria": {
        "high": {"bad_food": False, "expensive_food": False, "food_safety_issue": False, "limited_variety": False, "no_delivery": False, "no_nearby_food": False},
        "mid": {"bad_food": False, "expensive_food": True, "food_safety_issue": False, "limited_variety": True, "no_delivery": True, "no_nearby_food": False},
        "low": {"bad_food": True, "expensive_food": True, "food_safety_issue": True, "limited_variety": True, "no_delivery": True, "no_nearby_food": True},
    },
    "cost": {
        "high": {"expensive_utilities": False, "hidden_fees": False, "bad_internet": False, "forced_internship_fee": False, "unclear_fees": False, "campus_monopoly": False},
        "mid": {"expensive_utilities": True, "hidden_fees": False, "bad_internet": True, "forced_internship_fee": False, "unclear_fees": False, "campus_monopoly": True},
        "low": {"expensive_utilities": True, "hidden_fees": True, "bad_internet": True, "forced_internship_fee": True, "unclear_fees": True, "campus_monopoly": True},
    },
    "environment": {
        "high": {"remote_location": False, "small_campus": False, "poor_facilities": True, "no_transit": False, "bad_security": False, "multi_campus": False},
        "mid": {"remote_location": False, "small_campus": True, "poor_facilities": True, "no_transit": False, "bad_security": False, "multi_campus": True},
        "low": {"remote_location": True, "small_campus": True, "poor_facilities": False, "no_transit": True, "bad_security": True, "multi_campus": True},
    },
    "employment": {
        "high": {"fake_employment_rate": False, "forced_sign": False, "useless_career_center": False, "bad_job_fair": False, "low_recognition": False, "trap_major": False, "forced_factory": False},
        "mid": {"fake_employment_rate": True, "forced_sign": False, "useless_career_center": True, "bad_job_fair": True, "low_recognition": False, "trap_major": False, "forced_factory": False},
        "low": {"fake_employment_rate": True, "forced_sign": True, "useless_career_center": True, "bad_job_fair": True, "low_recognition": True, "trap_major": True, "forced_factory": True},
    },
    "admin": {
        "high": {"slow_admin": False, "bad_counselor": False, "formalism": False, "unfair_scholarship": False, "no_feedback_channel": False, "random_plan_change": False, "bureaucracy": False},
        "mid": {"slow_admin": True, "bad_counselor": False, "formalism": True, "unfair_scholarship": True, "no_feedback_channel": True, "random_plan_change": False, "bureaucracy": True},
        "low": {"slow_admin": True, "bad_counselor": True, "formalism": True, "unfair_scholarship": True, "no_feedback_channel": True, "random_plan_change": True, "bureaucracy": True},
    },
    "mental": {
        "high": {"no_counseling": False, "no_room_change": False, "bad_club": False},
        "mid": {"no_counseling": True, "no_room_change": True, "bad_club": False},
        "low": {"no_counseling": True, "no_room_change": True, "bad_club": True},
    },
}

def make_answers(base_profile, variations=None):
    answers = {}
    for cat, level in base_profile.items():
        if level in profiles.get(cat, {}):
            answers.update(profiles[cat][level])
    if variations:
        answers.update(variations)
    return answers

# Missing reviews to add
fixes = [
    # 1. 上海大学 (id=38, 综合) - 社会学的替代
    {
        "school_id": 38, "major_name": "新闻学",
        "comment": "上大新闻传播学院在上海市内有一定影响力。宝山校区校园很大很美。宿舍四人间有空调。食堂选择多，尔美食堂的煲仔饭很赞。实习机会上海报业集团和新媒体公司都有。上大综合性大学选课自由度高。",
        "tags": ["校园巨美", "食堂神仙", "就业无忧"],
        "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "high", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
        "variations": {}
    },
    # 2. 东华大学 (id=39, 理工) - 服装与服饰设计的替代
    {
        "school_id": 39, "major_name": "英语",
        "comment": "东华英语专业有纺织服装特色方向。延安路校区在市中心，宿舍条件一般但位置无敌。松江校区宿舍新但偏。东华的国际交流机会多，服装行业国际化背景有优势。就业外企和贸易公司为主。",
        "tags": ["电梯便利", "老师超好", "就业无忧"],
        "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
        "variations": {"multi_campus": True}
    },
    # 3. 上海理工大学 (id=41, 理工) - 光学工程的替代
    {
        "school_id": 41, "major_name": "自动化",
        "comment": "上理工自动化在制造业方向有特色。军工路校区靠近复兴岛。宿舍六人间上下铺有空调。食堂环境一般但价格实惠。上海制造业企业有校招。学校虽普通但在上海就业地缘优势明显。",
        "tags": ["空调自由", "佛系养身", "食堂地狱"],
        "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "mid"},
        "variations": {"bunk_bed": True}
    },
    # 4. 浙江理工大学 (id=83, 理工) - 纺织工程的替代
    {
        "school_id": 83, "major_name": "工商管理",
        "comment": "浙理工工商管理有纺织服装行业背景。下沙校区宿舍四人间空调独卫。食堂桂花园的煲仔饭是招牌。杭州就业市场广阔，学校管理类专业就业尚可。校园环境不错，生活便利。",
        "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
        "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "mid", "admin": "mid", "mental": "high"},
        "variations": {}
    },
    # 5. 河海大学 (id=64, 理工) - 水利工程的替代
    {
        "school_id": 64, "major_name": "电气工程及其自动化",
        "comment": "河海电气有水利电力特色。江宁校区宿舍条件好四人间独卫。食堂新食堂选择多。就业国家电网和电力设计院每年招河海毕业生。学校在南京211里性价比很高，工科实力强。",
        "tags": ["宿舍豪华", "就业无忧", "老师超好"],
        "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "mid", "cost": "mid", "environment": "mid", "employment": "high", "admin": "mid", "mental": "high"},
        "variations": {"multi_campus": True}
    },
    # 6. 中国矿业大学 (id=65, 理工) - 采矿工程的替代
    {
        "school_id": 65, "major_name": "电气工程及其自动化",
        "comment": "矿大电气在徐州有着很好的就业前景。南湖校区宿舍条件极好，四人上床下桌独卫空调。食堂桃苑的米线和麻辣烫是招牌。校园超大环境优美。就业国家电网和矿业央企每年大批招人。",
        "tags": ["宿舍豪华", "食堂神仙", "就业无忧"],
        "profile": {"academic": "mid", "dormitory": "high", "cafeteria": "high", "cost": "high", "environment": "high", "employment": "high", "admin": "mid", "mental": "high"},
        "variations": {"remote_location": True}
    },
    # 7. 南京信息工程大学 (id=71, 理工) - 大气科学的替代
    {
        "school_id": 71, "major_name": "通信工程",
        "comment": "南信大通信工程有气象信息化方向特色。龙王山校区环境清幽。宿舍四人间空调独卫。食堂中苑新食堂品种丰富。学校双一流加持后发展快。就业通信企业和气象信息化单位都有需求。",
        "tags": ["宿舍豪华", "校园巨美", "就业无忧"],
        "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "high"},
        "variations": {}
    },
    # 8. 江苏大学 (id=73, 综合) - 医学检验技术的替代
    {
        "school_id": 73, "major_name": "临床医学",
        "comment": "江大临床医学在镇江有口碑。校园大环境好，图书馆非常气派。宿舍四人间空调独卫。食堂一食堂的锅盖面好吃。就业镇江苏南地区医院有校招。虽然不是211但综合实力不错。",
        "tags": ["宿舍豪华", "图书馆霸位", "就业无忧"],
        "profile": {"academic": "mid", "dormitory": "mid", "cafeteria": "mid", "cost": "mid", "environment": "high", "employment": "mid", "admin": "mid", "mental": "mid"},
        "variations": {"multi_campus": True, "bad_exam_schedule": True}
    },
]

db = sqlite3.connect(os.path.join(BASE_DIR, CONFIG["database"]))
db.row_factory = sqlite3.Row

added = 0
for f in fixes:
    # Find major id
    major = db.execute("SELECT id FROM majors WHERE name = ?", (f["major_name"],)).fetchone()
    if not major:
        print(f"❌ 专业 '{f['major_name']}' 不存在，跳过")
        continue
    
    major_id = major["id"]
    school_id = f["school_id"]
    
    # Check if already exists
    device_id = f"ai-generator-east-fix-{school_id}-{f['major_name']}"
    existing = db.execute("SELECT id FROM reviews WHERE school_id = ? AND major_id = ? AND device_id = ?",
                          (school_id, major_id, device_id)).fetchone()
    if existing:
        print(f"⚠️  已存在，跳过: 学校{school_id} {f['major_name']}")
        continue
    
    answers = make_answers(f["profile"], f.get("variations", {}))
    
    # Ensure all categories have answers
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
                    profile = f["profile"]
                    if profile.get(cat_key) == "high":
                        answers[q["id"]] = q["yes_score"] > q["no_score"]
                    elif profile.get(cat_key) == "low":
                        answers[q["id"]] = q["yes_score"] < q["no_score"]
                    else:
                        answers[q["id"]] = q["id"] in ["poor_facilities", "laundry_access", "hot_water_24h", "has_ac", "private_bathroom"]
                    break
    
    category_scores, overall_score = calc_scores_from_answers(answers)
    
    db.execute(
        """INSERT INTO reviews 
        (school_id, major_id, device_id, answers, category_scores, overall_score, comment, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (school_id, major_id, device_id,
         json.dumps(answers, ensure_ascii=False),
         json.dumps(category_scores, ensure_ascii=False),
         overall_score, f["comment"], json.dumps(f["tags"], ensure_ascii=False))
    )
    db.commit()
    school = db.execute("SELECT name FROM schools WHERE id = ?", (school_id,)).fetchone()
    print(f"✅ {school['name']} - {f['major_name']}: {overall_score:.1f}分")
    added += 1

print(f"\n✅ 补全完成！新增 {added} 条评价")
total = db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
print(f"📊 评价总数: {total}")
