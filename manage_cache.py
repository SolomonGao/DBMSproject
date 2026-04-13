#!/usr/bin/env python3
"""
cachemanageprocess CLI tool

Usage:
    python manage_cache.py stats          # query看statistics
    python manage_cache.py clear          # 清空所hascache
    python manage_cache.py cleanup        # cleanupexpired条project
    python manage_cache.py clear-pattern <pattern>  # 按modelpattern清remove
    python manage_cache.py monitor        # real-timemonitormodelpattern
"""

import sys
import asyncio
import argparse
from datetime import datetime

sys.path.insert(0, 'mcp_server')

from app.cache import query_cache


def format_stats(stats: dict) -> str:
    """formatizationstatisticsinfo"""
    lines = [
        "📊 querycachestatistics",
        "=" * 40,
        f"  cache条project: {stats['size']:,} / {stats['maxsize']:,}",
        f"  hit次number: {stats['hits']:,}",
        f"  未hit:   {stats['misses']:,}",
        f"  hit率:   {stats['hit_rate']}",
        f"  eviction次number: {stats['evictions']:,}",
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
            lines.append("❌ hit率较低 (<50%)，build议checkcacheconfig")
    except:
        pass
    
    return "\n".join(lines)


async def cmd_stats():
    """显示statisticsinfo"""
    stats = query_cache.get_stats()
    print(format_stats(stats))


async def cmd_clear():
    """清空所hascache"""
    print("⚠️  OKwant清空所hascache吗？这willexport致under次queryvariable慢。")
    confirm = input("input 'yes' Confirm: ")
    
    if confirm.lower() == 'yes':
        count = await query_cache.clear()
        print(f"✅ already清空 {count} 个cache条project")
    else:
        print("alreadyCancel")


async def cmd_cleanup():
    """cleanupexpired条project"""
    count = await query_cache.cleanup_expired()
    if count > 0:
        print(f"🧹 cleanup {count} 个expired条project")
    else:
        print("🤷 没hasexpired条projectneedcleanup")


async def cmd_clear_pattern(pattern: str):
    """按modelpattern清remove"""
    count = await query_cache.invalidate_pattern(pattern)
    print(f"✅ already清remove {count} 个包含 '{pattern}' 条project")


async def cmd_monitor(interval: int = 5):
    """real-timemonitormodelpattern"""
    print(f"🔍 开startmonitorcache（每 {interval} 秒Refresh，按 Ctrl+C 停stop）...")
    print("-" * 60)
    
    last_hits = 0
    last_misses = 0
    
    try:
        while True:
            stats = query_cache.get_stats()
            
            # 计算real-time QPS
            total_reqs = stats['hits'] + stats['misses']
            last_total = last_hits + last_misses
            qps = (total_reqs - last_total) / interval
            
            # print状staterow
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(
                f"\r[{timestamp}] "
                f"条project: {stats['size']:>3}/{stats['maxsize']:<3} | "
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
        print("\n\n👋 monitoralready停stop")


async def main():
    parser = argparse.ArgumentParser(
        description='cachemanageprocesstool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    python manage_cache.py stats
    python manage_cache.py clear
    python manage_cache.py monitor --interval 10
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='availablecommand')
    
    # stats
    subparsers.add_parser('stats', help='query看cachestatistics')
    
    # clear
    subparsers.add_parser('clear', help='清空所hascache')
    
    # cleanup
    subparsers.add_parser('cleanup', help='cleanupexpired条project')
    
    # clear-pattern
    pattern_parser = subparsers.add_parser('clear-pattern', help='按modelpattern清removecache')
    pattern_parser.add_argument('pattern', help='匹allocatemodelpattern（如 2024-01-01）')
    
    # monitor
    monitor_parser = subparsers.add_parser('monitor', help='real-timemonitormodelpattern')
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
