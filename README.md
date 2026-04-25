# 学之声 (uni-review)

大学专业综合测评平台 —— 从学生视角评价学校和专业。

不是论文数和院士数，而是食堂好不好吃、空调有没有、老师人好不好。

## 功能特性

- **学校搜索 + 定位** — 支持关键词搜索，GPS/IP自动定位附近学校（多校区支持）
- **8大类52问题测评问卷** — 学业管理、宿舍条件、食堂餐饮、消费透明度、校园环境、就业前景、管理服务、心理人际
- **加权综合评分** — 每类有独立权重，综合分按加权平均计算，支持自定义权重排名
- **学校/专业详情页** — 雷达图 + 8维度详情 + 每题有无比例统计
- **排名页** — 支持按省份/城市筛选，权重可调
- **学校对比页** — 两校雷达图叠加对比
- **点赞/评论系统** — 设备指纹防重复提交，点赞可撤销
- **暗色模式** — 跟随系统或手动切换
- **移动端适配** — 响应式布局

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3 + Flask 3.1 |
| 数据库 | SQLite (WAL模式) |
| 前端 | Tailwind CSS + Chart.js + Vanilla JS |
| 模板 | Jinja2 |
| 部署 | Gunicorn + Nginx |

## 项目结构

```
uni-review/
├── app.py              # Flask主应用（路由、API、评分计算）
├── config.json         # 配置文件（8大类52问题+权重+标签+端口）
├── seed.py             # 种子数据（316所学校+562个校区+85个专业）
├── generate_reviews.py # 假测评数据生成（约1432条）
├── requirements.txt    # Python依赖
├── data/
│   └── uni_review.db   # SQLite数据库
├── templates/          # Jinja2模板
│   ├── base.html       # 基础布局（导航、暗色模式、Tailwind CDN）
│   ├── index.html      # 首页
│   ├── search.html     # 搜索结果
│   ├── school.html     # 学校详情
│   ├── major.html      # 专业详情（在某校下）
│   ├── review.html     # 测评详情
│   ├── submit.html     # 提交测评
│   ├── ranking.html    # 排名页
│   ├── compare.html    # 学校对比
│   └── 404.html        # 错误页
├── static/             # 静态资源目录（当前为空，使用CDN）
├── SPEC.md             # 重构规格书
└── history.md          # 操作记录
```

## 快速启动

### 1. 克隆项目

```bash
git clone <repo-url> uni-review
cd uni-review
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

仅依赖 `flask==3.1.0`，无其他第三方库。

### 3. 初始化数据库

```bash
# 方式一：从零开始
python3 seed.py          # 建表 + 插入316所学校、562个校区、85个专业
python3 generate_reviews.py  # 生成约1432条假测评数据

# 方式二：使用已有数据库（如果data/uni_review.db已存在）
# 直接启动即可
```

### 4. 启动开发服务器

```bash
python3 app.py
```

访问 http://localhost:5210

## 评分体系

### 8大评测维度及权重

| 维度 | 图标 | 权重 | 问题数 |
|------|------|------|--------|
| 学业管理 | 📚 | 15 | 7 |
| 宿舍条件 | 🏠 | 25 | 9 |
| 食堂餐饮 | 🍚 | 15 | 6 |
| 消费透明度 | 💰 | 10 | 6 |
| 校园环境 | 🌳 | 8 | 6 |
| 就业前景 | 💼 | 20 | 7 |
| 管理服务 | 🏛️ | 5 | 7 |
| 心理人际 | 💚 | 2 | 3 |

### 评分逻辑

每个问题为「有无类」问题（是/否），回答对应不同分数（1-5分制）：

- **负面问题**（有此情况=差）：有=低分，无=高分。例："是否强制校园跑" → 有=1, 无=5
- **正面问题**（有此情况=好）：有=高分，无=低分。例："是否有独立卫浴" → 有=5, 无=1

大类得分 = 该类所有已答问题得分的平均值
综合得分 = 各大类得分 × 权重的加权平均

### 标签系统

25个预设标签，如：内卷严重、食堂神仙、空调自由、宿舍破旧、就业困难、形式主义、水电刺客、就业率注水等。

## 数据库表结构

| 表 | 说明 |
|---|---|
| schools | 学校（名称、省份、城市、区县、经纬度、类型、层次） |
| campuses | 校区（多校区大学，独立经纬度） |
| majors | 专业（名称、学科类别） |
| reviews | 测评（学校+专业+设备ID、answers JSON、分类得分JSON、综合分、评论、标签） |
| comments | 评论 |
| liked_records | 点赞记录（防重复点赞） |

## API一览

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/schools` | GET | 搜索学校（?q=关键词） |
| `/api/majors` | GET | 搜索专业（?q=关键词） |
| `/api/nearby_schools` | GET | 附近学校（?lat=&lng=） |
| `/api/detect_location` | GET | IP定位 |
| `/api/submit_review` | POST | 提交测评 |
| `/api/check_review` | GET | 检查是否已提交 |
| `/api/comment` | POST | 发表评论 |
| `/api/like` | POST | 点赞/取消点赞 |
| `/api/ranking` | GET | 排名数据（支持自定义权重） |
| `/api/school_compare` | GET | 学校对比（?id1=&id2=） |
| `/api/stats` | GET | 全站统计 |

## 配置说明

所有可变配置在 `config.json` 中：

- `host` / `port` — 监听地址和端口
- `debug` — 调试模式（生产环境必须为false）
- `database` — SQLite数据库路径
- `secret_key` — Flask密钥
- `categories` — 8大类及问题定义（修改后需重建数据库）
- `tags` — 预设标签列表

## 相关文档

- [DEPLOY.md](DEPLOY.md) — 部署文档
- [MIGRATION.md](MIGRATION.md) — 数据迁移文档
- [CONTRIBUTING.md](CONTRIBUTING.md) — 贡献指南
- [SPEC.md](SPEC.md) — 重构规格书

## License

MIT
