#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""大学专业综合测评平台 - 从学生视角评价学校和专业"""

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
app.secret_key = CONFIG["secret_key"]

DATABASE = os.path.join(BASE_DIR, CONFIG["database"])

# 维度信息
DIMENSIONS = CONFIG["dimensions"]
DIM_KEYS = list(DIMENSIONS.keys())
ALL_TAGS = CONFIG["tags"]


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
        professional_difficulty INTEGER NOT NULL CHECK(professional_difficulty BETWEEN 1 AND 5),
        teaching_quality INTEGER NOT NULL CHECK(teaching_quality BETWEEN 1 AND 5),
        college_atmosphere INTEGER NOT NULL CHECK(college_atmosphere BETWEEN 1 AND 5),
        dormitory INTEGER NOT NULL CHECK(dormitory BETWEEN 1 AND 5),
        cafeteria INTEGER NOT NULL CHECK(cafeteria BETWEEN 1 AND 5),
        campus_environment INTEGER NOT NULL CHECK(campus_environment BETWEEN 1 AND 5),
        infrastructure INTEGER NOT NULL CHECK(infrastructure BETWEEN 1 AND 5),
        employment_prospect INTEGER NOT NULL CHECK(employment_prospect BETWEEN 1 AND 5),
        extracurricular INTEGER NOT NULL CHECK(extracurricular BETWEEN 1 AND 5),
        mental_support INTEGER NOT NULL CHECK(mental_support BETWEEN 1 AND 5),
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
def calc_weighted_score(row, weights=None):
    """根据权重计算加权得分"""
    if weights is None:
        weights = {k: DIMENSIONS[k]["weight"] for k in DIM_KEYS}
    total_weight = sum(weights.values())
    if total_weight == 0:
        return 0
    score = sum(row[k] * weights.get(k, 0) for k in DIM_KEYS) / total_weight
    return round(score, 2)


def get_school_avg(school_id, weights=None):
    """获取学校各维度平均分和综合分"""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM reviews WHERE school_id = ?", (school_id,)
    ).fetchall()
    if not rows:
        return None
    avg = {}
    for k in DIM_KEYS:
        vals = [r[k] for r in rows if r[k] is not None]
        avg[k] = round(sum(vals) / len(vals), 2) if vals else 0
    avg["overall_score"] = calc_weighted_score(avg, weights)
    avg["review_count"] = len(rows)
    return avg


def get_major_avg_in_school(school_id, major_id, weights=None):
    """获取某校某专业各维度平均分"""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM reviews WHERE school_id = ? AND major_id = ?",
        (school_id, major_id),
    ).fetchall()
    if not rows:
        return None
    avg = {}
    for k in DIM_KEYS:
        vals = [r[k] for r in rows if r[k] is not None]
        avg[k] = round(sum(vals) / len(vals), 2) if vals else 0
    avg["overall_score"] = calc_weighted_score(avg, weights)
    avg["review_count"] = len(rows)
    return avg


# ── 路由 ──────────────────────────────────────────────────

# ── 首页 ──
@app.route("/")
def index():
    db = get_db()
    # 获取热门学校（按测评数排序）
    hot_schools = db.execute("""
        SELECT s.*, COUNT(r.id) as review_count,
               ROUND(AVG(r.overall_score), 2) as avg_score
        FROM schools s
        LEFT JOIN reviews r ON s.id = r.school_id
        GROUP BY s.id
        ORDER BY review_count DESC, avg_score DESC
        LIMIT 12
    """).fetchall()

    # 获取最新测评
    latest_reviews = db.execute("""
        SELECT r.*, s.name as school_name, m.name as major_name, m.category as major_category
        FROM reviews r
        JOIN schools s ON r.school_id = s.id
        JOIN majors m ON r.major_id = m.id
        ORDER BY r.created_at DESC
        LIMIT 10
    """).fetchall()

    # 获取统计
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
                           dimensions=DIMENSIONS,
                           dim_keys=DIM_KEYS)


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
                           dimensions=DIMENSIONS, dim_keys=DIM_KEYS)


# ── 学校详情 ──
@app.route("/school/<int:school_id>")
def school_detail(school_id):
    db = get_db()
    school = db.execute("SELECT * FROM schools WHERE id = ?", (school_id,)).fetchone()
    if not school:
        return render_template("404.html", msg="学校不存在"), 404

    # 学校各维度平均分
    avg = get_school_avg(school_id)

    # 该校各专业评分
    major_scores = db.execute("""
        SELECT m.id as major_id, m.name as major_name, m.category,
               COUNT(r.id) as review_count,
               ROUND(AVG(r.overall_score), 2) as avg_score
        FROM majors m
        JOIN reviews r ON m.id = r.major_id AND r.school_id = ?
        GROUP BY m.id
        ORDER BY avg_score DESC
    """, (school_id,)).fetchall()

    # 该校测评列表
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
                           dimensions=DIMENSIONS,
                           dim_keys=DIM_KEYS)


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
                           dimensions=DIMENSIONS,
                           dim_keys=DIM_KEYS)


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

    return render_template("review.html",
                           review=review,
                           comments=comments,
                           dimensions=DIMENSIONS,
                           dim_keys=DIM_KEYS)


