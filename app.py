#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""学之声 - 大学专业综合测评平台 - 从学生视角评价学校和专业"""

import json
import os
import sqlite3
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Flask, g, jsonify, redirect, render_template, request,
    send_from_directory, url_for
)

# ── 加载配置 ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", CONFIG.get("secret_key", "dev-key"))


# ── 类别和问题信息 ────────────────────────────────────────
CATEGORIES = CONFIG["categories"]
CAT_KEYS = list(CATEGORIES.keys())
ALL_TAGS = CONFIG["tags"]

# 构建问题id到类别的映射
QUESTION_TO_CAT = {}
for cat_key, cat_info in CATEGORIES.items():
    for q in cat_info["questions"]:
        QUESTION_TO_CAT[q["id"]] = cat_key


# ── Jinja2 过滤器和全局函数 ──────────────────────────────
def time_ago(date_str):
    """将日期字符串转为友好时间"""
    if not date_str:
        return ""
    try:
        now = datetime.now()
        date = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        diff = (now - date).total_seconds()
    except Exception:
        return str(date_str)[:10]
    if diff < 60:
        return "刚刚"
    if diff < 3600:
        return f"{int(diff // 60)}分钟前"
    if diff < 86400:
        return f"{int(diff // 3600)}小时前"
    if diff < 2592000:
        return f"{int(diff // 86400)}天前"
    return str(date_str)[:10]


def score_bg_filter(score):
    """评分对应的CSS类"""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "bg-gray-100 text-gray-700"
    if s >= 4:
        return "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
    if s >= 3:
        return "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400"
    if s >= 2:
        return "bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400"
    return "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400"


def score_color_filter(score):
    """评分数字对应的CSS类"""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "text-gray-500"
    if s >= 4:
        return "text-green-500"
    if s >= 3:
        return "text-yellow-500"
    if s >= 2:
        return "text-orange-500"
    return "text-red-500"


def score_bar_filter(score):
    """评分进度条对应的CSS类"""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "bg-gray-300"
    if s >= 4:
        return "bg-green-500"
    if s >= 3:
        return "bg-yellow-500"
    if s >= 2:
        return "bg-orange-500"
    return "bg-red-500"


def parse_tags(tags_str):
    """解析JSON标签字符串为列表"""
    if not tags_str:
        return []
    try:
        return json.loads(tags_str)
    except (json.JSONDecodeError, TypeError):
        return []


def format_score_filter(score):
    """格式化评分为1位小数"""
    try:
        s = float(score)
        return f"{s:.1f}"
    except (TypeError, ValueError):
        return "0.0"


def stars_filter(score):
    """将评分转换为星星显示（满分5分）"""
    try:
        s = float(score)
    except (TypeError, ValueError):
        s = 0
    full_stars = int(s)
    has_half = (s - full_stars) >= 0.5
    empty_stars = 5 - full_stars - (1 if has_half else 0)
    result = "★" * full_stars
    if has_half:
        result += "☆"
    result += "☆" * empty_stars
    return result


app.jinja_env.filters["time_ago"] = time_ago
app.jinja_env.filters["score_bg"] = score_bg_filter
app.jinja_env.filters["score_color"] = score_color_filter
app.jinja_env.filters["parse_tags"] = parse_tags
app.jinja_env.filters["format_score"] = format_score_filter
app.jinja_env.filters["stars"] = stars_filter
app.jinja_env.filters["score_bar"] = score_bar_filter

DATABASE = os.path.join(BASE_DIR, CONFIG["database"])


