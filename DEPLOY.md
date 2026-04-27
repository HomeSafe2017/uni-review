# 部署文档

## 环境要求

- Python 3.8+
- SQLite 3
- Nginx（可选，用于反代和SSL）
- 2核CPU / 1GB内存即可运行

## 安装步骤

### 1. 服务器准备

```bash
# 更新系统
apt update && apt upgrade -y

# 安装Python3和pip
apt install -y python3 python3-pip python3-venv
```

### 2. 部署项目

```bash
# 创建项目目录
mkdir -p /root/uni-review
cd /root/uni-review

# 上传项目文件（从本地）
# 本地执行：
tar czf /tmp/uni-review.tar.gz --exclude='__pycache__' --exclude='.git' --exclude='data/uni_review.db' .
scp /tmp/uni-review.tar.gz root@YOUR_SERVER_IP:/root/uni-review/

# 服务器执行：
cd /root/uni-review
tar xzf uni-review.tar.gz
rm -f uni-review.tar.gz

# 安装依赖
pip3 install -r requirements.txt
# 或使用虚拟环境：
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
cd /root/uni-review
python3 seed.py
python3 generate_reviews.py
```

### 4. 验证启动

```bash
# 先用Flask开发服务器测试
python3 app.py
# 访问 http://YOUR_SERVER_IP:5210 确认正常后 Ctrl+C 退出
```

## Gunicorn 配置

### 手动启动

```bash
cd /root/uni-review
gunicorn -w 2 -b 0.0.0.0:5210 --daemon app:app
```

参数说明：
- `-w 2` — 2个worker进程（SQLite不适合太多并发写，2个即可）
- `-b 0.0.0.0:5210` — 监听所有网卡的5210端口
- `--daemon` — 后台运行
- `app:app` — app.py文件中的app对象

### 停止 Gunicorn

```bash
# 查找进程
ps aux | grep gunicorn

# 停止（发送TERM信号）
pkill -f "gunicorn.*app:app"

# 强制停止
pkill -9 -f "gunicorn.*app:app"
```

### 重启 Gunicorn

```bash
pkill -f "gunicorn.*app:app" && sleep 1 && cd /root/uni-review && gunicorn -w 2 -b 0.0.0.0:5210 --daemon app:app
```

## Systemd 服务配置

创建服务文件：

```bash
cat > /etc/systemd/system/uni-review.service << 'EOF'
[Unit]
Description=学之声 - 大学专业测评平台
After=network.target

[Service]
Type=notify
User=root
WorkingDirectory=/root/uni-review
Environment=PATH=/root/uni-review/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/root/uni-review/venv/bin/gunicorn -w 2 -b 0.0.0.0:5210 app:app
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

如果没用虚拟环境，把PATH和ExecStart改为系统Python路径。

启用并启动：

```bash
systemctl daemon-reload
systemctl enable uni-review
systemctl start uni-review

# 查看状态
systemctl status uni-review

# 查看日志
journalctl -u uni-review -f
```

## Nginx 反向代理

### 基础配置（HTTP）

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5210;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 静态文件（如果以后从CDN改为本地）
    location /static/ {
        alias /root/uni-review/static/;
        expires 7d;
    }
}
```

### SSL 配置（HTTPS）

使用 Certbot 自动配置：

```bash
# 安装 Certbot
apt install -y certbot python3-certbot-nginx

# 获取证书（需先将域名解析到服务器IP）
certbot --nginx -d your-domain.com

# 自动续期已由systemd timer处理，验证：
systemctl list-timers | grep certbot
```

