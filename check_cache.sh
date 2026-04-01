#!/bin/bash
# 检查缓存工作状态

echo "🔍 检查缓存状态..."
echo ""

# 进入容器检查 Python 缓存状态
docker exec gdelt_app python -c "
import sys
sys.path.insert(0, 'mcp_server')
from app.cache import query_cache
stats = query_cache.get_stats()
print('📊 当前缓存状态:')
for k, v in stats.items():
    print(f'  {k}: {v}')
"

echo ""
echo "💡 如果 hits 为 0，说明缓存未命中。可能原因："
echo "  1. SQL 查询字符串每次不同（有时间戳、随机数等）"
echo "  2. 查询结果为空（空结果不缓存）"
echo "  3. 缓存被清空过"
echo ""
echo "🔧 查看最近的日志:"
docker logs gdelt_app --tail 20 2>&1 | grep -i "cache\|缓存" || echo "暂无缓存相关日志"