# ── 数据库 ────────────────────────────────────────────────
def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS schools (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        province TEXT,
        city TEXT,
        district TEXT,
        latitude REAL,
        longitude REAL,
        type TEXT,
        level TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS campuses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        school_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
        UNIQUE(school_id, name)
    );

    CREATE TABLE IF NOT EXISTS majors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(name, category)
    );

    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        school_id INTEGER NOT NULL,
        major_id INTEGER NOT NULL,
        device_id TEXT NOT NULL,
        answers TEXT NOT NULL DEFAULT '{}',
        category_scores TEXT NOT NULL DEFAULT '{}',
        overall_score REAL,
        comment TEXT,
        tags TEXT,
        likes INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (school_id) REFERENCES schools(id),
        FOREIGN KEY (major_id) REFERENCES majors(id),
        UNIQUE(school_id, major_id, device_id)
    );

    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        review_id INTEGER NOT NULL,
        device_id TEXT NOT NULL,
        content TEXT NOT NULL,
        likes INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS liked_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT NOT NULL,
        target_type TEXT NOT NULL CHECK(target_type IN ('review', 'comment')),
        target_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(device_id, target_type, target_id)
    );
    """)
    db.commit()


# ── 辅助函数 ──────────────────────────────────────────────
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

    # 加权综合分
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


def get_school_avg(school_id):
    """获取学校各大类平均分和综合分"""
    db = get_db()
    rows = db.execute(
        "SELECT answers, category_scores, overall_score FROM reviews WHERE school_id = ?",
        (school_id,),
    ).fetchall()
    if not rows:
        return None

    # 聚合每个类别的得分
    cat_sums = {k: [] for k in CAT_KEYS}
    for row in rows:
        try:
            cs = json.loads(row["category_scores"]) if row["category_scores"] else {}
        except (json.JSONDecodeError, TypeError):
            cs = {}
        for k in CAT_KEYS:
            if cs.get(k, 0) > 0:
                cat_sums[k].append(cs[k])

    avg = {}
    for k in CAT_KEYS:
        vals = cat_sums[k]
        avg[k] = round(sum(vals) / len(vals), 2) if vals else 0

    # 重新计算综合分
    total_weight = sum(
        CATEGORIES[k]["weight"] for k in CAT_KEYS if avg.get(k, 0) > 0
    )
    if total_weight == 0:
        avg["overall_score"] = 0
    else:
        avg["overall_score"] = round(
            sum(avg.get(k, 0) * CATEGORIES[k]["weight"] for k in CAT_KEYS if avg.get(k, 0) > 0)
            / total_weight, 2
        )
    avg["review_count"] = len(rows)

    # 计算每个问题的比例统计
    question_stats = {}
    for q_id in QUESTION_TO_CAT:
        yes_count = 0
        no_count = 0
        for row in rows:
            try:
                ans = json.loads(row["answers"]) if row["answers"] else {}
            except (json.JSONDecodeError, TypeError):
                ans = {}
            if q_id in ans:
                if ans[q_id]:
                    yes_count += 1
                else:
                    no_count += 1
        total = yes_count + no_count
        if total > 0:
            question_stats[q_id] = {
                "yes_count": yes_count,
                "no_count": no_count,
                "yes_pct": round(yes_count / total * 100, 1),
                "no_pct": round(no_count / total * 100, 1),
                "total": total,
            }
    avg["question_stats"] = question_stats

    return avg


def get_major_avg_in_school(school_id, major_id):
    """获取某校某专业各大类平均分"""
    db = get_db()
    rows = db.execute(
        "SELECT answers, category_scores, overall_score FROM reviews WHERE school_id = ? AND major_id = ?",
        (school_id, major_id),
    ).fetchall()
    if not rows:
        return None

    cat_sums = {k: [] for k in CAT_KEYS}
    for row in rows:
        try:
            cs = json.loads(row["category_scores"]) if row["category_scores"] else {}
        except (json.JSONDecodeError, TypeError):
            cs = {}
        for k in CAT_KEYS:
            if cs.get(k, 0) > 0:
                cat_sums[k].append(cs[k])

    avg = {}
    for k in CAT_KEYS:
        vals = cat_sums[k]
        avg[k] = round(sum(vals) / len(vals), 2) if vals else 0

    total_weight = sum(
        CATEGORIES[k]["weight"] for k in CAT_KEYS if avg.get(k, 0) > 0
    )
    if total_weight == 0:
        avg["overall_score"] = 0
    else:
        avg["overall_score"] = round(
            sum(avg.get(k, 0) * CATEGORIES[k]["weight"] for k in CAT_KEYS if avg.get(k, 0) > 0)
            / total_weight, 2
        )
    avg["review_count"] = len(rows)

    # 问题比例统计
    question_stats = {}
    for q_id in QUESTION_TO_CAT:
        yes_count = 0
        no_count = 0
        for row in rows:
            try:
                ans = json.loads(row["answers"]) if row["answers"] else {}
            except (json.JSONDecodeError, TypeError):
                ans = {}
            if q_id in ans:
                if ans[q_id]:
                    yes_count += 1
                else:
                    no_count += 1
        total = yes_count + no_count
        if total > 0:
            question_stats[q_id] = {
                "yes_count": yes_count,
                "no_count": no_count,
                "yes_pct": round(yes_count / total * 100, 1),
                "no_pct": round(no_count / total * 100, 1),
                "total": total,
            }
    avg["question_stats"] = question_stats

    return avg


# ── 路由 ──────────────────────────────────────────────────

# ── 首页 ──
@app.route("/")
def index():
    db = get_db()
    hot_schools = db.execute("""
        SELECT s.*, COUNT(r.id) as review_count,
               ROUND(AVG(r.overall_score), 2) as avg_score
        FROM schools s
        LEFT JOIN reviews r ON s.id = r.school_id
        GROUP BY s.id
        ORDER BY review_count DESC, avg_score DESC
        LIMIT 12
    """).fetchall()

    latest_reviews = db.execute("""
        SELECT r.*, s.name as school_name, m.name as major_name, m.category as major_category
        FROM reviews r
        JOIN schools s ON r.school_id = s.id
        JOIN majors m ON r.major_id = m.id
        ORDER BY r.created_at DESC
        LIMIT 10
    """).fetchall()

    stats = db.execute("""
        SELECT
            (SELECT COUNT(*) FROM schools) as school_count,
            (SELECT COUNT(*) FROM reviews) as review_count,
            (SELECT COUNT(DISTINCT major_id) FROM reviews) as major_count
    """).fetchone()

    return render_template("index.html",
                           hot_schools=hot_schools,
                           latest_reviews=latest_reviews,
                           stats=stats,
                           categories=CATEGORIES,
                           cat_keys=CAT_KEYS)


# ── 搜索 ──
@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return redirect(url_for("index"))
    db = get_db()
    schools = db.execute(
        "SELECT * FROM schools WHERE name LIKE ? LIMIT 20",
        (f"%{q}%",),
    ).fetchall()
    return render_template("search.html", schools=schools, q=q,
                           categories=CATEGORIES, cat_keys=CAT_KEYS)


# ── 学校详情 ──
@app.route("/school/<int:school_id>")
def school_detail(school_id):
    db = get_db()
    school = db.execute("SELECT * FROM schools WHERE id = ?", (school_id,)).fetchone()
    if not school:
        return render_template("404.html", msg="学校不存在"), 404

    avg = get_school_avg(school_id)

    major_rows = db.execute("""
        SELECT m.id as major_id, m.name as major_name, m.category,
               COUNT(r.id) as review_count,
               ROUND(AVG(r.overall_score), 2) as avg_score,
               GROUP_CONCAT(r.category_scores, '|||') as all_cat_scores
        FROM majors m
        JOIN reviews r ON m.id = r.major_id AND r.school_id = ?
        GROUP BY m.id
        ORDER BY avg_score DESC
    """, (school_id,)).fetchall()

    # 为每个专业计算各维度平均分
    major_scores = []
    for row in major_rows:
        ms = dict(row)
        cat_sums = {k: [] for k in CAT_KEYS}
        if ms["all_cat_scores"]:
            for cs_str in ms["all_cat_scores"].split("|||"):
                try:
                    cs = json.loads(cs_str) if cs_str else {}
                except (json.JSONDecodeError, TypeError):
                    cs = {}
                for k in CAT_KEYS:
                    if cs.get(k, 0) > 0:
                        cat_sums[k].append(cs[k])
        ms["category_scores"] = {}
        for k in CAT_KEYS:
            vals = cat_sums[k]
            ms["category_scores"][k] = round(sum(vals) / len(vals), 2) if vals else 0
        # 移除不需要传到模板的原始字段
        del ms["all_cat_scores"]
        major_scores.append(ms)

    reviews = db.execute("""
        SELECT r.*, m.name as major_name, m.category as major_category
        FROM reviews r
        JOIN majors m ON r.major_id = m.id
        WHERE r.school_id = ?
        ORDER BY r.created_at DESC
    """, (school_id,)).fetchall()

    return render_template("school.html",
                           school=school,
                           avg=avg,
                           major_scores=major_scores,
                           reviews=reviews,
                           categories=CATEGORIES,
                           cat_keys=CAT_KEYS)


# ── 专业详情（在某校下） ──
@app.route("/school/<int:school_id>/major/<int:major_id>")
def major_in_school(school_id, major_id):
    db = get_db()
    school = db.execute("SELECT * FROM schools WHERE id = ?", (school_id,)).fetchone()
    major = db.execute("SELECT * FROM majors WHERE id = ?", (major_id,)).fetchone()
    if not school or not major:
        return render_template("404.html", msg="学校或专业不存在"), 404

    avg = get_major_avg_in_school(school_id, major_id)

    reviews = db.execute("""
        SELECT r.*, m.name as major_name
        FROM reviews r
        JOIN majors m ON r.major_id = m.id
        WHERE r.school_id = ? AND r.major_id = ?
        ORDER BY r.created_at DESC
    """, (school_id, major_id)).fetchall()

    return render_template("major.html",
                           school=school,
                           major=major,
                           avg=avg,
                           reviews=reviews,
                           categories=CATEGORIES,
                           cat_keys=CAT_KEYS)


# ── 测评详情 ──
@app.route("/review/<int:review_id>")
def review_detail(review_id):
    db = get_db()
    review = db.execute("""
        SELECT r.*, s.name as school_name, m.name as major_name, m.category as major_category
        FROM reviews r
        JOIN schools s ON r.school_id = s.id
        JOIN majors m ON r.major_id = m.id
        WHERE r.id = ?
    """, (review_id,)).fetchone()
    if not review:
        return render_template("404.html", msg="测评不存在"), 404

    comments = db.execute("""
        SELECT * FROM comments WHERE review_id = ? ORDER BY created_at DESC
    """, (review_id,)).fetchall()

    # 解析 answers 和 category_scores
    try:
        answers = json.loads(review["answers"]) if review["answers"] else {}
    except (json.JSONDecodeError, TypeError):
        answers = {}
    try:
        category_scores = json.loads(review["category_scores"]) if review["category_scores"] else {}
    except (json.JSONDecodeError, TypeError):
        category_scores = {}

    return render_template("review.html",
                           review=review,
                           answers=answers,
                           category_scores=category_scores,
                           comments=comments,
                           categories=CATEGORIES,
                           cat_keys=CAT_KEYS)


# ── 提交测评 ──
@app.route("/submit")
def submit_page():
    db = get_db()
    schools = db.execute("SELECT id, name, province, city FROM schools ORDER BY name").fetchall()
    majors = db.execute("SELECT id, name, category FROM majors ORDER BY category, name").fetchall()
    return render_template("submit.html",
                           schools=schools,
                           majors=majors,
                           categories=CATEGORIES,
                           cat_keys=CAT_KEYS,
                           tags=ALL_TAGS)


# ── 排名 ──
@app.route("/ranking")
def ranking_page():
    return render_template("ranking.html",
                           categories=CATEGORIES,
                           cat_keys=CAT_KEYS)


# ── 对比 ──
@app.route("/compare")
def compare_page():
    return render_template("compare.html",
                           categories=CATEGORIES,
                           cat_keys=CAT_KEYS)


# ── API ──────────────────────────────────────────────────

@app.route("/api/schools")
def api_schools():
    q = request.args.get("q", "").strip()
    db = get_db()
    if q:
        rows = db.execute(
            "SELECT id, name, province, city FROM schools WHERE name LIKE ? ORDER BY name LIMIT 20",
            (f"%{q}%",),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT id, name, province, city FROM schools ORDER BY name LIMIT 50"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/majors")
def api_majors():
    q = request.args.get("q", "").strip()
    db = get_db()
    if q:
        rows = db.execute(
            "SELECT id, name, category FROM majors WHERE name LIKE ? ORDER BY category, name LIMIT 30",
            (f"%{q}%",),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT id, name, category FROM majors ORDER BY category, name LIMIT 50"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/nearby_schools")
def api_nearby_schools():
    """根据经纬度查找附近的学校（支持多校区）"""
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    if lat is None or lng is None:
        return jsonify({"error": "需要 lat 和 lng 参数"}), 400
    return jsonify(_find_nearby_schools(lat, lng))


@app.route("/api/detect_location")
def api_detect_location():
    """IP定位 - 使用 ip-api.com 免费API（支持多校区）"""
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ',' in user_ip:
        user_ip = user_ip.split(',')[0].strip()
    if user_ip in ('127.0.0.1', '::1', 'localhost'):
        user_ip = ''
    try:
        import urllib.request
        url = f"http://ip-api.com/json/{user_ip}?lang=zh-CN&fields=status,lat,lon"
        resp = urllib.request.urlopen(url, timeout=5)
        data = json.loads(resp.read())
        if data.get("status") == "success":
            lat, lng = data["lat"], data["lon"]
            # Reuse nearby_schools logic by calling it internally
            return api_nearby_schools.__wrapped__(lat, lng) if hasattr(api_nearby_schools, '__wrapped__') else jsonify(_find_nearby_schools(lat, lng))
    except Exception as e:
        print(f"IP定位失败: {e}")
    return jsonify([])


def _find_nearby_schools(lat, lng):
    """共享的附近学校查询逻辑"""
    db = get_db()
    haversine = """(6371 * acos(
        CASE WHEN abs(cos(radians(?)) * cos(radians(LAT)) *
            cos(radians(LNG) - radians(?)) +
            sin(radians(?)) * sin(radians(LAT))) > 1
        THEN sign(cos(radians(?)) * cos(radians(LAT)) *
            cos(radians(LNG) - radians(?)) +
            sin(radians(?)) * sin(radians(LAT)))
        ELSE cos(radians(?)) * cos(radians(LAT)) *
            cos(radians(LNG) - radians(?)) +
            sin(radians(?)) * sin(radians(LAT))
        END))"""

    h_campus = haversine.replace("LAT", "c.latitude").replace("LNG", "c.longitude")
    h_school = haversine.replace("LAT", "s.latitude").replace("LNG", "s.longitude")

    campus_rows = db.execute(f"""
        SELECT s.id, s.name, s.province, s.city, s.type, s.level,
               c.name AS campus_name,
               {h_campus} as distance
        FROM campuses c JOIN schools s ON c.school_id = s.id
        ORDER BY distance LIMIT 30
    """, (lat, lng, lat, lat, lng, lat, lat, lng, lat)).fetchall()

    campus_school_ids = [r["id"] for r in campus_rows]
    ph = ",".join(["?"] * len(campus_school_ids)) if campus_school_ids else "0"
    school_rows = db.execute(f"""
        SELECT s.id, s.name, s.province, s.city, s.type, s.level,
               NULL AS campus_name,
               {h_school} as distance
        FROM schools s
        WHERE s.latitude IS NOT NULL AND s.longitude IS NOT NULL
          AND s.id NOT IN ({ph})
        ORDER BY distance LIMIT 20
    """, (lat, lng, lat, lat, lng, lat, lat, lng, lat) + tuple(campus_school_ids)).fetchall()

    seen = {}
    for r in list(campus_rows) + list(school_rows):
        d = dict(r)
        sid = d["id"]
        if sid not in seen or d["distance"] < seen[sid]["distance"]:
            seen[sid] = d

    results = sorted(seen.values(), key=lambda x: x["distance"])
    return [r for r in results if r["distance"] < 100][:10]


@app.route("/api/submit_review", methods=["POST"])
def api_submit_review():
    data = request.get_json()
    if not data:
        return jsonify({"error": "无效数据"}), 400

    device_id = data.get("device_id", "").strip()
    school_id = data.get("school_id")
    major_id = data.get("major_id")
    answers_raw = data.get("answers", {})

    if not device_id or not school_id or not major_id:
        return jsonify({"error": "缺少必要参数"}), 400

    db = get_db()

    # 检查是否已提交
    existing = db.execute(
        "SELECT id FROM reviews WHERE school_id = ? AND major_id = ? AND device_id = ?",
        (school_id, major_id, device_id),
    ).fetchone()
    if existing:
        return jsonify({"error": "您已经对该学校该专业提交过测评了"}), 409

    # 验证每个大类至少回答1个问题
    answers = {}
    for q_id, val in answers_raw.items():
        if isinstance(val, bool):
            answers[q_id] = val
        elif isinstance(val, str):
            answers[q_id] = val.lower() in ('true', 'yes', '1')
        elif isinstance(val, int):
            answers[q_id] = val == 1

    # 检查每个大类是否有回答
    cat_answered = {k: False for k in CAT_KEYS}
    for q_id in answers:
        cat_key = QUESTION_TO_CAT.get(q_id)
        if cat_key:
            cat_answered[cat_key] = True

    unanswered_cats = [CATEGORIES[k]["name"] for k in CAT_KEYS if not cat_answered.get(k)]
    if unanswered_cats and len(unanswered_cats) == len(CAT_KEYS):
        return jsonify({"error": "请至少回答每个大类中的1个问题"}), 400

    # 计算得分
    category_scores, overall_score = calc_scores_from_answers(answers)

    comment = data.get("comment", "").strip()
    tags = data.get("tags", [])

    try:
        cursor = db.execute(
            """INSERT INTO reviews
            (school_id, major_id, device_id, answers, category_scores, overall_score, comment, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (school_id, major_id, device_id,
             json.dumps(answers, ensure_ascii=False),
             json.dumps(category_scores, ensure_ascii=False),
             overall_score, comment, json.dumps(tags, ensure_ascii=False)),
        )
        db.commit()
        return jsonify({"success": True, "review_id": cursor.lastrowid,
                        "overall_score": overall_score})
    except sqlite3.IntegrityError:
        return jsonify({"error": "您已经对该学校该专业提交过测评了"}), 409