# ── 提交测评 ──
@app.route("/submit")
def submit_page():
    db = get_db()
    schools = db.execute("SELECT id, name, province, city FROM schools ORDER BY name").fetchall()
    majors = db.execute("SELECT id, name, category FROM majors ORDER BY category, name").fetchall()
    return render_template("submit.html",
                           schools=schools,
                           majors=majors,
                           dimensions=DIMENSIONS,
                           dim_keys=DIM_KEYS,
                           tags=ALL_TAGS)


# ── 排名 ──
@app.route("/ranking")
def ranking_page():
    db = get_db()
    return render_template("ranking.html",
                           dimensions=DIMENSIONS,
                           dim_keys=DIM_KEYS)


# ── 对比 ──
@app.route("/compare")
def compare_page():
    db = get_db()
    schools = db.execute("SELECT id, name, province, city FROM schools ORDER BY name").fetchall()
    return render_template("compare.html",
                           schools=schools,
                           dimensions=DIMENSIONS,
                           dim_keys=DIM_KEYS)


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
    school_id = request.args.get("school_id", "")
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
    """根据经纬度查找附近的学校"""
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    radius = request.args.get("radius", default=50, type=float)  # km
    if lat is None or lng is None:
        return jsonify({"error": "需要 lat 和 lng 参数"}), 400

    db = get_db()
    # 使用简单的距离公式（Haversine近似）
    rows = db.execute("""
        SELECT id, name, province, city, latitude, longitude,
               (6371 * acos(
                   cos(radians(?)) * cos(radians(latitude)) *
                   cos(radians(longitude) - radians(?)) +
                   sin(radians(?)) * sin(radians(latitude))
               )) as distance
        FROM schools
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        HAVING distance < ?
        ORDER BY distance
        LIMIT 10
    """, (lat, lng, lat, radius)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/submit_review", methods=["POST"])
def api_submit_review():
    data = request.get_json()
    if not data:
        return jsonify({"error": "无效数据"}), 400

    device_id = data.get("device_id", "").strip()
    school_id = data.get("school_id")
    major_id = data.get("major_id")

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

    # 验证评分
    scores = {}
    for k in DIM_KEYS:
        val = data.get(k)
        if val is None or not (1 <= int(val) <= 5):
            return jsonify({"error": f"评分 {DIMENSIONS[k]['name']} 无效"}), 400
        scores[k] = int(val)

    # 计算综合分
    overall_score = calc_weighted_score(scores)

    comment = data.get("comment", "").strip()
    tags = data.get("tags", [])

    try:
        cursor = db.execute(
            f"""INSERT INTO reviews
            (school_id, major_id, device_id, {', '.join(DIM_KEYS)}, overall_score, comment, tags)
            VALUES (?, ?, ?, {', '.join(['?'] * len(DIM_KEYS))}, ?, ?, ?)""",
            (school_id, major_id, device_id,
             *[scores[k] for k in DIM_KEYS],
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
    target_type = data.get("target_type")  # 'review' or 'comment'
    target_id = data.get("target_id")

    if not device_id or target_type not in ("review", "comment") or not target_id:
        return jsonify({"error": "参数无效"}), 400

    db = get_db()
    # 检查是否已点赞
    existing = db.execute(
        "SELECT id FROM liked_records WHERE device_id = ? AND target_type = ? AND target_id = ?",
        (device_id, target_type, target_id),
    ).fetchone()

    if existing:
        # 取消点赞
        db.execute("DELETE FROM liked_records WHERE id = ?", (existing["id"],))
        table = "reviews" if target_type == "review" else "comments"
        db.execute(f"UPDATE {table} SET likes = likes - 1 WHERE id = ?", (target_id,))
        db.commit()
        return jsonify({"success": True, "liked": False})
    else:
        # 点赞
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
    # 获取权重参数
    weights = {}
    for k in DIM_KEYS:
        w = request.args.get(f"w_{k}", default=DIMENSIONS[k]["weight"], type=float)
        weights[k] = w

    province = request.args.get("province", "")
    city = request.args.get("city", "")

    db = get_db()

    # 构建查询
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

    rows = db.execute(f"""
        SELECT s.id as school_id, s.name as school_name, s.province, s.city,
               s.type, s.level,
               COUNT(r.id) as review_count,
               {', '.join(f'ROUND(AVG(r.{k}), 2) as avg_{k}' for k in DIM_KEYS)}
        FROM schools s
        JOIN reviews r ON s.id = r.school_id
        {where_sql}
        GROUP BY s.id
        HAVING review_count >= 1
    """, params).fetchall()

    # 计算加权得分并排序
    result = []
    for row in rows:
        d = dict(row)
        scores = {k: d[f"avg_{k}"] for k in DIM_KEYS}
        d["overall_score"] = calc_weighted_score(scores, weights)
        result.append(d)

    result.sort(key=lambda x: x["overall_score"], reverse=True)

    # 添加排名
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

        avg_rows = db.execute("""
            SELECT {fields}
            FROM reviews WHERE school_id = ?
        """.format(fields=", ".join(DIM_KEYS)), (sid,)).fetchall()

        avg = {}
        for k in DIM_KEYS:
            vals = [r[k] for r in avg_rows if r[k] is not None]
            avg[k] = round(sum(vals) / len(vals), 2) if vals else 0
        avg["overall_score"] = calc_weighted_score(avg)
        avg["review_count"] = len(avg_rows)

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
    print(f"🚀 大学专业测评平台已启动，访问 http://0.0.0.0:{CONFIG['port']}")
    app.run(
        host=CONFIG["host"],
        port=CONFIG["port"],
        debug=CONFIG["debug"],
    )
