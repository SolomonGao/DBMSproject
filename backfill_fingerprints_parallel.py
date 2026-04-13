#!/usr/bin/env python3
"""
androw补全eventfingerprint
usemultithreadparallel processingmulti天ETL

usage:
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
    """generate date list to process"""
    dates = []
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    current = start
    while current <= end:
        dates.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    
    return dates


def check_date_status(date: str) -> Tuple[str, int, int]:
    """check某天fingerprint状state"""
    try:
        # fetcheventnumber
        evt_result = subprocess.run(
            ["docker", "exec", "gdelt_mysql", "mysql", "-u", "root", "-prootpassword", 
             "-N", "-e", f"SELECT COUNT(*) FROM gdelt.events_table WHERE SQLDATE = '{date}'"],
            capture_output=True, text=True, timeout=10
        )
        evt_count = int(evt_result.stdout.strip()) if evt_result.returncode == 0 else 0
        
        # fetchfingerprintnumber（fingerprintgridpattern: US-20240101-WDC-PROTEST-001）
        date_no_dash = date.replace('-', '')
        fp_result = subprocess.run(
            ["docker", "exec", "gdelt_mysql", "mysql", "-u", "root", "-prootpassword",
             "-N", "-e", f"SELECT COUNT(*) FROM gdelt.event_fingerprints WHERE fingerprint LIKE '%-{date_no_dash}-%'"],
            capture_output=True, text=True, timeout=10
        )
        fp_count = int(fp_result.stdout.strip()) if fp_result.returncode == 0 else 0
        
        # callback试transportoutput
        if fp_count > 0 or evt_count > 0:
            print(f"  [check] {date}: {fp_count} fingerprint / {evt_count} event")
        
        return (date, fp_count, evt_count)
    except Exception as e:
        print(f"  [error] check {date} failed: {e}")
        return (date, -1, -1)


def process_date(date: str) -> Tuple[str, bool, str]:
    """处processform天ETL"""
    try:
        # 先check状state
        date_str, fp_count, evt_count = check_date_status(date)
        
        if fp_count >= evt_count:
            return (date, True, f"alreadycomplete整 ({fp_count}/{evt_count})")
        
        print(f"  [{date}] 开startETL，whenbefore {fp_count}/{evt_count}...")
        
        # runETL（增add超when到10分钟，Because one day may have2-5万event）
        result = subprocess.run(
            ["docker", "exec", "-w", "/app", "gdelt_app", 
             "python", "db_scripts/etl_pipeline.py", date],
            capture_output=True, text=True, timeout=600  # 10分钟超when
        )
        
        if result.returncode == 0:
            # 再次check
            _, new_fp, evt = check_date_status(date)
            added = new_fp - fp_count
            if new_fp >= evt:
                return (date, True, f"completefinish (+{added}, {new_fp}/{evt})")
            else:
                return (date, True, f"部分 (+{added}, {new_fp}/{evt})")
        else:
            error_msg = result.stderr[:200] if result.stderr else "unknownerror"
            return (date, False, f"failed: {error_msg}")
            
    except subprocess.TimeoutExpired:
        return (date, False, "超when(10分钟)")
    except Exception as e:
        return (date, False, f"asyncconstant: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description='androw补全eventfingerprint')
    parser.add_argument('--start', default='2024-01-01', help='开startdate (YYYY-MM-DD)')
    parser.add_argument('--end', default='2024-12-31', help='result束date (YYYY-MM-DD)')
    parser.add_argument('--workers', type=int, default=8, help='androwworkthreadnumber (默认: 8)')
    parser.add_argument('--dry-run', action='store_true', help='只check状state，不执rowETL')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔧 androw补全eventfingerprint")
    print("=" * 60)
    print(f"daterange: {args.start} ~ {args.end}")
    print(f"androwschedule: {args.workers} thread")
    print()
    
    # generatedatelist
    dates = get_dates_to_process(args.start, args.end)
    print(f"总共 {len(dates)} 天need处process")
    print()
    
    # 先checkalldate状state
    print("📊 checkwhenbefore状state...")
    status_list = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(check_date_status, date): date for date in dates}
        for future in as_completed(futures):
            date, fp, evt = future.result()
            status_list.append((date, fp, evt))
    
    # statistics
    # complete整: fingerprintnumber >= eventnumber（package括eventnumber为0case）
    complete = sum(1 for _, fp, evt in status_list if fp >= evt and fp >= 0 and evt >= 0)
    # 部分: 有fingerprintbut未complete整
    partial = sum(1 for _, fp, evt in status_list if 0 < fp < evt)
    # 空缺: 有eventbut无fingerprint
    empty = sum(1 for _, fp, evt in status_list if fp == 0 and evt > 0)
    # error: queryinquiryfailed
    error = sum(1 for _, fp, evt in status_list if fp < 0 or evt < 0)
    
    print(f"状statestatistics:")
    print(f"  ✅ complete整: {complete} 天")
    print(f"  ⚠️  部分: {partial} 天")
    print(f"  ❌ 空缺: {empty} 天")
    if error > 0:
        print(f"  💥 error: {error} 天")
    print()
    
    if args.dry_run:
        print("📝 干runmodelpattern，不执rowETL")
        return
    
    # 筛selectneed处processdate
    need_process = [date for date, fp, evt in status_list if fp < evt]
    
    if not need_process:
        print("✅ alldatealreadycomplete整，无需处process")
        return
    
    print(f"🚀 开start处process {len(need_process)} 天...")
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
    print("✅ 处processcompletefinish")
    print("=" * 60)
    
    # 最endstatistics
    final_result = subprocess.run(
        ["docker", "exec", "gdelt_mysql", "mysql", "-u", "root", "-prootpassword",
         "-e", "SELECT 'events_table', COUNT(*) FROM events_table WHERE SQLDATE BETWEEN '2024-01-01' AND '2024-12-31' UNION ALL SELECT 'fingerprints', COUNT(*) FROM event_fingerprints"],
        capture_output=True, text=True
    )
    print("最endstatistics:")
    print(final_result.stdout)


if __name__ == "__main__":
    main()
