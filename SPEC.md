# 学之声 - 大规模重构规格书

## 一、核心改动：评分体系从"滑块打分"改为"有无类问卷"

### 1.1 新评分体系设计

将原来10个滑块维度改为 **8个大类 × 若干"有无"问题** 的形式。
每个问题回答"有/是"或"无/否"，每个回答对应一个分数（1-5分制）。
大类得分 = 该类所有问题得分的平均值。
综合得分 = 各大类得分的加权平均值。

**评分逻辑**：
- "负面"问题（有此情况=差）：有=低分，无=高分。例："是否强制校园跑" → 有=1, 无=5
- "正面"问题（有此情况=好）：有=高分，无=低分。例："是否有独立卫浴" → 有=5, 无=1

### 1.2 新 config.json 结构

```json
{
  "host": "0.0.0.0",
  "port": 5210,
  "debug": false,
  "database": "data/uni_review.db",
  "secret_key": "uni-review-secret-key-2026",
  "categories": {
    "academic": {
      "name": "学业管理",
      "icon": "📚",
      "weight": 15,
      "questions": [
        {"id": "forced_run", "text": "学校是否强制校园跑", "yes_score": 1, "no_score": 5},
        {"id": "forced_study", "text": "学校是否强制早晚自习", "yes_score": 1, "no_score": 5},
        {"id": "hard_course_select", "text": "选课是否需要抢（热门课秒没）", "yes_score": 2, "no_score": 5},
        {"id": "system_crash", "text": "教务系统是否经常崩溃", "yes_score": 1, "no_score": 5},
        {"id": "bad_curriculum", "text": "课程设置是否不合理（水课多）", "yes_score": 2, "no_score": 5},
        {"id": "forced_lecture", "text": "是否强制参加无意义的讲座/会议", "yes_score": 2, "no_score": 5},
        {"id": "bad_exam_schedule", "text": "考试安排是否不合理（集中/冲突）", "yes_score": 2, "no_score": 5}
      ]
    },
    "dormitory": {
      "name": "宿舍条件",
      "icon": "🏠",
      "weight": 25,
      "questions": [
        {"id": "private_bathroom", "text": "宿舍是否有独立卫浴", "yes_score": 5, "no_score": 1},
        {"id": "has_ac", "text": "宿舍是否有空调", "yes_score": 5, "no_score": 1},
        {"id": "power_limit", "text": "宿舍是否限电/限瓦数", "yes_score": 1, "no_score": 5},
        {"id": "has_curfew", "text": "宿舍是否有门禁（晚归锁门）", "yes_score": 2, "no_score": 5},
        {"id": "bunk_bed", "text": "宿舍是否为上下铺（非上床下桌）", "yes_score": 2, "no_score": 5},
        {"id": "over_6_room", "text": "宿舍是否超过6人（8人间/10人间）", "yes_score": 1, "no_score": 5},
        {"id": "room_check", "text": "宿舍是否查寝/强制卫生检查", "yes_score": 2, "no_score": 5},
        {"id": "hot_water_24h", "text": "宿舍是否有24小时热水", "yes_score": 5, "no_score": 2},
        {"id": "laundry_access", "text": "宿舍是否可洗衣（洗衣房/自装）", "yes_score": 5, "no_score": 2}
      ]
    },
    "cafeteria": {
      "name": "食堂餐饮",
      "icon": "🍚",
      "weight": 15,
      "questions": [
        {"id": "bad_food", "text": "食堂饭菜是否普遍难吃", "yes_score": 1, "no_score": 5},
        {"id": "expensive_food", "text": "食堂价格是否偏贵", "yes_score": 2, "no_score": 5},
        {"id": "food_safety_issue", "text": "食堂是否有食品安全问题", "yes_score": 1, "no_score": 5},
        {"id": "limited_variety", "text": "食堂种类是否单一", "yes_score": 2, "no_score": 5},
        {"id": "no_delivery", "text": "学校是否禁止外卖进校/进宿舍", "yes_score": 2, "no_score": 5},
        {"id": "no_nearby_food", "text": "校园周边是否没有足够的餐饮选择", "yes_score": 2, "no_score": 5}
      ]
    },
    "cost": {
      "name": "消费透明度",
      "icon": "💰",
      "weight": 10,
      "questions": [
        {"id": "expensive_utilities", "text": "宿舍水电费是否收费高昂/不透明", "yes_score": 1, "no_score": 5},
        {"id": "hidden_fees", "text": "学校是否存在隐形消费（强制购买教材等）", "yes_score": 1, "no_score": 5},
        {"id": "bad_internet", "text": "校园网是否收费且质量差", "yes_score": 2, "no_score": 5},
        {"id": "forced_internship_fee", "text": "是否存在强制收费实习", "yes_score": 1, "no_score": 5},
        {"id": "unclear_fees", "text": "学费之外是否有大量杂费不明不白", "yes_score": 1, "no_score": 5},
        {"id": "campus_monopoly", "text": "校园内消费是否被垄断（仅校园卡/高价小卖部）", "yes_score": 2, "no_score": 5}
      ]
    },
    "environment": {
      "name": "校园环境",
      "icon": "🌳",
      "weight": 8,
      "questions": [
        {"id": "remote_location", "text": "校区是否偏僻（远离市区/交通不便）", "yes_score": 1, "no_score": 5},
        {"id": "small_campus", "text": "校园面积是否过小", "yes_score": 2, "no_score": 5},
        {"id": "poor_facilities", "text": "校园是否有完善的体育/活动设施", "yes_score": 5, "no_score": 2},
        {"id": "no_transit", "text": "学校是否不在交通干线附近", "yes_score": 2, "no_score": 5},
        {"id": "bad_security", "text": "校园及周边治安是否不佳", "yes_score": 1, "no_score": 5},
        {"id": "multi_campus", "text": "学校是否存在多校区通勤问题", "yes_score": 2, "no_score": 5}
      ]
    },
    "employment": {
      "name": "就业前景",
      "icon": "💼",
      "weight": 20,
      "questions": [
        {"id": "fake_employment_rate", "text": "学校公布的就业率是否虚高/注水", "yes_score": 1, "no_score": 5},
        {"id": "forced_sign", "text": "学校是否强制签就业协议（凑就业率）", "yes_score": 1, "no_score": 5},
        {"id": "useless_career_center", "text": "学校就业指导是否形同虚设", "yes_score": 2, "no_score": 5},
        {"id": "bad_job_fair", "text": "校园招聘会质量是否低下", "yes_score": 2, "no_score": 5},
        {"id": "low_recognition", "text": "学校/专业是否在就业市场认可度低", "yes_score": 1, "no_score": 5},
        {"id": "trap_major", "text": "专业是否属于"天坑专业"（就业困难）", "yes_score": 2, "no_score": 5},
        {"id": "forced_factory", "text": "学校是否强制去工厂/无关岗位实习", "yes_score": 1, "no_score": 5}
      ]
    },
    "admin": {
      "name": "管理服务",
      "icon": "🏛️",
      "weight": 5,
      "questions": [
        {"id": "slow_admin", "text": "学校行政是否效率低下（办事难）", "yes_score": 1, "no_score": 5},
        {"id": "bad_counselor", "text": "辅导员是否不作为/偏心", "yes_score": 2, "no_score": 5},
        {"id": "formalism", "text": "学校形式主义是否严重", "yes_score": 1, "no_score": 5},
        {"id": "unfair_scholarship", "text": "奖助学金评定是否不公平", "yes_score": 2, "no_score": 5},
        {"id": "no_feedback_channel", "text": "学校是否没有有效的投诉/反馈渠道", "yes_score": 2, "no_score": 5},
        {"id": "random_plan_change", "text": "学校是否随意更改培养方案", "yes_score": 2, "no_score": 5},
        {"id": "bureaucracy", "text": "是否存在学生会官僚作风", "yes_score": 1, "no_score": 5}
      ]
    },
    "mental": {
      "name": "心理人际",
      "icon": "💚",
      "weight": 2,
      "questions": [
        {"id": "no_counseling", "text": "学校是否没有可及的心理咨询服务", "yes_score": 2, "no_score": 5},
        {"id": "no_room_change", "text": "学校是否没有室友调换机制", "yes_score": 2, "no_score": 5},
        {"id": "bad_club", "text": "学校社团/活动氛围是否很差", "yes_score": 2, "no_score": 5}
      ]
    }
  },
  "tags": [
    "内卷严重", "佛系养身", "食堂神仙", "食堂地狱", "空调自由",
    "空调绝缘", "电梯便利", "爬楼达人", "校园巨美", "校园荒凉",
    "宿舍豪华", "宿舍破旧", "老师超好", "老师摆烂", "就业无忧",
    "就业困难", "WiFi飞起", "WiFi龟速", "图书馆霸位", "社团丰富",
    "强制校园跑", "强制早晚自习", "形式主义", "水电刺客", "就业率注水"
  ]
}
```

