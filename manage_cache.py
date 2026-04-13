#!/usr/bin/env python3
"""
cache管理 CLI 工具

Usage:
    python manage_cache.py stats          # 查看统计
    python manage_cache.py clear          # 清空所hascache
    python manage_cache.py cleanup        # cleanupexpired条目
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
    """format化统计info"""
    lines = [
        "📊 querycache统计",
        "=" * 40,
        f"  cache条目: {stats['size']:,} / {stats['maxsize']:,}",
        f"  hit次数: {stats['hits']:,}",
        f"  未hit:   {stats['misses']:,}",
        f"  hit率:   {stats['hit_rate']}",
        f"  eviction次数: {stats['evictions']:,}",
        "=" * 40,
    ]
    
    # hit率评估
    hit_rate_str = stats['hit_rate'].rstrip('%')
    try:
        hit_rate = float(hit_rate_str)
        if hit_rate >= 80:
            lines.append("✅ hit率优秀 (≥80%)")
        elif hit_rate >= 50:
            lines.append("⚠️ hit率一般 (50-80%)")
        else:
            lines.append("❌ hit率较低 (<50%)，建议检查cache配置")
    except:
        pass
    
    return "\n".join(lines)


async def cmd_stats():
    """显示统计info"""
    stats = query_cache.get_stats()
    print(format_stats(stats))


async def cmd_clear():
    """清空所hascache"""
    print("⚠️  OK要清空所hascache吗？这会导致下次query变慢。")
    confirm = input("输入 'yes' Confirm: ")
    
    if confirm.lower() == 'yes':
        count = await query_cache.clear()
        print(f"✅ 已清空 {count} 个cache条目")
    else:
        print("已Cancel")


async def cmd_cleanup():
    """cleanupexpired条目"""
    count = await query_cache.cleanup_expired()
    if count > 0:
        print(f"🧹 cleanup {count} 个expired条目")
    else:
        print("🤷 没hasexpired条目需要cleanup")


async def cmd_clear_pattern(pattern: str):
    """按模式清除"""
    count = await query_cache.invalidate_pattern(pattern)
    print(f"✅ 已清除 {count} 个包含 '{pattern}' 条目")


async def cmd_monitor(interval: int = 5):
    """实时监控模式"""
    print(f"🔍 开始监控cache（每 {interval} 秒Refresh，按 Ctrl+C 停止）...")
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
            
            # 打印状态row
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(
                f"\r[{timestamp}] "
                f"条目: {stats['size']:>3}/{stats['maxsize']:<3} | "
                f"hit: {stats['hits']:>6} | "
                f"未hit: {stats['misses']:>6} | "
                f"hit率: {stats['hit_rate']:>6} | "
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
        description='cache管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    python manage_cache.py stats
    python manage_cache.py clear
    python manage_cache.py monitor --interval 10
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # stats
    subparsers.add_parser('stats', help='查看cache统计')
    
    # clear
    subparsers.add_parser('clear', help='清空所hascache')
    
    # cleanup
    subparsers.add_parser('cleanup', help='cleanupexpired条目')
    
    # clear-pattern
    pattern_parser = subparsers.add_parser('clear-pattern', help='按模式清除cache')
    pattern_parser.add_argument('pattern', help='匹配模式（如 2024-01-01）')
    
    # monitor
    monitor_parser = subparsers.add_parser('monitor', help='实时监控模式')
    monitor_parser.add_argument('--interval', '-i', type=int, default=5, help='Refresh间隔（秒）')
    
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