@app.route("/api/check_review")
def api_check_review():
    """检查某设备是否已对某学校某专业提交过测评"""
    device_id = request.args.get("device_id", "")
    school_id = request.args.get("school_id", type=int)
    major_id = request.args.get("major_id", type=int)
    db = get_db()
    existing = db.execute(
        "SELECT id FROM reviews WHERE school_id = ? AND major_id = ? AND device_id = ?",
        (school_id, major_id, device_id),
    ).fetchone()
    return jsonify({"exists": existing is not None, "review_id": existing["id"] if existing else None})


@app.route("/api/comment", methods=["POST"])
def api_comment():
    data = request.get_json()
    if not data:
        return jsonify({"error": "无效数据"}), 400
    device_id = data.get("device_id", "").strip()
    review_id = data.get("review_id")
    content = data.get("content", "").strip()
    if not device_id or not review_id or not content:
        return jsonify({"error": "缺少必要参数"}), 400
    if len(content) > 500:
        return jsonify({"error": "评论不能超过500字"}), 400

    db = get_db()
    review = db.execute("SELECT id FROM reviews WHERE id = ?", (review_id,)).fetchone()
    if not review:
        return jsonify({"error": "测评不存在"}), 404

    cursor = db.execute(
        "INSERT INTO comments (review_id, device_id, content) VALUES (?, ?, ?)",
        (review_id, device_id, content),
    )
    db.commit()
    return jsonify({"success": True, "comment_id": cursor.lastrowid})