### 1.3 数据库变更

**删除旧 reviews 表的10个维度列，改为 answers JSON 字段**：

```sql
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    major_id INTEGER NOT NULL,
    device_id TEXT NOT NULL,
    answers TEXT NOT NULL DEFAULT '{}',  -- JSON: {"forced_run": true, "has_ac": false, ...}
    category_scores TEXT NOT NULL DEFAULT '{}',  -- JSON: {"academic": 3.5, "dormitory": 2.8, ...}
    overall_score REAL,
    comment TEXT,
    tags TEXT,
    likes INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (school_id) REFERENCES schools(id),
    FOREIGN KEY (major_id) REFERENCES majors(id),
    UNIQUE(school_id, major_id, device_id)
);
```

### 1.4 评分计算逻辑

```python
def calc_scores_from_answers(answers, categories_config):
    """从有无答案计算各大类得分和综合得分"""
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
    total_weight = sum(cat_info["weight"] for cat_key, cat_info in categories_config.items() if category_scores.get(cat_key, 0) > 0)
    if total_weight == 0:
        overall = 0
    else:
        overall = sum(
            category_scores.get(cat_key, 0) * cat_info["weight"]
            for cat_key, cat_info in categories_config.items()
            if category_scores.get(cat_key, 0) > 0
        ) / total_weight
    return category_scores, round(overall, 2)
```

