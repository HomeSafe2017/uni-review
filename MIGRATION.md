# 数据迁移文档

## 概述

学之声使用 SQLite 数据库，数据存储在 `data/uni_review.db`。项目涉及两类数据：

1. **种子数据** — 学校、校区、专业（由 seed.py 管理）
2. **用户数据** — 测评、评论、点赞记录（由用户产生或 generate_reviews.py 生成）

## 数据库备份与恢复

### 备份

```bash
# 方式一：直接复制（需先停服务）
pkill -f "gunicorn.*app:app"
cp data/uni_review.db data/uni_review.db.bak.$(date +%Y%m%d)
# 重启
gunicorn -w 2 -b 0.0.0.0:5210 --daemon app:app

# 方式二：SQLite在线备份（不需停服务）
sqlite3 data/uni_review.db ".backup data/uni_review.db.bak.$(date +%Y%m%d)"

# 方式三：导出SQL文本
sqlite3 data/uni_review.db .dump > backup_$(date +%Y%m%d).sql
```

### 恢复

```bash
# 从.db文件恢复
pkill -f "gunicorn.*app:app"
cp data/uni_review.db.bak.20260425 data/uni_review.db
gunicorn -w 2 -b 0.0.0.0:5210 --daemon app:app

# 从SQL文本恢复
pkill -f "gunicorn.*app:app"
rm -f data/uni_review.db
sqlite3 data/uni_review.db < backup_20260425.sql
gunicorn -w 2 -b 0.0.0.0:5210 --daemon app:app
```

### 远程服务器备份

```bash
# 下载远程数据库到本地
scp root@YOUR_SERVER_IP:/root/uni-review/data/uni_review.db ./backup_remote_$(date +%Y%m%d).db

# 上传本地数据库到远程（覆盖！谨慎操作）
scp data/uni_review.db root@YOUR_SERVER_IP:/root/uni-review/data/uni_review.db
ssh root@YOUR_SERVER_IP "pkill -f 'gunicorn.*app:app'; sleep 1; cd /root/uni-review && gunicorn -w 2 -b 0.0.0.0:5210 --daemon app:app"
```

## 种子数据重建

### 完整重建流程（清除所有数据）

```bash
cd /root/uni-review

# 1. 停止服务
pkill -f "gunicorn.*app:app"

# 2. 删除旧数据库
rm -f data/uni_review.db data/uni_review.db-wal data/uni_review.db-shm

# 3. 重建种子数据
python3 seed.py
# 输出示例：
# ✅ 已插入 316 所学校, 562 个校区, 85 个专业

# 4. 生成假测评数据（可选）
python3 generate_reviews.py
# 输出示例：
# ✅ 已生成 1432 条测评数据
#    覆盖 316 所学校, 85 个专业
#    综合分范围: 1.5 ~ 4.3, 平均: 2.87

# 5. 重启服务
gunicorn -w 2 -b 0.0.0.0:5210 --daemon app:app
```

### 仅重建种子数据（保留用户测评）

```bash
# 注意：此操作会删除所有用户测评数据！
# 因为 reviews 表依赖 schools 和 majors 的外键

# 如果只想新增学校/专业，建议直接操作数据库：
python3 -c "
import sqlite3
conn = sqlite3.connect('data/uni_review.db')
# 示例：添加一所新学校
conn.execute('INSERT OR IGNORE INTO schools (name, province, city, district, latitude, longitude, type, level) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
    ('测试大学', '北京', '北京', '海淀区', 39.9, 116.3, '综合', '普通'))
conn.commit()
conn.close()
print('OK')
"
```

### seed.py 详解

seed.py 会在数据库不存在时创建表并插入数据：

| 数据 | 数量 | 来源 |
|------|------|------|
| schools | 316所 | SCHOOLS列表（覆盖全国31省） |
| campuses | 562个 | CAMPUSES列表（多校区大学） |
| majors | 85个 | 固定列表（工学/理学/文学等12个学科门类） |

学校层次分布：
- 985/211：约40所
- 211：约70所
- 双一流：约20所
- 普通：约186所

### generate_reviews.py 详解

假数据生成逻辑：

