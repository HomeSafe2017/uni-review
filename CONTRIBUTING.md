# 贡献指南

感谢你对学之声项目的贡献意愿！

## 开发环境搭建

### 1. Fork & Clone

```bash
git clone <your-fork-url> uni-review
cd uni-review
```

### 2. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
python3 seed.py
python3 generate_reviews.py
```

### 4. 启动开发服务器

```bash
python3 app.py
```

访问 http://localhost:5210

开发模式下如需自动重载，修改 config.json 中 `debug` 为 `true`，或：

```bash
flask --app app run --debug --port 5210
```

## 代码规范

### Python (app.py, seed.py, generate_reviews.py)

- **缩进**：4空格
- **行宽**：不硬性限制，但建议不超过120字符
- **编码**：UTF-8，文件头声明 `# -*- coding: utf-8 -*-`
- **字符串**：优先使用双引号
- **命名**：
  - 函数/变量：snake_case（如 `get_school_avg`）
  - 常量：UPPER_SNAKE_CASE（如 `CATEGORIES`, `DATABASE`）
  - 路由函数：与URL对应（如 `school_detail`, `api_submit_review`）
- **数据库操作**：
  - 使用 `get_db()` 获取连接（自动管理连接生命周期）
  - 使用参数化查询，不要拼接SQL
  - JSON字段（answers, category_scores, tags）序列化/反序列化用 `json.dumps/loads`
- **依赖**：尽量使用Python标准库，不引入新pip依赖
- **配置**：可变内容放 `config.json`，不在代码中硬编码

### HTML/JS (templates/)

- **CSS框架**：Tailwind CSS（CDN引入），不写自定义CSS
- **JS库**：Chart.js（CDN引入），不引入其他JS框架
- **模板**：Jinja2，继承 `base.html`
- **暗色模式**：所有新UI元素必须支持暗色模式（使用Tailwind的 `dark:` 前缀）
- **移动端**：所有页面必须移动端可用（使用响应式类如 `sm:`, `md:`）
- **JS风格**：
  - Vanilla JS，不使用框架
  - 使用 `fetch()` 调用API
  - 使用 `async/await` 处理异步

### 配置文件 (config.json)

- 修改问题/权重/标签时保持JSON格式正确
- 问题ID一旦发布不要修改（影响已有数据）
- 新增问题ID用 snake_case 命名

## 项目架构说明

### app.py 结构

```
1. 配置加载 (第1-36行)
2. Jinja2过滤器 (第38-147行)
3. 数据库管理 (第151-239行)
4. 辅助函数 - 评分计算 (第242-408行)
5. 页面路由 (第411-598行)
6. API路由 (第601-1022行)
7. 错误处理 + 启动 (第1025-1045行)
```

### 数据流

```
用户提交测评 → /api/submit_review
  → 验证参数（设备ID、学校、专业、每个大类至少1题）
  → 检查重复（同一设备+学校+专业唯一）
  → calc_scores_from_answers() 计算得分
  → 存入 reviews 表（answers JSON + category_scores JSON + overall_score）
  → 返回结果

查看学校详情 → /school/<id>
  → get_school_avg() 聚合所有测评的category_scores
  → 计算各维度平均分 + 问题比例统计
  → 渲染 school.html（雷达图用Chart.js）
```

### 评分计算核心

`calc_scores_from_answers(answers)` 是评分核心函数，在 app.py 和 generate_reviews.py 中各有一份（需保持同步）：

1. 遍历8大类，每类的每个问题从answers中取值
2. 根据回答（true/false）取 yes_score 或 no_score
3. 大类得分 = 该类已答问题得分的平均值
4. 综合得分 = 各大类得分 × 权重的加权平均

## 提交流程

### 1. 创建分支

```bash
git checkout -b feature/your-feature
# 或
git checkout -b fix/your-fix
```

### 2. 开发 & 测试

```bash
# 修改代码后本地测试
python3 app.py

# 如果修改了数据库schema，需重建
rm -f data/uni_review.db
python3 seed.py
python3 generate_reviews.py
```

### 3. 提交

```bash
git add .
git commit -m "feat: 简要描述"   # 新功能
git commit -m "fix: 简要描述"    # 修复
git commit -m "docs: 简要描述"   # 文档
git commit -m "refactor: 简要描述" # 重构
```

Commit 格式：`<type>: <description>`

type 可选：feat / fix / docs / style / refactor / test / chore

### 4. 推送 & PR

```bash
git push origin feature/your-feature
# 然后在Git平台上创建Pull Request
```

## 常见开发任务

### 添加新的评测问题

1. 编辑 `config.json`，在对应大类的 `questions` 数组中添加新问题：
```json
{"id": "new_question_id", "text": "问题描述", "yes_score": 2, "no_score": 5}
```
2. 不需要修改数据库schema（answers是JSON字段）
3. 不需要重建数据库（旧测评自动跳过新问题）
4. 提交页面会自动渲染新问题

### 添加新的评测大类

1. 编辑 `config.json`，在 `categories` 中添加新大类
2. 在 `CAT_KEYS` 中会自动包含（因为代码中 `CAT_KEYS = list(CATEGORIES.keys())`）
3. 需要考虑权重分配（当前8类权重总和为100）
4. 旧测评不会包含新大类数据，平均分计算时自动跳过

### 添加新页面

1. 在 `app.py` 中添加路由函数
2. 在 `templates/` 中创建HTML模板，继承 `base.html`
3. 在 `base.html` 的导航栏中添加链接

### 添加新API

1. 在 `app.py` 的 API 区域添加路由
2. 返回 `jsonify()` 格式的JSON
3. 注意SQLite的并发写入限制

### 修改前端样式

- 使用 Tailwind CSS 类，不写自定义CSS
- 记得加 `dark:` 前缀支持暗色模式
- 用 `sm:` / `md:` / `lg:` 做响应式
- Chart.js 配置在模板的 `<script>` 中

## 注意事项

- **不要修改 seed.py 中的学校数据ID** — 已有测评通过 school_id 关联
- **不要修改 config.json 中已有问题的ID** — 已有测评的 answers 以ID为键
- **calc_scores_from_answers 函数有两份** — app.py 和 generate_reviews.py 中各有一份，修改评分逻辑时需同步更新
- **SQLite不适合高并发写入** — 如果需要支持大量用户同时提交，考虑迁移到 PostgreSQL
- **WAL模式** — 数据库默认使用WAL模式，支持读写并发，备份时注意 `-wal` 和 `-shm` 文件
