#!/usr/bin/env python3
"""
cachemanageprocess CLI tool

Usage:
    python manage_cache.py stats          # queryseestatistics
    python manage_cache.py clear          # clearsohascache
    python manage_cache.py cleanup        # cleanupexpireditemproject
    python manage_cache.py clear-pattern <pattern>  # bymodelpatternclearremove
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
        f"  cacheitemproject: {stats['size']:,} / {stats['maxsize']:,}",
        f"  hittimenumber: {stats['hits']:,}",
        f"  nothit:   {stats['misses']:,}",
        f"  hitrate:   {stats['hit_rate']}",
        f"  evictiontimenumber: {stats['evictions']:,}",
        "=" * 40,
    ]
    
    # hitrate评估
    hit_rate_str = stats['hit_rate'].rstrip('%')
    try:
        hit_rate = float(hit_rate_str)
        if hit_rate >= 80:
            lines.append("✅ hitrateopt秀 (≥80%)")
        elif hit_rate >= 50:
            lines.append("⚠️ hitrateone般 (50-80%)")
        else:
            lines.append("❌ hitrate较low (<50%)，build议checkcacheconfig")
    except:
        pass
    
    return "\n".join(lines)


async def cmd_stats():
    """displaystatisticsinfo"""
    stats = query_cache.get_stats()
    print(format_stats(stats))


async def cmd_clear():
    """clearsohascache"""
    print("⚠️  OKwantclearsohascache吗？thiswillexport致undertimequeryvariableslow。")
    confirm = input("input 'yes' Confirm: ")
    
    if confirm.lower() == 'yes':
        count = await query_cache.clear()
        print(f"✅ alreadyclear {count} cacheitemproject")
    else:
        print("alreadyCancel")


async def cmd_cleanup():
    """cleanupexpireditemproject"""
    count = await query_cache.cleanup_expired()
    if count > 0:
        print(f"🧹 cleanup {count} expireditemproject")
    else:
        print("🤷 nohasexpireditemprojectneedcleanup")


async def cmd_clear_pattern(pattern: str):
    """bymodelpatternclearremove"""
    count = await query_cache.invalidate_pattern(pattern)
    print(f"✅ alreadyclearremove {count} package含 '{pattern}' itemproject")


async def cmd_monitor(interval: int = 5):
    """real-timemonitormodelpattern"""
    print(f"🔍 openstartmonitorcache（each {interval} 秒Refresh，by Ctrl+C 停stop）...")
    print("-" * 60)
    
    last_hits = 0
    last_misses = 0
    
    try:
        while True:
            stats = query_cache.get_stats()
            
            # calculatereal-time QPS
            total_reqs = stats['hits'] + stats['misses']
            last_total = last_hits + last_misses
            qps = (total_reqs - last_total) / interval
            
            # printstatusstaterow
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(
                f"\r[{timestamp}] "
                f"itemproject: {stats['size']:>3}/{stats['maxsize']:<3} | "
                f"hit: {stats['hits']:>6} | "
                f"nothit: {stats['misses']:>6} | "
                f"hitrate: {stats['hit_rate']:>6} | "
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
    subparsers.add_parser('stats', help='queryseecachestatistics')
    
    # clear
    subparsers.add_parser('clear', help='clearsohascache')
    
    # cleanup
    subparsers.add_parser('cleanup', help='cleanupexpireditemproject')
    
    # clear-pattern
    pattern_parser = subparsers.add_parser('clear-pattern', help='bymodelpatternclearremovecache')
    pattern_parser.add_argument('pattern', help='匹allocatemodelpattern（if 2024-01-01）')
    
    # monitor
    monitor_parser = subparsers.add_parser('monitor', help='real-timemonitormodelpattern')
    monitor_parser.add_argument('--interval', '-i', type=int, default=5, help='Refreshinterval隔（秒）')
    
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