手动配置 SSL：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # SSL 优化
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;

    location / {
        proxy_pass http://127.0.0.1:5210;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

注意：HTTPS 是浏览器 GPS 定位（`navigator.geolocation`）的前提。没有SSL时只能使用IP定位。

## 更新部署流程

### 快速更新（仅代码变更）

```bash
# 本地打包
cd ~/projects/uni-review
tar czf /tmp/uni-review.tar.gz --exclude='__pycache__' --exclude='.git' --exclude='data' .

# 上传
scp /tmp/uni-review.tar.gz root@YOUR_SERVER_IP:/root/uni-review/

# 服务器解压+重启
ssh root@YOUR_SERVER_IP "cd /root/uni-review && tar xzf uni-review.tar.gz && rm -f uni-review.tar.gz && pkill -f 'gunicorn.*app:app'; sleep 1; gunicorn -w 2 -b 0.0.0.0:5210 --daemon app:app"
```

### 全量更新（含数据库重建）

```bash
# 本地打包（包含数据库）
cd ~/projects/uni-review
tar czf /tmp/uni-review.tar.gz --exclude='__pycache__' --exclude='.git' .

# 上传
scp /tmp/uni-review.tar.gz root@YOUR_SERVER_IP:/root/uni-review/

# 服务器操作
ssh root@YOUR_SERVER_IP
cd /root/uni-review
tar xzf uni-review.tar.gz
rm -f uni-review.tar.gz

# 重建数据库（会清除所有数据！）
rm -f data/uni_review.db
python3 seed.py
python3 generate_reviews.py

# 重启服务
pkill -f "gunicorn.*app:app"; sleep 1; gunicorn -w 2 -b 0.0.0.0:5210 --daemon app:app
```

### 使用 systemd 的重启方式

```bash
# 如果配置了systemd服务
ssh root@YOUR_SERVER_IP "systemctl restart uni-review"
```

## 常见问题排查

### Gunicorn 启动失败

```bash
# 1. 检查端口是否被占用
ss -tlnp | grep 5210
# 如果被占用，先杀掉旧进程
fuser -k 5210/tcp

# 2. 前台启动看报错信息
cd /root/uni-review
gunicorn -w 2 -b 0.0.0.0:5210 app:app
# 注意：去掉 --daemon 前台运行，观察错误输出

# 3. 检查Python依赖
pip3 list | grep -i flask
pip3 list | grep -i gunicorn

# 4. 检查工作目录是否正确
# gunicorn 必须在项目根目录启动，否则找不到 config.json 和 templates/
```

### 数据库锁定 (database is locked)

SQLite 在并发写入时可能出现此错误。

```bash
# 1. 检查是否有僵死进程
ps aux | grep gunicorn
# 如果有多个gunicorn实例，全部杀掉重启
pkill -9 -f gunicorn

# 2. 检查WAL文件
ls -la /root/uni-review/data/
# 正常应有 uni_review.db, uni_review.db-wal, uni_review.db-shm

# 3. 强制检查点（将WAL写回主库）
cd /root/uni-review
python3 -c "
import sqlite3
conn = sqlite3.connect('data/uni_review.db')
conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
conn.close()
print('OK')
"

# 4. 减少 worker 数量（SQLite不适合高并发写）
# 改为 -w 1 或 -w 2
```

### 页面502 Bad Gateway

```bash
# Nginx反代时后端服务未运行
# 1. 检查gunicorn是否在运行
ps aux | grep gunicorn

# 2. 检查端口是否监听
ss -tlnp | grep 5210

# 3. 直接访问后端确认
curl http://127.0.0.1:5210/
```

### IP定位不工作

```bash
# 1. 检查服务器是否能访问外部API
curl "http://ip-api.com/json/?lang=zh-CN&fields=status,lat,lon"

# 2. 检查Nginx是否正确传递X-Forwarded-For
# 在Nginx配置中确认有：
# proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

# 3. ip-api.com 限流 45次/分钟，超出会返回失败
```

### 模板找不到 (TemplateNotFound)

```bash
# 确认templates目录存在且有文件
ls /root/uni-review/templates/

# 确认gunicorn在正确目录启动
# WorkingDirectory 必须是 /root/uni-review
```

### config.json 修改后不生效

Gunicorn 的 worker 进程在启动时加载 config.json，修改后需重启：

```bash
pkill -f "gunicorn.*app:app"; sleep 1; cd /root/uni-review && gunicorn -w 2 -b 0.0.0.0:5210 --daemon app:app
```
