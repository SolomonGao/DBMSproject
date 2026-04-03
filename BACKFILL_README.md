# 指纹补全方案

## 问题
ETL脚本有`LIMIT 1000`限制，每天只处理了1000条事件（实际有2-5万条）。

当前状态:
- 总事件数: 17,480,236
- 已生成指纹: 392,371 (2.2%)
- 缺失指纹: ~17,087,865

## 解决方案

### 方案1: 并行补全（推荐，最快）

使用8个worker并行处理：

```bash
# 全量补全（约需 3-4 小时）
python backfill_fingerprints_parallel.py --workers 8

# 或指定日期范围
python backfill_fingerprints_parallel.py --start 2024-01-01 --end 2024-06-30 --workers 8

# 干运行（只检查状态，不执行）
python backfill_fingerprints_parallel.py --workers 8 --dry-run
```

**优点**:
- 8个worker同时处理不同日期
- 速度快 6-8 倍
- 自动跳过已完成的日期

**缺点**:
- 数据库并发压力大
- 可能需要多次运行（每次处理5000条，每天需要4-10次循环）

### 方案2: 顺序补全（稳定，较慢）

```bash
# 使用修复后的脚本逐天处理
./backfill_fingerprints.sh
```

**优点**:
- 数据库压力小
- 稳定可靠

**缺点**:
- 速度慢（单线程）
- 预计需要 12-18 小时

### 方案3: 分段并行（平衡）

```bash
# 分4个批次，每批次3个月，每批次用4个worker

# 第一批
python backfill_fingerprints_parallel.py --start 2024-01-01 --end 2024-03-31 --workers 4 &

# 第二批
python backfill_fingerprints_parallel.py --start 2024-04-01 --end 2024-06-30 --workers 4 &

# 第三批
python backfill_fingerprints_parallel.py --start 2024-07-01 --end 2024-09-30 --workers 4 &

# 第四批
python backfill_fingerprints_parallel.py --start 2024-10-01 --end 2024-12-31 --workers 4 &

wait
echo "全部完成"
```

## 建议

**如果你的服务器性能好**（16核+，SSD）：
```bash
# 方案1: 8 worker全量
python backfill_fingerprints_parallel.py --workers 8
```

**如果你的服务器性能一般**（4-8核）：
```bash
# 方案3: 分段并行
# 先跑第一批，看数据库压力，再决定后续批次
python backfill_fingerprints_parallel.py --start 2024-01-01 --end 2024-03-31 --workers 4
```

**如果你要最稳妥**:
```bash
# 方案2: 顺序处理（让它在后台慢慢跑）
nohup ./backfill_fingerprints.sh > backfill.log 2>&1 &
tail -f backfill.log
```

## 检查进度

```bash
# 查看指纹生成进度
docker exec gdelt_mysql mysql -u root -prootpassword gdelt -e "
SELECT 
    'Total Events' as metric,
    COUNT(*) as count
FROM events_table 
WHERE SQLDATE BETWEEN '2024-01-01' AND '2024-12-31'
UNION ALL
SELECT 
    'Total Fingerprints',
    COUNT(*)
FROM event_fingerprints;
"

# 计算完成百分比
# 结果: fingerprints / events * 100%
```

## 注意事项

1. **ETL脚本已修复**: 移除了`LIMIT 1000`，改为批量处理（每批5000条）
2. **断点续传**: 并行脚本会自动跳过已完成的日期
3. **多次运行**: 如果一次没处理完，可以再次运行脚本
4. **监控数据库**: 如果MySQL负载过高，减少worker数量

## 预计时间

| 方案 | Worker数 | 预计时间 |
|------|----------|----------|
| 顺序处理 | 1 | 12-18 小时 |
| 并行处理 | 4 | 3-5 小时 |
| 并行处理 | 8 | 2-3 小时 |

## 完成后验证

```bash
# 验证所有日期都有完整指纹
docker exec gdelt_mysql mysql -u root -prootpassword gdelt -e "
SELECT 
    COUNT(DISTINCT SQLDATE) as days_with_events
FROM events_table 
WHERE SQLDATE BETWEEN '2024-01-01' AND '2024-12-31'
UNION ALL
SELECT 
    COUNT(DISTINCT SUBSTRING(fingerprint, 4, 8))
FROM event_fingerprints;
"

# 两个数字应该都是 366
```
