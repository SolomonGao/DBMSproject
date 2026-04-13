#!/usr/bin/env python3
"""
androwbackfilleventfingerprint
usemultithreadparallel processingmultidayETL

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
    """checksomedayfingerprintstatusstate"""
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
    """handleprocessformdayETL"""
    try:
        # firstcheckstatusstate
        date_str, fp_count, evt_count = check_date_status(date)
        
        if fp_count >= evt_count:
            return (date, True, f"alreadycompletewhole ({fp_count}/{evt_count})")
        
        print(f"  [{date}] openstartETL，whenbefore {fp_count}/{evt_count}...")
        
        # runETL（increaseaddsuperwhento10minute，Because one day may have2-5万event）
        result = subprocess.run(
            ["docker", "exec", "-w", "/app", "gdelt_app", 
             "python", "db_scripts/etl_pipeline.py", date],
            capture_output=True, text=True, timeout=600  # 10minutesuperwhen
        )
        
        if result.returncode == 0:
            # 再timecheck
            _, new_fp, evt = check_date_status(date)
            added = new_fp - fp_count
            if new_fp >= evt:
                return (date, True, f"completefinish (+{added}, {new_fp}/{evt})")
            else:
                return (date, True, f"part (+{added}, {new_fp}/{evt})")
        else:
            error_msg = result.stderr[:200] if result.stderr else "unknownerror"
            return (date, False, f"failed: {error_msg}")
            
    except subprocess.TimeoutExpired:
        return (date, False, "superwhen(10minute)")
    except Exception as e:
        return (date, False, f"asyncconstant: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description='androwbackfilleventfingerprint')
    parser.add_argument('--start', default='2024-01-01', help='openstartdate (YYYY-MM-DD)')
    parser.add_argument('--end', default='2024-12-31', help='result束date (YYYY-MM-DD)')
    parser.add_argument('--workers', type=int, default=8, help='androwworkthreadnumber (default: 8)')
    parser.add_argument('--dry-run', action='store_true', help='onlycheckstatusstate，notexecrowETL')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔧 androwbackfilleventfingerprint")
    print("=" * 60)
    print(f"daterange: {args.start} ~ {args.end}")
    print(f"androwschedule: {args.workers} thread")
    print()
    
    # generatedatelist
    dates = get_dates_to_process(args.start, args.end)
    print(f"总total {len(dates)} dayneedhandleprocess")
    print()
    
    # firstcheckalldatestatusstate
    print("📊 checkwhenbeforestatusstate...")
    status_list = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(check_date_status, date): date for date in dates}
        for future in as_completed(futures):
            date, fp, evt = future.result()
            status_list.append((date, fp, evt))
    
    # statistics
    # completewhole: fingerprintnumber >= eventnumber（package括eventnumberfor0case）
    complete = sum(1 for _, fp, evt in status_list if fp >= evt and fp >= 0 and evt >= 0)
    # part: hasfingerprintbutnotcompletewhole
    partial = sum(1 for _, fp, evt in status_list if 0 < fp < evt)
    # vacancy: haseventbutnofingerprint
    empty = sum(1 for _, fp, evt in status_list if fp == 0 and evt > 0)
    # error: queryinquiryfailed
    error = sum(1 for _, fp, evt in status_list if fp < 0 or evt < 0)
    
    print(f"statusstatestatistics:")
    print(f"  ✅ completewhole: {complete} day")
    print(f"  ⚠️  part: {partial} day")
    print(f"  ❌ vacancy: {empty} day")
    if error > 0:
        print(f"  💥 error: {error} day")
    print()
    
    if args.dry_run:
        print("📝 干runmodelpattern，notexecrowETL")
        return
    
    # 筛selectneedhandleprocessdate
    need_process = [date for date, fp, evt in status_list if fp < evt]
    
    if not need_process:
        print("✅ alldatealreadycompletewhole，no需handleprocess")
        return
    
    print(f"🚀 openstarthandleprocess {len(need_process)} day...")
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
    print("✅ handleprocesscompletefinish")
    print("=" * 60)
    
    # mostendstatistics
    final_result = subprocess.run(
        ["docker", "exec", "gdelt_mysql", "mysql", "-u", "root", "-prootpassword",
         "-e", "SELECT 'events_table', COUNT(*) FROM events_table WHERE SQLDATE BETWEEN '2024-01-01' AND '2024-12-31' UNION ALL SELECT 'fingerprints', COUNT(*) FROM event_fingerprints"],
        capture_output=True, text=True
    )
    print("mostendstatistics:")
    print(final_result.stdout)


if __name__ == "__main__":
    main()
