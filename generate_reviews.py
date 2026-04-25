#!/usr/bin/env python3
"""
生成假测评数据脚本
- 根据学校层次(985/211/双一流/普通)和专业类型生成合理的评分
- 每校2-5个专业有测评
- 评论中明确标注"指标来源网络"
"""

import json
import random
import sqlite3
import os
from datetime import datetime, timedelta

DATABASE = os.path.join(os.path.dirname(__file__), "data", "uni_review.db")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

CATEGORIES = CONFIG["categories"]
CAT_KEYS = list(CATEGORIES.keys())
ALL_TAGS = CONFIG["tags"]


# ── 学校层次 → 基础分偏移 ──
LEVEL_OFFSET = {
    "985/211": 0.8,
    "211": 0.5,
    "双一流": 0.3,
    "普通": 0.0,
}

# ── 学校类型 → 各维度微调 ──
TYPE_MOD = {
    "综合":  {"academic": 0.2, "dormitory": 0.0, "cafeteria": 0.1, "cost": 0.0, "environment": 0.2, "employment": 0.1, "admin": 0.0, "mental": 0.1},
    "理工":  {"academic": 0.3, "dormitory": -0.1, "cafeteria": 0.0, "cost": 0.0, "environment": 0.0, "employment": 0.2, "admin": -0.1, "mental": -0.1},
    "师范":  {"academic": 0.1, "dormitory": 0.1, "cafeteria": 0.1, "cost": 0.1, "environment": 0.1, "employment": 0.0, "admin": 0.1, "mental": 0.2},
    "财经":  {"academic": 0.1, "dormitory": 0.0, "cafeteria": 0.1, "cost": -0.2, "environment": 0.1, "employment": 0.3, "admin": 0.0, "mental": 0.0},
    "医药":  {"academic": 0.2, "dormitory": -0.2, "cafeteria": -0.1, "cost": -0.2, "environment": -0.1, "employment": 0.1, "admin": -0.1, "mental": -0.2},
    "农林":  {"academic": 0.0, "dormitory": -0.2, "cafeteria": -0.1, "cost": 0.1, "environment": -0.1, "employment": -0.1, "admin": 0.0, "mental": -0.1},
    "政法":  {"academic": 0.2, "dormitory": 0.0, "cafeteria": 0.0, "cost": 0.0, "environment": 0.0, "employment": 0.1, "admin": 0.0, "mental": 0.0},
    "民族":  {"academic": 0.0, "dormitory": -0.1, "cafeteria": 0.0, "cost": 0.1, "environment": -0.1, "employment": -0.1, "admin": 0.0, "mental": 0.1},
    "语言":  {"academic": 0.1, "dormitory": 0.0, "cafeteria": 0.0, "cost": 0.0, "environment": 0.1, "employment": 0.0, "admin": 0.0, "mental": 0.1},
    "艺术":  {"academic": -0.1, "dormitory": 0.0, "cafeteria": 0.0, "cost": -0.2, "environment": 0.1, "employment": -0.1, "admin": 0.0, "mental": 0.1},
    "体育":  {"academic": -0.2, "dormitory": 0.0, "cafeteria": 0.1, "cost": 0.0, "environment": 0.1, "employment": -0.1, "admin": 0.0, "mental": 0.1},
}

# ── 专业类别 → 就业维度影响 ──
MAJOR_CAT_EMPLOYMENT = {
    "工学": 0.3, "经济学": 0.2, "管理学": 0.1, "理学": 0.0,
    "医学": 0.1, "文学": -0.1, "法学": 0.0, "教育学": 0.0,
    "农学": -0.3, "艺术学": -0.2, "历史学": -0.3, "哲学": -0.3,
}

# ── 评论模板 ──
COMMENT_TEMPLATES = {
    "985/211": [
        "学校整体水平较高，资源丰富。{highlight}指标来源网络。",
        "综合实力强，{highlight}但部分管理仍有提升空间。指标来源网络。",
        "学术氛围浓厚，{highlight}适合认真做学术的同学。指标来源网络。",
        "平台和资源都不错，{highlight}机会多竞争也大。指标来源网络。",
    ],
    "211": [
        "学校整体还可以，{highlight}指标来源网络。",
        "211平台有一定优势，{highlight}但部分设施待改善。指标来源网络。",
        "教学质量尚可，{highlight}就业情况看专业。指标来源网络。",
        "{highlight}总体过得去，性价比还行。指标来源网络。",
    ],
    "双一流": [
        "双一流学科有优势，{highlight}指标来源网络。",
        "部分学科实力强，{highlight}但整体水平参差不齐。指标来源网络。",
        "{highlight}双一流建设带来一些改善。指标来源网络。",
    ],
    "普通": [
        "普通本科，{highlight}指标来源网络。",
        "学校一般，{highlight}主要靠自己。指标来源网络。",
        "{highlight}设施和管理都有提升空间。指标来源网络。",
        "地方性院校，{highlight}就业靠个人能力。指标来源网络。",
    ],
}

