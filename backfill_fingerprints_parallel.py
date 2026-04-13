#!/usr/bin/env python3
"""
并行补全事件fingerprint
使用多线程parallel processing多天的ETL

用法:
    python backfill_fingerprints_parallel.py --workers 8
    python backfill_fingerprints_parallel.py --start 2024-01-01 --end 2024-01-31 --workers 4
"""

import asyncio
import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import List, Tuple
import json


def get_dates_to_process(start_date: str, end_date: str) -> List[str]:
    """生成需要处理的日期列表"""
    dates = []
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    current = start
    while current <= end:
        dates.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    
    return dates


def check_date_status(date: str) -> Tuple[str, int, int]:
    """检查某天的fingerprint状态"""
    try:
        # fetch事件数
        evt_result = subprocess.run(
            ["docker", "exec", "gdelt_mysql", "mysql", "-u", "root", "-prootpassword", 
             "-N", "-e", f"SELECT COUNT(*) FROM gdelt.events_table WHERE SQLDATE = '{date}'"],
            capture_output=True, text=True, timeout=10
        )
        evt_count = int(evt_result.stdout.strip()) if evt_result.returncode == 0 else 0
        
        # fetchfingerprint数（fingerprint格式: US-20240101-WDC-PROTEST-001）
        date_no_dash = date.replace('-', '')
        fp_result = subprocess.run(
            ["docker", "exec", "gdelt_mysql", "mysql", "-u", "root", "-prootpassword",
             "-N", "-e", f"SELECT COUNT(*) FROM gdelt.event_fingerprints WHERE fingerprint LIKE '%-{date_no_dash}-%'"],
            capture_output=True, text=True, timeout=10
        )
        fp_count = int(fp_result.stdout.strip()) if fp_result.returncode == 0 else 0
        
        # 调试输出
        if fp_count > 0 or evt_count > 0:
            print(f"  [检查] {date}: {fp_count} fingerprint / {evt_count} 事件")
        
        return (date, fp_count, evt_count)
    except Exception as e:
        print(f"  [错误] 检查 {date} 失败: {e}")
        return (date, -1, -1)


def process_date(date: str) -> Tuple[str, bool, str]:
    """处理单天的ETL"""
    try:
        # 先检查状态
        date_str, fp_count, evt_count = check_date_status(date)
        
        if fp_count >= evt_count:
            return (date, True, f"已完整 ({fp_count}/{evt_count})")
        
        print(f"  [{date}] 开始ETL，当前 {fp_count}/{evt_count}...")
        
        # 运行ETL（增加超时到10分钟，因为一天可能有2-5万事件）
        result = subprocess.run(
            ["docker", "exec", "-w", "/app", "gdelt_app", 
             "python", "db_scripts/etl_pipeline.py", date],
            capture_output=True, text=True, timeout=600  # 10分钟超时
        )
        
        if result.returncode == 0:
            # 再次检查
            _, new_fp, evt = check_date_status(date)
            added = new_fp - fp_count
            if new_fp >= evt:
                return (date, True, f"完成 (+{added}, {new_fp}/{evt})")
            else:
                return (date, True, f"部分 (+{added}, {new_fp}/{evt})")
        else:
            error_msg = result.stderr[:200] if result.stderr else "未知错误"
            return (date, False, f"失败: {error_msg}")
            
    except subprocess.TimeoutExpired:
        return (date, False, "超时(10分钟)")
    except Exception as e:
        return (date, False, f"异常: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description='并行补全事件fingerprint')
    parser.add_argument('--start', default='2024-01-01', help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', default='2024-12-31', help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--workers', type=int, default=8, help='并行工作线程数 (默认: 8)')
    parser.add_argument('--dry-run', action='store_true', help='只检查状态，不执行ETL')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔧 并行补全事件fingerprint")
    print("=" * 60)
    print(f"日期范围: {args.start} ~ {args.end}")
    print(f"并行度: {args.workers} 线程")
    print()
    
    # 生成日期列表
    dates = get_dates_to_process(args.start, args.end)
    print(f"总共 {len(dates)} 天需要处理")
    print()
    
    # 先检查所有日期状态
    print("📊 检查当前状态...")
    status_list = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(check_date_status, date): date for date in dates}
        for future in as_completed(futures):
            date, fp, evt = future.result()
            status_list.append((date, fp, evt))
    
    # 统计
    # 完整: fingerprint数 >= 事件数（package括事件数为0的情况）
    complete = sum(1 for _, fp, evt in status_list if fp >= evt and fp >= 0 and evt >= 0)
    # 部分: 有fingerprint但未完整
    partial = sum(1 for _, fp, evt in status_list if 0 < fp < evt)
    # 空缺: 有事件但无fingerprint
    empty = sum(1 for _, fp, evt in status_list if fp == 0 and evt > 0)
    # 错误: 查询失败
    error = sum(1 for _, fp, evt in status_list if fp < 0 or evt < 0)
    
    print(f"状态统计:")
    print(f"  ✅ 完整: {complete} 天")
    print(f"  ⚠️  部分: {partial} 天")
    print(f"  ❌ 空缺: {empty} 天")
    if error > 0:
        print(f"  💥 错误: {error} 天")
    print()
    
    if args.dry_run:
        print("📝 干运行模式，不执行ETL")
        return
    
    # 筛选需要处理的日期
    need_process = [date for date, fp, evt in status_list if fp < evt]
    
    if not need_process:
        print("✅ 所有日期已完整，无需处理")
        return
    
    print(f"🚀 开始处理 {len(need_process)} 天...")
    print()
    
    # parallel processing
    completed = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_date, date): date for date in need_process}
        
        for future in as_completed(futures):
            date, success, msg = future.result()
            completed += 1
            
            status = "✅" if success else "❌"
            print(f"[{completed}/{len(need_process)}] {status} {date}: {msg}")
    
    print()
    print("=" * 60)
    print("✅ 处理完成")
    print("=" * 60)
    
    # 最终统计
    final_result = subprocess.run(
        ["docker", "exec", "gdelt_mysql", "mysql", "-u", "root", "-prootpassword",
         "-e", "SELECT 'events_table', COUNT(*) FROM events_table WHERE SQLDATE BETWEEN '2024-01-01' AND '2024-12-31' UNION ALL SELECT 'fingerprints', COUNT(*) FROM event_fingerprints"],
        capture_output=True, text=True
    )
    print("最终统计:")
    print(final_result.stdout)


if __name__ == "__main__":
    main()