@app.route("/api/like", methods=["POST"])
def api_like():
    data = request.get_json()
    device_id = data.get("device_id", "").strip()
    target_type = data.get("target_type")
    target_id = data.get("target_id")

    if not device_id or target_type not in ("review", "comment") or not target_id:
        return jsonify({"error": "参数无效"}), 400

    db = get_db()
    existing = db.execute(
        "SELECT id FROM liked_records WHERE device_id = ? AND target_type = ? AND target_id = ?",
        (device_id, target_type, target_id),
    ).fetchone()

    if existing:
        db.execute("DELETE FROM liked_records WHERE id = ?", (existing["id"],))
        table = "reviews" if target_type == "review" else "comments"
        db.execute(f"UPDATE {table} SET likes = likes - 1 WHERE id = ?", (target_id,))
        db.commit()
        return jsonify({"success": True, "liked": False})
    else:
        db.execute(
            "INSERT INTO liked_records (device_id, target_type, target_id) VALUES (?, ?, ?)",
            (device_id, target_type, target_id),
        )
        table = "reviews" if target_type == "review" else "comments"
        db.execute(f"UPDATE {table} SET likes = likes + 1 WHERE id = ?", (target_id,))
        db.commit()
        return jsonify({"success": True, "liked": True})


@app.route("/api/ranking")
def api_ranking():
    """获取排名数据，支持自定义权重"""
    weights = {}
    for k in CAT_KEYS:
        w = request.args.get(f"w_{k}", default=CATEGORIES[k]["weight"], type=float)
        weights[k] = w

    province = request.args.get("province", "")
    city = request.args.get("city", "")

    db = get_db()

    where_clauses = []
    params = []
    if province:
        where_clauses.append("s.province = ?")
        params.append(province)
    if city:
        where_clauses.append("s.city = ?")
        params.append(city)

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    # 获取所有有测评的学校
    rows = db.execute(f"""
        SELECT s.id as school_id, s.name as school_name, s.province, s.city,
               s.type, s.level,
               COUNT(r.id) as review_count,
               GROUP_CONCAT(r.category_scores, '|||') as all_cat_scores
        FROM schools s
        JOIN reviews r ON s.id = r.school_id
        {where_sql}
        GROUP BY s.id
        HAVING review_count >= 1
    """, params).fetchall()

    # 计算加权得分
    result = []
    for row in rows:
        d = dict(row)
        # 聚合所有测评的类别得分
        cat_sums = {k: [] for k in CAT_KEYS}
        if d.get("all_cat_scores"):
            for cs_str in d["all_cat_scores"].split("|||"):
                try:
                    cs = json.loads(cs_str)
                    for k in CAT_KEYS:
                        if cs.get(k, 0) > 0:
                            cat_sums[k].append(cs[k])
                except (json.JSONDecodeError, TypeError):
                    pass

        avg_scores = {}
        for k in CAT_KEYS:
            vals = cat_sums[k]
            avg_scores[k] = round(sum(vals) / len(vals), 2) if vals else 0
            d[f"avg_{k}"] = avg_scores[k]

        # 加权得分
        total_weight = sum(weights.get(k, 0) for k in CAT_KEYS if avg_scores.get(k, 0) > 0)
        if total_weight > 0:
            d["overall_score"] = round(
                sum(avg_scores.get(k, 0) * weights.get(k, 0) for k in CAT_KEYS if avg_scores.get(k, 0) > 0)
                / total_weight, 2
            )
        else:
            d["overall_score"] = 0
        result.append(d)

    result.sort(key=lambda x: x["overall_score"], reverse=True)

    for i, r in enumerate(result):
        r["rank"] = i + 1

    return jsonify(result)


