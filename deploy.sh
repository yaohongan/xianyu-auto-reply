#!/bin/bash

# 闲鱼自动回复项目安全部署脚本
# 使用方法: ./deploy.sh

set -e  # 遇到错误立即退出

echo "=== 开始安全部署流程 ==="

# 1. 创建备份
echo "1. 创建数据备份..."
backup_dir="backups/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p $backup_dir

if [ -d "data" ]; then
    cp -r data/ $backup_dir/
    echo "✓ 数据库备份完成"
fi

if [ -d "logs" ]; then
    cp -r logs/ $backup_dir/
    echo "✓ 日志备份完成"
fi

if [ -f "global_config.yml" ]; then
    cp global_config.yml $backup_dir/
    echo "✓ 配置文件备份完成"
fi

echo "备份完成，位置: $backup_dir"

# 2. 停止服务
echo "2. 停止当前服务..."
docker-compose down
echo "✓ 服务已停止"

# 3. 拉取最新代码
echo "3. 拉取最新代码..."
git pull origin main
echo "✓ 代码更新完成"

# 4. 重新构建和启动
echo "4. 重新构建并启动服务..."
docker-compose build --no-cache
docker-compose up -d
echo "✓ 服务启动完成"

# 5. 等待服务启动
echo "5. 等待服务启动..."
sleep 10

# 6. 健康检查
echo "6. 进行健康检查..."
if docker-compose ps | grep -q "Up"; then
    echo "✓ 容器运行正常"
else
    echo "✗ 容器启动异常，请检查日志"
    docker-compose logs --tail=20
    exit 1
fi

# 7. 检查数据完整性
echo "7. 检查数据完整性..."
if [ -f "data/xianyu_data.db" ]; then
    echo "✓ 数据库文件存在"
else
    echo "⚠ 警告: 数据库文件不存在"
fi

echo "=== 部署完成 ==="
echo "备份位置: $backup_dir"
echo "请访问你的网站检查功能是否正常"
echo "如有问题，可以使用以下命令查看日志:"
echo "docker-compose logs -f"