## 二、提交测评页面改造 (submit.html)

### 2.1 问卷UI

把原来的10个滑块替换为8个大类卡片，每个卡片内有若干"有无"问题，使用 **开关切换按钮（toggle switch）** 来回答。

UI 示例：
```
┌─────────────────────────────────────────┐
│ 🏠 宿舍条件                             │
│                                         │
│ 宿舍是否有独立卫浴？      [有 ●━━ 无]   │
│ 宿舍是否有空调？          [有 ●━━ 无]   │
│ 宿舍是否限电/限瓦数？     [有 ━━● 无]   │
│ 宿舍是否有门禁？          [有 ●━━ 无]   │
│ ...                                     │
│                                         │
│ 📊 本类预估得分：3.4/5                  │
└─────────────────────────────────────────┘
```

- 每个问题的toggle默认在中间"未选"状态（灰色），用户必须点击选择"有"或"无"
- "有"在左，"无"在右（对于负面问题）或反过来
- 实际上统一为：左侧=是/有（绿色/红色取决于正负面），右侧=否/无
- 但为了简化UI，统一为：**左=是/有，右=否/无**，用颜色区分正面/负面
  - 正面问题（有=好）：选中"有"时toggle变绿，选中"无"时toggle变灰
  - 负面问题（有=差）：选中"有"时toggle变红，选中"无"时toggle变绿
- 每个大类卡片底部实时显示该类的预估平均得分
- 全部选完后底部显示综合预估得分

### 2.2 问题未答提示

提交时如果某个大类完全没有作答，提示"请至少回答每个大类中的1个问题"。

## 三、学校/专业详情页改造 (school.html, major.html, review.html, ranking.html)

### 3.1 显示方式