@app.route("/api/school_compare")
def api_school_compare():
    """获取两所学校对比数据"""
    id1 = request.args.get("id1", type=int)
    id2 = request.args.get("id2", type=int)
    if not id1 or not id2:
        return jsonify({"error": "需要 id1 和 id2"}), 400

    db = get_db()
    result = {}
    for sid, label in [(id1, "school1"), (id2, "school2")]:
        school = db.execute("SELECT * FROM schools WHERE id = ?", (sid,)).fetchone()
        if not school:
            return jsonify({"error": f"学校 {sid} 不存在"}), 404

        rows = db.execute(
            "SELECT answers, category_scores FROM reviews WHERE school_id = ?",
            (sid,),
        ).fetchall()

        cat_sums = {k: [] for k in CAT_KEYS}
        for row in rows:
            try:
                cs = json.loads(row["category_scores"]) if row["category_scores"] else {}
            except (json.JSONDecodeError, TypeError):
                cs = {}
            for k in CAT_KEYS:
                if cs.get(k, 0) > 0:
                    cat_sums[k].append(cs[k])

        avg = {}
        for k in CAT_KEYS:
            vals = cat_sums[k]
            avg[k] = round(sum(vals) / len(vals), 2) if vals else 0

        total_weight = sum(CATEGORIES[k]["weight"] for k in CAT_KEYS if avg.get(k, 0) > 0)
        if total_weight > 0:
            avg["overall_score"] = round(
                sum(avg.get(k, 0) * CATEGORIES[k]["weight"] for k in CAT_KEYS if avg.get(k, 0) > 0)
                / total_weight, 2
            )
        else:
            avg["overall_score"] = 0
        avg["review_count"] = len(rows)

        # 问题比例统计
        question_stats = {}
        for q_id in QUESTION_TO_CAT:
            yes_count = 0
            no_count = 0
            for row in rows:
                try:
                    ans = json.loads(row["answers"]) if row["answers"] else {}
                except (json.JSONDecodeError, TypeError):
                    ans = {}
                if q_id in ans:
                    if ans[q_id]:
                        yes_count += 1
                    else:
                        no_count += 1
            total = yes_count + no_count
            if total > 0:
                question_stats[q_id] = {
                    "yes_count": yes_count,
                    "no_count": no_count,
                    "yes_pct": round(yes_count / total * 100, 1),
                    "no_pct": round(no_count / total * 100, 1),
                }
        avg["question_stats"] = question_stats

        result[label] = {"school": dict(school), "avg": avg}

    return jsonify(result)


@app.route("/api/stats")
def api_stats():
    db = get_db()
    stats = db.execute("""
        SELECT
            (SELECT COUNT(*) FROM schools) as school_count,
            (SELECT COUNT(*) FROM reviews) as review_count,
            (SELECT COUNT(DISTINCT major_id) FROM reviews) as major_count,
            (SELECT COUNT(*) FROM comments) as comment_count
    """).fetchone()
    return jsonify(dict(stats))


# ── 错误页面 ──
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html", msg="页面不存在"), 404


@app.errorhandler(500)
def internal_error(e):
    return render_template("404.html", msg="服务器错误"), 500


# ── 启动 ──────────────────────────────────────────────────
if __name__ == "__main__":
    with app.app_context():
        init_db()
    print(f"🚀 学之声 - 大学专业测评平台已启动，访问 http://0.0.0.0:{CONFIG['port']}")
    app.run(
        host=CONFIG["host"],
        port=CONFIG["port"],
        debug=CONFIG["debug"],
    )