HIGHLIGHTS = {
    "好宿舍": ["宿舍条件不错，", "住宿环境还行，", "宿舍挺舒适的，"],
    "好食堂": ["食堂味道可以，", "餐饮选择较多，", "食堂性价比高，"],
    "好就业": ["就业情况较好，", "用人单位认可度还行，", "就业率高，"],
    "差就业": ["就业情况一般，", "就业竞争大，", "就业压力大，"],
    "差宿舍": ["宿舍条件一般，", "住宿环境待改善，", "宿舍比较老旧，"],
    "差食堂": ["食堂一般，", "餐饮选择有限，", "食堂价格偏贵，"],
    "差管理": ["行政效率低，", "形式主义较多，", "管理有待改善，"],
    "内卷": ["学习氛围浓厚但内卷，", "竞争压力大，", "卷王很多，"],
    "偏僻": ["位置偏僻，", "交通不太方便，", "远离市区，"],
}


def calc_scores_from_answers(answers, categories_config=None):
    """从有无答案计算各大类得分和综合得分"""
    if categories_config is None:
        categories_config = CATEGORIES
    category_scores = {}
    for cat_key, cat_info in categories_config.items():
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
        for cat_key, cat_info in categories_config.items()
        if category_scores.get(cat_key, 0) > 0
    )
    if total_weight == 0:
        overall = 0
    else:
        overall = sum(
            category_scores.get(cat_key, 0) * cat_info["weight"]
            for cat_key, cat_info in categories_config.items()
            if category_scores.get(cat_key, 0) > 0
        ) / total_weight
    return category_scores, round(overall, 2)


def generate_answers_for_school_major(school, major, seed_val):
    """根据学校层次和专业类型生成合理的answers"""
    rng = random.Random(seed_val)

    level = school["level"] or "普通"
    stype = school["type"] or "综合"
    mcategory = major["category"] or "工学"

    base_offset = LEVEL_OFFSET.get(level, 0)
    type_mods = TYPE_MOD.get(stype, {})
    employ_mod = MAJOR_CAT_EMPLOYMENT.get(mcategory, 0)

    answers = {}
    for cat_key, cat_info in CATEGORIES.items():
        # 基础概率：学校层次越高，"有问题"(yes)的概率越低
        base_yes_prob = 0.55 - base_offset * 0.15

        # 应用类型微调
        cat_mod = type_mods.get(cat_key, 0)
        base_yes_prob -= cat_mod * 0.1

        # 就业维度特别处理
        if cat_key == "employment":
            base_yes_prob -= employ_mod * 0.15

        # 确保概率在合理范围
        base_yes_prob = max(0.1, min(0.7, base_yes_prob))

        for q in cat_info["questions"]:
            # 每个问题有独立但相关的概率
            q_prob = base_yes_prob + rng.uniform(-0.15, 0.15)
            q_prob = max(0.05, min(0.8, q_prob))

            # 特殊问题调整
            # 985/211强制校园跑概率低
            if q["id"] == "forced_run" and level in ("985/211", "211"):
                q_prob -= 0.1
            # 医药类强制实习概率高
            if q["id"] == "forced_factory" and stype == "医药":
                q_prob += 0.2
            # 农林类偏僻概率高
            if q["id"] == "remote_location" and stype == "农林":
                q_prob += 0.15
            # 理工类选课难
            if q["id"] == "hard_course_select" and stype == "理工":
                q_prob += 0.1
            # 天坑专业
            if q["id"] == "trap_major":
                if mcategory in ("农学", "历史学", "哲学"):
                    q_prob += 0.3
                elif mcategory in ("工学", "经济学"):
                    q_prob -= 0.15
                # 顶尖学校即使天坑专业就业也不算差
                if level in ("985/211",) and mcategory not in ("农学", "历史学", "哲学"):
                    q_prob -= 0.2
            # 就业率注水 - 普通学校更高
            if q["id"] == "fake_employment_rate" and level == "普通":
                q_prob += 0.15
            # 强制签就业协议 - 普通学校更高
            if q["id"] == "forced_sign" and level == "普通":
                q_prob += 0.1

            q_prob = max(0.05, min(0.85, q_prob))
            answers[q["id"]] = rng.random() < q_prob

    return answers


