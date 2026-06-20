#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# AI Route Planner — 一键部署到云服务器
# 使用: bash deploy.sh
# ─────────────────────────────────────────────────────────
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ─── 1. Check prerequisites ─────────────────────────────
info "检查运行环境..."

command -v docker >/dev/null 2>&1 || error "请先安装 Docker: https://docs.docker.com/engine/install/ubuntu/"
command -v docker compose >/dev/null 2>&1 || error "请先安装 Docker Compose (plugin)"

# ─── 2. Check .env ──────────────────────────────────────
if [ ! -f .env ]; then
    if [ -f .env.production ]; then
        warn ".env 不存在，从 .env.production 复制..."
        cp .env.production .env
        warn ">>> 请编辑 .env 填入真实的 API Key，然后重新运行 bash deploy.sh"
        exit 0
    else
        error ".env.production 模板文件不存在"
    fi
fi

# Quick check for placeholder keys
if grep -q "sk-your-deepseek-api-key\|your-gaode-api-key" .env 2>/dev/null; then
    warn ".env 中仍有占位 API Key，请确认已填入真实值"
fi

# ─── 3. Add swap if needed (for 2GB servers) ────────────
SWAP_SIZE=$(free -m | awk '/^Swap:/ {print $2}')
if [ "$SWAP_SIZE" -lt 1024 ]; then
    warn "Swap 不足 (当前 ${SWAP_SIZE}MB)，创建 2GB swap 文件..."
    if [ ! -f /swapfile ]; then
        sudo fallocate -l 2G /swapfile
        sudo chmod 600 /swapfile
        sudo mkswap /swapfile
        sudo swapon /swapfile
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
        info "Swap 创建完成"
    fi
else
    info "Swap 已有 ${SWAP_SIZE}MB，跳过"
fi

# ─── 4. Build & start ───────────────────────────────────
info "构建镜像并启动服务 (可能需要 3-5 分钟)..."

docker compose -f docker-compose.prod.yml up -d --build

# ─── 5. Wait for health ─────────────────────────────────
info "等待健康检查..."
RETRY=0
MAX_RETRY=30
until curl -sf http://localhost:80/api/route/health >/dev/null 2>&1; do
    RETRY=$((RETRY + 1))
    if [ "$RETRY" -ge "$MAX_RETRY" ]; then
        warn "健康检查超时，查看日志: docker compose -f docker-compose.prod.yml logs --tail=50"
        exit 1
    fi
    sleep 2
done

# ─── 6. Done ────────────────────────────────────────────
PUBLIC_IP=$(curl -sf ifconfig.me 2>/dev/null || echo "你的公网IP")
echo ""
info "部署完成！"
echo ""
echo "  前端页面:  http://${PUBLIC_IP}"
echo "  健康检查:  http://${PUBLIC_IP}/api/route/health"
echo ""
echo "  查看日志:  docker compose -f docker-compose.prod.yml logs -f"
echo "  停止服务:  docker compose -f docker-compose.prod.yml down"