1. 每所学校根据层次选择1-5个相关专业生成测评
2. 每个专业生成1-3条测评
3. 评分根据学校层次+类型+专业类别智能调整（985偏高分、农林偏僻等）
4. 评论由模板+高亮片段组合，所有假数据评论标注"指标来源网络"
5. 标签根据评分自动匹配
6. 使用固定种子 `random.seed(42)`，结果可复现
7. device_id 格式为 `seed_{school_id}_{major_id}_{i}`，用于区分假数据和真实用户数据

## 数据库操作常用命令

### 查看数据统计

```bash
sqlite3 data/uni_review.db "
SELECT
  (SELECT COUNT(*) FROM schools) as schools,
  (SELECT COUNT(*) FROM campuses) as campuses,
  (SELECT COUNT(*) FROM majors) as majors,
  (SELECT COUNT(*) FROM reviews) as reviews,
  (SELECT COUNT(*) FROM comments) as comments;
"
```

### 查看用户测评（非种子数据）

```bash
sqlite3 data/uni_review.db "
SELECT COUNT(*) FROM reviews WHERE device_id NOT LIKE 'seed_%';
"
```

### 查看测评分布

```bash
sqlite3 data/uni_review.db "
SELECT
  ROUND(overall_score, 0) as score_range,
  COUNT(*) as count
FROM reviews
GROUP BY score_range
ORDER BY score_range;
"
```

### 清理假数据（保留真实用户数据）

```bash
sqlite3 data/uni_review.db "
DELETE FROM reviews WHERE device_id LIKE 'seed_%';
DELETE FROM comments WHERE review_id NOT IN (SELECT id FROM reviews);
DELETE FROM liked_records WHERE target_type='review' AND target_id NOT IN (SELECT id FROM reviews);
VACUUM;
"
```

### 检查数据库完整性

```bash
sqlite3 data/uni_review.db "PRAGMA integrity_check;"
```

### 压缩数据库（清理碎片空间）

```bash
sqlite3 data/uni_review.db "VACUUM;"
```

## 版本升级注意事项

### config.json 中 categories 变更

如果修改了 `config.json` 中的 categories（增加/删除/修改问题），需要注意：

1. **新增问题** — 已有测评的 answers JSON 中不会包含新问题ID，计算得分时自动跳过，不影响旧数据
2. **删除问题** — 已有测评的 answers 中可能包含已删除的问题ID，计算时自动忽略（因为新config中找不到该ID）
3. **修改问题ID** — 等同于删除旧问题+新增新问题，旧数据中旧ID的回答将失效
4. **修改权重** — 只影响排名和综合分计算，不需要重建数据库
5. **修改分数映射** (yes_score/no_score) — 影响已有数据的得分计算，但answers不变，重新计算时使用新分数

**安全变更**（不需要重建数据库）：
- 修改权重
- 修改问题文本（text）
- 修改问题分数映射
- 新增问题

**危险变更**（需要重建或迁移数据库）：
- 修改问题ID
- 删除问题（旧数据回答残留但不影响功能）

### 数据库表结构变更

app.py 中使用 `CREATE TABLE IF NOT EXISTS`，不会自动修改已有表结构。如需修改表结构：

```bash
# 方式一：重建（丢失所有数据）
rm -f data/uni_review.db
python3 seed.py
python3 generate_reviews.py

# 方式二：手动迁移（保留数据）
sqlite3 data/uni_review.db "
ALTER TABLE reviews ADD COLUMN new_column TEXT DEFAULT '';
"
```

### 从旧版滑块评分迁移到有无类问卷

如果从旧版（10维度滑块）升级到当前版本（8大类52问题），数据库schema不兼容，必须重建：

```bash
# 备份旧数据
cp data/uni_review.db data/uni_review_old.db

# 重建
rm -f data/uni_review.db
python3 seed.py
python3 generate_reviews.py
```

旧版测评数据无法自动迁移，因为评分体系完全不同。

## 数据安全建议

1. **定期备份** — 建议每日自动备份用户数据到其他服务器或对象存储
2. **区分假数据** — seed生成的device_id以 `seed_` 开头，可用于过滤
3. **WAL模式** — 数据库默认使用WAL模式，支持读写并发，但需注意 `-wal` 和 `-shm` 文件也要一起备份
4. **外键约束** — reviews 表有 `UNIQUE(school_id, major_id, device_id)` 约束，同一设备不能重复评价同一学校同一专业