def generate_comment(school, major, category_scores, seed_val):
    """生成评论"""
    rng = random.Random(seed_val + 9999)
    level = school["level"] or "普通"
    templates = COMMENT_TEMPLATES.get(level, COMMENT_TEMPLATES["普通"])

    # 根据分数选highlight
    highlights = []
    if category_scores.get("dormitory", 3) >= 3.5:
        highlights.append(rng.choice(HIGHLIGHTS["好宿舍"]))
    elif category_scores.get("dormitory", 3) < 2.5:
        highlights.append(rng.choice(HIGHLIGHTS["差宿舍"]))

    if category_scores.get("cafeteria", 3) >= 3.5:
        highlights.append(rng.choice(HIGHLIGHTS["好食堂"]))
    elif category_scores.get("cafeteria", 3) < 2.5:
        highlights.append(rng.choice(HIGHLIGHTS["差食堂"]))

    if category_scores.get("employment", 3) >= 3.5:
        highlights.append(rng.choice(HIGHLIGHTS["好就业"]))
    elif category_scores.get("employment", 3) < 2.5:
        highlights.append(rng.choice(HIGHLIGHTS["差就业"]))

    if category_scores.get("admin", 3) < 2.5:
        highlights.append(rng.choice(HIGHLIGHTS["差管理"]))

    if category_scores.get("academic", 3) >= 3.5 and level in ("985/211", "211"):
        highlights.append(rng.choice(HIGHLIGHTS["内卷"]))

    if category_scores.get("environment", 3) < 2.5:
        highlights.append(rng.choice(HIGHLIGHTS["偏僻"]))

    highlight_text = "".join(highlights) if highlights else ""
    template = rng.choice(templates)
    return template.format(highlight=highlight_text)


def generate_tags(category_scores, seed_val):
    """根据评分生成标签"""
    rng = random.Random(seed_val + 7777)
    tags = []

    if category_scores.get("academic", 3) >= 3.8:
        tags.append("内卷严重")
    elif category_scores.get("academic", 3) < 2.5:
        tags.append("佛系养身")

    if category_scores.get("cafeteria", 3) >= 4.0:
        tags.append("食堂神仙")
    elif category_scores.get("cafeteria", 3) < 2.0:
        tags.append("食堂地狱")

    if category_scores.get("dormitory", 3) >= 4.0:
        tags.append("宿舍豪华")
        tags.append("空调自由")
    elif category_scores.get("dormitory", 3) < 2.0:
        tags.append("宿舍破旧")
        tags.append("空调绝缘")

    if category_scores.get("employment", 3) >= 3.8:
        tags.append("就业无忧")
    elif category_scores.get("employment", 3) < 2.5:
        tags.append("就业困难")

    if category_scores.get("cost", 3) < 2.0:
        tags.append("水电刺客")

    if category_scores.get("environment", 3) >= 4.0:
        tags.append("校园巨美")
    elif category_scores.get("environment", 3) < 2.5:
        tags.append("校园荒凉")

    if category_scores.get("admin", 3) < 2.0:
        tags.append("形式主义")

    # 从所有标签中随机补充1-2个
    remaining = [t for t in ALL_TAGS if t not in tags]
    if remaining:
        extra = rng.sample(remaining, min(rng.randint(0, 2), len(remaining)))
        tags.extend(extra)

    # 去重保留顺序
    seen = set()
    unique_tags = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            unique_tags.append(t)

    return unique_tags[:5]  # 最多5个标签


