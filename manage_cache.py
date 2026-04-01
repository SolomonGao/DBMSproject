#!/usr/bin/env python3
"""
缓存管理 CLI 工具

Usage:
    python manage_cache.py stats          # 查看统计
    python manage_cache.py clear          # 清空所有缓存
    python manage_cache.py cleanup        # 清理过期条目
    python manage_cache.py clear-pattern <pattern>  # 按模式清除
    python manage_cache.py monitor        # 实时监控模式
"""

import sys
import asyncio
import argparse
from datetime import datetime

sys.path.insert(0, 'mcp_server')

from app.cache import query_cache


def format_stats(stats: dict) -> str:
    """格式化统计信息"""
    lines = [
        "📊 查询缓存统计",
        "=" * 40,
        f"  缓存条目: {stats['size']:,} / {stats['maxsize']:,}",
        f"  命中次数: {stats['hits']:,}",
        f"  未命中:   {stats['misses']:,}",
        f"  命中率:   {stats['hit_rate']}",
        f"  淘汰次数: {stats['evictions']:,}",
        "=" * 40,
    ]
    
    # 命中率评估
    hit_rate_str = stats['hit_rate'].rstrip('%')
    try:
        hit_rate = float(hit_rate_str)
        if hit_rate >= 80:
            lines.append("✅ 命中率优秀 (≥80%)")
        elif hit_rate >= 50:
            lines.append("⚠️ 命中率一般 (50-80%)")
        else:
            lines.append("❌ 命中率较低 (<50%)，建议检查缓存配置")
    except:
        pass
    
    return "\n".join(lines)


async def cmd_stats():
    """显示统计信息"""
    stats = query_cache.get_stats()
    print(format_stats(stats))


async def cmd_clear():
    """清空所有缓存"""
    print("⚠️  确定要清空所有缓存吗？这会导致下次查询变慢。")
    confirm = input("输入 'yes' 确认: ")
    
    if confirm.lower() == 'yes':
        count = await query_cache.clear()
        print(f"✅ 已清空 {count} 个缓存条目")
    else:
        print("已取消")


async def cmd_cleanup():
    """清理过期条目"""
    count = await query_cache.cleanup_expired()
    if count > 0:
        print(f"🧹 清理了 {count} 个过期条目")
    else:
        print("🤷 没有过期条目需要清理")


async def cmd_clear_pattern(pattern: str):
    """按模式清除"""
    count = await query_cache.invalidate_pattern(pattern)
    print(f"✅ 已清除 {count} 个包含 '{pattern}' 的条目")


async def cmd_monitor(interval: int = 5):
    """实时监控模式"""
    print(f"🔍 开始监控缓存（每 {interval} 秒刷新，按 Ctrl+C 停止）...")
    print("-" * 60)
    
    last_hits = 0
    last_misses = 0
    
    try:
        while True:
            stats = query_cache.get_stats()
            
            # 计算实时 QPS
            total_reqs = stats['hits'] + stats['misses']
            last_total = last_hits + last_misses
            qps = (total_reqs - last_total) / interval
            
            # 打印状态行
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(
                f"\r[{timestamp}] "
                f"条目: {stats['size']:>3}/{stats['maxsize']:<3} | "
                f"命中: {stats['hits']:>6} | "
                f"未命中: {stats['misses']:>6} | "
                f"命中率: {stats['hit_rate']:>6} | "
                f"QPS: {qps:>5.1f}",
                end='', flush=True
            )
            
            last_hits = stats['hits']
            last_misses = stats['misses']
            
            await asyncio.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\n👋 监控已停止")


async def main():
    parser = argparse.ArgumentParser(
        description='缓存管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python manage_cache.py stats
    python manage_cache.py clear
    python manage_cache.py monitor --interval 10
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # stats
    subparsers.add_parser('stats', help='查看缓存统计')
    
    # clear
    subparsers.add_parser('clear', help='清空所有缓存')
    
    # cleanup
    subparsers.add_parser('cleanup', help='清理过期条目')
    
    # clear-pattern
    pattern_parser = subparsers.add_parser('clear-pattern', help='按模式清除缓存')
    pattern_parser.add_argument('pattern', help='匹配模式（如 2024-01-01）')
    
    # monitor
    monitor_parser = subparsers.add_parser('monitor', help='实时监控模式')
    monitor_parser.add_argument('--interval', '-i', type=int, default=5, help='刷新间隔（秒）')
    
    args = parser.parse_args()
    
    if args.command == 'stats':
        await cmd_stats()
    elif args.command == 'clear':
        await cmd_clear()
    elif args.command == 'cleanup':
        await cmd_cleanup()
    elif args.command == 'clear-pattern':
        await cmd_clear_pattern(args.pattern)
    elif args.command == 'monitor':
        await cmd_monitor(args.interval)
    else:
        parser.print_help()


if __name__ == '__main__':
    asyncio.run(main())