- 不再显示10个维度的滑块/进度条
- 改为显示8个大类卡片，每个卡片显示：
  - 大类名称 + 图标 + 平均分（如 🏠 宿舍条件 3.4/5）
  - 星级显示（★★★☆☆）
  - 展开后显示该类所有问题的"是/否"比例（如：独立卫浴：有 72% / 无 28%）
- 综合评分显示方式不变（分数/5 + 星级）

### 3.2 雷达图更新

雷达图的8个轴对应8个大类，数值为该类平均分。

## 四、扩充学校数据

将学校数量从62所扩充到 **300+所**，覆盖：
- 39所985高校
- 112所211高校（含985）
- 各省重点高校
- 常见被学生讨论的二本/三本院校

每所学校需要：name, province, city, district, latitude, longitude, type(综合/理工/师范/财经/医药/政法/农林/艺术/体育), level(985/211/双一流/普通一本/二本/三本/专科)

**注意：经纬度必须真实可用**，用于定位功能。

## 五、修复定位功能

### 5.1 问题分析

当前定位使用 `navigator.geolocation` API，在 HTTP 环境下被浏览器禁止（需要HTTPS）。
由于服务器没有SSL证书，浏览器端定位不可用。

### 5.2 修复方案

**双模式定位**：
1. 优先尝试浏览器定位（HTTPS下可用）
2. 浏览器定位失败时，改用 **服务端IP定位**：前端调用 `/api/detect_location`，服务端使用免费IP定位API（如 ip-api.com）获取用户位置，然后查找最近学校

后端新增API：
```python
@app.route("/api/detect_location")
def detect_location():
    # 使用 ip-api.com 免费API（无需key，限45次/分钟）
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    try:
        import urllib.request
        resp = urllib.request.urlopen(f"http://ip-api.com/json/{user_ip}?lang=zh-CN&fields=status,lat,lon")
        data = json.loads(resp.read())
        if data.get("status") == "success":
            lat, lng = data["lat"], data["lon"]
            # 查找最近的学校
            nearby = db.execute("""
                SELECT *, (
                    6371 * acos(cos(radians(?)) * cos(radians(latitude)) *
                    cos(radians(longitude) - radians(?)) + sin(radians(?)) *
                    sin(radians(latitude)))
                ) AS distance
                FROM schools WHERE latitude IS NOT NULL
                ORDER BY distance LIMIT 5
            """, (lat, lng, lat)).fetchall()
            return jsonify([dict(r) for r in nearby])
    except:
        pass
    return jsonify([])
```

前端修改 `detectLocation()` 函数：
```javascript
async function detectLocation() {
    // 方案1：浏览器定位
    if (navigator.geolocation) {
        try {
            const pos = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 });
            });
            // 使用浏览器定位...
            return;
        } catch(e) {
            // 浏览器定位失败，尝试IP定位
        }
    }
    // 方案2：IP定位
    try {
        const resp = await fetch('/api/detect_location');
        const data = await resp.json();
        if (data.length > 0) {
            const nearest = data[0];
            selectSchool(nearest.id, nearest.name, nearest.province + ' ' + nearest.city);
        } else {
            alert('定位失败，请手动搜索学校');
        }
    } catch(e) {
        alert('定位失败，请手动搜索学校');
    }
}
```

## 六、实施步骤

1. **更新 config.json** — 替换为新的大类/问题结构
2. **更新 app.py** — 
   - 更新数据库schema（reviews表改为answers JSON）
   - 更新评分计算逻辑（从滑块分数改为有无答案计算）
   - 更新所有路由和API
   - 新增 /api/detect_location 接口
   - 更新 Jinja2 过滤器
3. **更新所有模板** — submit/school/major/review/ranking/compare
4. **更新 seed.py** — 扩充学校数据至300+所，更新种子测评数据格式
5. **删除旧数据库** — 重新初始化

## 七、注意事项

- 代码中使用 Python 标准库，不引入新的 pip 依赖
- 所有可变内容在 config.json 中配置
- 模板使用 Tailwind CSS + Chart.js
- 保持暗色模式支持
- 保持移动端适配