def main():
    random.seed(42)  # 全局种子保证可复现

    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row

    schools = db.execute("SELECT * FROM schools").fetchall()
    majors = db.execute("SELECT * FROM majors").fetchall()
    major_by_id = {m["id"]: dict(m) for m in majors}

    # 专业按category分组
    majors_by_category = {}
    for m in majors:
        cat = m["category"] or "其他"
        if cat not in majors_by_category:
            majors_by_category[cat] = []
        majors_by_category[cat].append(m)

    # 学校层次决定每校生成多少专业的测评
    reviews_per_school = {
        "985/211": (3, 5),   # 3-5个专业
        "211": (2, 4),       # 2-4个专业
        "双一流": (2, 3),     # 2-3个专业
        "普通": (1, 3),       # 1-3个专业
    }

    review_count = 0
    # 时间范围：最近6个月内随机
    now = datetime.now()
    start_date = now - timedelta(days=180)

    for school in schools:
        school_dict = dict(school)
        level = school_dict.get("level", "普通")
        stype = school_dict.get("type", "综合")
        school_id = school_dict["id"]

        min_majors, max_majors = reviews_per_school.get(level, (1, 2))
        num_majors = random.randint(min_majors, max_majors)

        # 选择专业：优先选与学校类型相关的专业
        related_categories = {
            "理工": ["工学", "理学"],
            "医药": ["医学", "理学"],
            "师范": ["教育学", "文学", "理学"],
            "财经": ["经济学", "管理学"],
            "农林": ["农学", "理学"],
            "政法": ["法学", "管理学"],
            "综合": ["工学", "理学", "文学", "管理学", "经济学"],
            "民族": ["文学", "历史学", "法学"],
            "语言": ["文学", "经济学"],
            "艺术": ["艺术学", "文学"],
            "体育": ["教育学", "管理学"],
        }

        preferred_cats = related_categories.get(stype, ["工学", "理学", "管理学"])
        preferred_majors = []
        other_majors = []
        for cat in preferred_cats:
            if cat in majors_by_category:
                preferred_majors.extend(majors_by_category[cat])
        for cat, ms in majors_by_category.items():
            if cat not in preferred_cats:
                other_majors.extend(ms)

        # 先从相关专业的池子里选，不够再用其他专业补
        chosen_majors = []
        pool = list(preferred_majors)
        random.shuffle(pool)
        for m in pool:
            if len(chosen_majors) >= num_majors:
                break
            chosen_majors.append(m)

        if len(chosen_majors) < num_majors:
            random.shuffle(other_majors)
            for m in other_majors:
                if len(chosen_majors) >= num_majors:
                    break
                if m not in chosen_majors:
                    chosen_majors.append(m)

        for major in chosen_majors:
            major_dict = dict(major)
            major_id = major_dict["id"]

            # 每个专业生成1-3条测评
            num_reviews = random.randint(1, 2) if level == "普通" else random.randint(1, 3)

            for i in range(num_reviews):
                seed_val = school_id * 1000 + major_id * 10 + i
                rng = random.Random(seed_val)

                # 生成answers
                answers = generate_answers_for_school_major(school_dict, major_dict, seed_val)

                # 计算分数
                category_scores, overall_score = calc_scores_from_answers(answers)

                # 生成评论
                comment = generate_comment(school_dict, major_dict, category_scores, seed_val)

                # 生成标签
                tags = generate_tags(category_scores, seed_val)

                # 随机时间
                days_ago = rng.randint(0, 180)
                hours_ago = rng.randint(0, 23)
                created_at = start_date + timedelta(days=days_ago, hours=hours_ago)

                # device_id
                device_id = f"seed_{school_id}_{major_id}_{i}"

                # 检查是否已存在
                existing = db.execute(
                    "SELECT id FROM reviews WHERE school_id=? AND major_id=? AND device_id=?",
                    (school_id, major_id, device_id)
                ).fetchone()
                if existing:
                    continue

                db.execute(
                    """INSERT INTO reviews
                    (school_id, major_id, device_id, answers, category_scores, overall_score, comment, tags, likes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        school_id,
                        major_id,
                        device_id,
                        json.dumps(answers, ensure_ascii=False),
                        json.dumps(category_scores, ensure_ascii=False),
                        overall_score,
                        comment,
                        json.dumps(tags, ensure_ascii=False),
                        rng.randint(0, 15),
                        created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    )
                )
                review_count += 1

    db.commit()

    # 统计
    total_reviews = db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    schools_with_reviews = db.execute(
        "SELECT COUNT(DISTINCT school_id) FROM reviews"
    ).fetchone()[0]
    majors_with_reviews = db.execute(
        "SELECT COUNT(DISTINCT major_id) FROM reviews"
    ).fetchone()[0]

    # 平均分分布
    score_rows = db.execute("SELECT overall_score FROM reviews").fetchall()
    if score_rows:
        scores = [r[0] for r in score_rows]
        avg_score = round(sum(scores) / len(scores), 2)
        min_score = round(min(scores), 2)
        max_score = round(max(scores), 2)
    else:
        avg_score = min_score = max_score = 0

    print(f"✅ 已生成 {review_count} 条测评数据")
    print(f"   覆盖 {schools_with_reviews} 所学校, {majors_with_reviews} 个专业")
    print(f"   综合分范围: {min_score} ~ {max_score}, 平均: {avg_score}")

    db.close()


if __name__ == "__main__":
    main()
