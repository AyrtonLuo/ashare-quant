#!/bin/bash
# ==============================================================================
# deploy_server.sh - A-Share Quant Streamlit 云服务器一键自动化部署脚本 (Ubuntu/Debian)
# ==============================================================================

set -e

echo "🚀 开始部署 ashare-quant 量化选股终端系统..."

# 1. 软件源更新与系统依赖安装
echo "📦 正在更新 Apt 软件源并安装系统依赖包..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git curl build-essential libssl-dev nginx

# 2. 获取当前部署目录路径与用户
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="$(whoami)"

echo "📂 部署应用目录: ${APP_DIR}"
echo "👤 运行服务用户: ${CURRENT_USER}"

# 3. 创建 Python 虚拟环境
if [ ! -d "${APP_DIR}/venv" ]; then
    echo "🐍 正在创建 Python 3 虚拟环境 (venv)..."
    python3 -m venv "${APP_DIR}/venv"
fi

echo "⚡ 正在升级 pip 并安装依赖包..."
"${APP_DIR}/venv/bin/pip" install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
if [ -f "${APP_DIR}/requirements.txt" ]; then
    "${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
fi

# 4. 创建并配置 Systemd 后台守护服务
SERVICE_FILE="/etc/systemd/system/ashare-quant.service"

echo "⚙️ 正在生成 Systemd 后台守护进程服务文件 (${SERVICE_FILE})...."
sudo bash -c "cat <<EOF > ${SERVICE_FILE}
[Unit]
Description=A-Share Quant Streamlit AI Stock Selection Terminal
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/venv/bin/streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF"

echo "🔄 正在重载 Systemd 配置并启动 ashare-quant 服务..."
sudo systemctl daemon-reload
sudo systemctl enable ashare-quant.service
sudo systemctl restart ashare-quant.service

echo "✅ ashare-quant Systemd 守护服务已开启后台运行！"

# 5. 输出 Nginx 反向代理配置样例
echo "🌐 正在配置 Nginx 反向代理..."
NGINX_CONF="/etc/nginx/sites-available/ashare-quant.conf"
sudo bash -c "cat <<EOF > ${NGINX_CONF}
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }
}
EOF"

if [ -d "/etc/nginx/sites-enabled" ]; then
    sudo ln -sf "${NGINX_CONF}" /etc/nginx/sites-enabled/
    sudo nginx -t && sudo systemctl reload nginx || true
fi

echo "=============================================================================="
echo "🎉 部署完成！量化终端服务已在后台成功启动。"
echo "📍 Streamlit 服务端口: http://<服务器IP>:8501"
echo "🛠️ 检查服务状态命令: sudo systemctl status ashare-quant.service"
echo "📜 查看实时运行日志命令: sudo journalctl -u ashare-quant.service -f"
echo "=============================================================================="
