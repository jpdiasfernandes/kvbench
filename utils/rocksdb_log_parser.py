#!/usr/bin/env python3
import re
import sys
from tabulate import tabulate
from pint import UnitRegistry, Quantity
from datetime import datetime, timedelta
import argparse
import json

float_re = r'\d+(\.\d+)?'
operation_type = "read"
count_pair = fr'Count:\s+(?P<count>\d+)'
avg_pair = fr'Average:\s+(?P<avg>{float_re})'
stdev_pair = fr'StdDev:\s+(?P<stdev>{float_re})'
min_pair = fr'Min:\s+(?P<min>{float_re})'
median_pair = fr'Median:\s+(?P<median>{float_re})'
max_pair = fr'Max:\s+(?P<max>{float_re})'
p50_pair = fr'P50:\s+(?P<p50>{float_re})'
p75_pair = fr'P75:\s+(?P<p75>{float_re})'
p99_pair = fr'P99:\s+(?P<p99>{float_re})'
p99_9_pair = fr'P99\.9:\s+(?P<p99_9>{float_re})'
p99_99_pair = fr'P99\.99:\s+(?P<p99_99>{float_re})'

def get_stats(operation_type, text):
    stats_line1 = fr'Microseconds\s+per\s+{operation_type}:'
    stats_line2 = fr'{count_pair}\s+{avg_pair}\s+{stdev_pair}'
    stats_line3 = fr'{min_pair}\s+{median_pair}\s+{max_pair}'
    stats_line4 = fr'Percentiles:\s+{p50_pair}\s+{p75_pair}\s+{p99_pair}\s+{p99_9_pair}\s+{p99_99_pair}'
    read_stats = fr'{stats_line1}\s*\n\s*{stats_line2}\s*\n\s*{stats_line3}\s*\n\s*{stats_line4}'

    match = re.search(read_stats, text)
    if match:
        res = {}
        res["type"] = operation_type
        res["count"] = int(match.group('count'))
        res["latency"] = {}
        res["latency"]["avg"] = float(match.group('avg'))
        res["latency"]["stdev"] = float(match.group('stdev'))
        res["latency"]["min"] = float(match.group('min'))
        res["latency"]["median"] = float(match.group('median'))
        res["latency"]["max"] = float(match.group('max'))
        res["latency"]["p50"] = float(match.group('p50'))
        res["latency"]["p75"] = float(match.group('p75'))
        res["latency"]["p99"] = float(match.group('p99'))
        res["latency"]["p99.9"] = float(match.group('p99_9'))
        res["latency"]["p99.99"] = float(match.group('p99_99'))
        return res

def get_stat_row(stat):
    latency = stat["latency"]
    return [ stat["type"], stat["count"], latency["avg"], latency["stdev"], latency["min"], latency["median"], latency["max"],
             latency["p50"], latency["p75"], latency["p99"], latency["p99.9"], latency["p99.99"]]

def print_op_stats(text):
    stat_read = get_stats("read", text)
    stat_write = get_stats("write", text)

    table = [ ['type', 'count', 'avg', 'stdev', 'min', 'median', 'max', 'p50', 'p75', 'p75', 'p99', 'p99.9', 'p99.99'] ,
              get_stat_row(stat_read), get_stat_row(stat_write)]
    print(tabulate(table, headers='firstrow', tablefmt='fancy_grid'))

def match_any_stat(line, stats_type='any'):
    db_stat_expressions = {
        fr'Uptime\(secs\):\s+(?P<total_uptime_sec>{float_re})\s+total,\s+(?P<interval_uptime_sec>{float_re})\s+interval',
        r'Cumulative writes:\s*(?P<cuml_writes>.*?)\s*writes,\s*(?P<cuml_keys>.*?)\s*keys,\s*(?P<cuml_commit_groups>.*?)\s*commit groups,\s*(?P<cuml_writes_per_group>.*?)\s*writes per commit group,\s*ingest:\s*(?P<cuml_ingest>.*?),\s*(?P<cuml_ingest_rate>.*)',
        r'Cumulative WAL:\s*(?P<cuml_wal_writes>.*?)\s*writes,\s*(?P<cuml_wal_syncs>.*?)\s*syncs,\s*(?P<cuml_writes_per_sync>.*?)\s*writes per sync,\s*written:\s*(?P<cuml_wal_written>.*?),\s*(?P<cuml_wal_rate>.*)',
        r'Cumulative stall:\s*(?P<cuml_stall_time>.*?)\s*H:M:S,\s*(?P<cuml_stall_percent>.*?)\s*percent',
        r'Interval writes:\s*(?P<int_writes>.*?)\s*writes,\s*(?P<int_keys>.*?)\s*keys,\s*(?P<int_commit_groups>.*?)\s*commit groups,\s*(?P<int_writes_per_group>.*?)\s*writes per commit group,\s*ingest:\s*(?P<int_ingest>.*?),\s*(?P<int_ingest_rate>.*)',
        r'Interval stall:\s*(?P<int_stall_time>.*?)\s*H:M:S,\s*(?P<int_stall_percent>.*?)\s*percent'
    }

    misc_stat_expressions = {
        fr'Uptime\(secs\):\s+(?P<total_uptime_sec>{float_re})\s+total,\s+(?P<interval_uptime_sec>{float_re})\s+interval',
        r'Flush\(GB\):\s*cumulative\s*(?P<cuml_flush_gb>.*?),\s*interval\s*(?P<int_flush_gb>.*)',
        r'Cumulative compaction:\s*(?P<cuml_compaction_write>.*?)\s*write,\s*(?P<cuml_compaction_write_rate>.*?)\s*write,\s*(?P<cuml_compaction_read>.*?)\s*read,\s*(?P<cuml_compaction_read_rate>.*?)\s*read,\s*(?P<cuml_compaction_elapsed>.*?)\s*seconds',
        r'Interval compaction:\s*(?P<int_compaction_write>.*?)\s*write,\s*(?P<int_compaction_write_rate>.*?)\s*write,\s*(?P<int_compaction_read>.*?)\s*read,\s*(?P<int_compaction_read_rate>.*?)\s*read,\s*(?P<int_compaction_elapsed>.*?)\s*seconds',
        r'Write Stall \(count\):\s*cf-l0-file-count-limit-delays-with-ongoing-compaction:\s*(?P<cf_l0_delays_ongoing>.*?),\s*cf-l0-file-count-limit-stops-with-ongoing-compaction:\s*(?P<cf_l0_stops_ongoing>.*?),\s*l0-file-count-limit-delays:\s*(?P<l0_delays>.*?),\s*l0-file-count-limit-stops:\s*(?P<l0_stops>.*?),\s*memtable-limit-delays:\s*(?P<memtable_delays>.*?),\s*memtable-limit-stops:\s*(?P<memtable_stops>.*?),\s*pending-compaction-bytes-delays:\s*(?P<pending_delays>.*?),\s*pending-compaction-bytes-stops:\s*(?P<pending_stops>.*?),\s*total-delays:\s*(?P<total_delays>.*?),\s*total-stops:\s*(?P<total_stops>.*)',
        r'interval:\s*(?P<interval_count>.*?)\s*total count',
        r'Block cache .*?@.*?#.*?\s*capacity:\s*(?P<block_cache_capacity>.*?)\s*seed:\s*(?P<block_cache_seed>.*?)\s*usage:\s*(?P<block_cache_usage>.*?)\s*table_size:\s*(?P<block_cache_table_size>.*?)\s*occupancy:\s*(?P<block_cache_occupancy>.*?)\s*collections:\s*(?P<block_cache_collections>.*?)\s*last_copies:\s*(?P<block_cache_last_copies>.*?)\s*last_secs:\s*(?P<block_cache_last_sec>.*?)\s*secs_since:\s*(?P<block_cache_since_sec>.*)',
        r'Block cache entry stats\(count,size,portion\):\s*(?P<block_cache_stat_list>.*)'
    }

    expressions = set()
    if stats_type != 'misc':
        expressions.update(db_stat_expressions)
    if stats_type != 'db':
        expressions.update(misc_stat_expressions)

    for expression in expressions:
        match = re.search(expression, line)
        if match != None:
            return match

    return None

def parse_stats(stat, unified_stats):

    stat = stat.lstrip()
    stat = stat.rstrip()
    splited_stat = stat.split('\n')

    for i, line in enumerate(splited_stat):
        match = match_any_stat(line)
        if match:
            dict = match.groupdict()
            for key, value in dict.items():
                #Carefull with uptime
                if key.endswith('_time'):
                    t = datetime.strptime(value, "%H:%M:%S.%f")
                    value = timedelta(hours=t.hour, minutes=t.minute, seconds=t.second, microseconds=t.microsecond)
                elif key.endswith('_sec'):
                    value = ureg(value + ' seconds')
                elif key.endswith('_gb'):
                    value = ureg(value + ' GB')
                elif key == "block_cache_stat_list":
                    inner_pattern = r'(?P<type>\w+)\((?P<count>.*?),(?P<size>.*?),(?P<portion>.*?)%\)'
                    matches = re.finditer(inner_pattern, value)
                    new_value = []
                    for block in matches:
                        new_value.append({
                            "type": block.group("type"),
                            "count": ureg(block.group("count")),
                            "size": ureg(block.group("size")),
                            "portion": ureg(block.group("portion"))
                        })
                    value = new_value
                else:
                    value = ureg(value)
                unified_stats[key] = value

def pre_process_row(row):
    "A row might have a number followed by a space and a unit"
    "To make splitting easier just want to delete the space"
    re_units = r'(GB|MB|KB|B)'
    value_index = 0
    row = row.lstrip()
    row = row.rstrip()
    values = row.split()
    new_row = []
    while value_index < len(values) - 1:
        val = values[value_index]
        next_val = values[value_index + 1]
        match = re.search(re_units, next_val)
        #If next value is a unit then merge val with unit
        if match:
            val = val + next_val
            value_index += 1
        new_row.append(val)
        value_index += 1
    return ' '.join(new_row)

def parse_compaction_stats(compaction_stat, unified_stats):
    if "compaction_stats" not in unified_stats:
        unified_stats["compaction_stats"] = {}
    stat = {}
    compaction_stat = compaction_stat.lstrip()
    compaction_stat = compaction_stat.rstrip()
    lines = compaction_stat.split('\n')
    headers = lines[0].split()

    #Only start from third line
    #First line is header
    #Second line is separator
    for row in lines[2:]:
        #For now hacky way to stop parsing when we encounter
        #compaction stats for user. For now compaction information
        #by levels is good enough. Just before **Compaction Stats [default] ** (for user)
        #there is a line with no content
        if row == '':
            break
        row = pre_process_row(row)
        values = row.split()
        row_stats = {}
        for i, val in enumerate(values[1:]):
            header = headers[i + 1]
            re_header_unit = r'.*?\((?P<header_unit>.*?)\)'
            match = re.search(re_header_unit, header)
            if match and match.group('header_unit') != 'cnt':
                val = ureg(val + match.group('header_unit'))
            elif val.isnumeric():
                val = float(val)
            elif header == 'Size':
                val = ureg(val)
            row_stats[header] = val
        stat[values[0]] = row_stats

    unified_stats["compaction_stats"] = stat

def unify_stats(db_stats, compaction_stats, misc_stats):
    res = {}
    for i, db_stat in enumerate(db_stats):
        match = re.search(fr'Uptime\(secs\):\s+({float_re})', db_stat)
        if match:
            uptime = match.group(1)
            uptime_str = str(uptime)
            res[uptime_str] = {}
            parse_stats(db_stat, res[uptime_str])
            parse_compaction_stats(compaction_stats[i], res[uptime_str])
            parse_stats(misc_stats[i], res[uptime_str])
    return res

def get_db_stats(text):
    db_stats = re.split(r'\*\* DB Stats \*\*((.|\s)*?)\*\* Compaction Stats', text)
    compaction_stats = re.split(r'\*\* Compaction Stats \[default\] \*\*((.|\s)*?)Blob file', text)
    float_re = r'\d(\.\d+)?'
    misc_stats = re.split(fr'space amp:\s+{float_re}\n((.|\s)*?)\*\* File Read', text)

    db_stats_group = []
    compaction_stats_group = []
    misc_stats_group = []
    for group in db_stats:
        new_group = group[:20]
        if re.search(r'Uptime', new_group):
            db_stats_group.append(group)

    for group in compaction_stats:
        new_group = group[:20].strip()
        if new_group.startswith("Level"):
            compaction_stats_group.append(group)

    for group in misc_stats:
        new_group = group[:20].strip()
        if new_group.startswith(r'Uptime(secs)'):
            misc_stats_group.append(group)


    return unify_stats(db_stats_group, compaction_stats_group, misc_stats_group)
    #print(db_stats_group)
    #print(compaction_stats_group)
    #print(misc_stats_group)

def stats_to_json_dict(stats_dict):
    json_dict = {}
    for key, val in stats_dict.items():
        if isinstance(val, Quantity) or isinstance(val, timedelta):
            val = str(val)
        elif isinstance(val, list):
            val = [ stats_to_json_dict(x) for x in val ]
        elif isinstance(val, dict):
            val = stats_to_json_dict(val)
        json_dict[key] = val
    return json_dict

def print_db_stats(json_dict, fmt='fancy_grid', file_out=sys.stdout, transpose=True):
    table = []
    header = []
    for uptime, val in json_dict.items():
        copy_val = val.copy()
        copy_val.pop("compaction_stats", None)
        copy_val.pop("block_cache_stat_list", None)
        sorted_items = sorted(copy_val.items(), key=lambda x: x[0])
        if header == []:
            header = [ x[0] for x in sorted_items ]
            table.append(header)
        row = [ x[1] for x in sorted_items ]
        table.append(row)
    if transpose:
        table = list(map(list, zip(*table)))
    print(tabulate(table, tablefmt=fmt), file=file_out)

def print_compaction_stats(json_dict, fmt='fancy_grid', file_out=sys.stdout):
    for uptime, val in json_dict.items():
        print("Uptime: " + uptime)
        table = []
        cur_dict = val["compaction_stats"]
        sorted_levels = sorted(cur_dict.items(), key=lambda x: x[0])
        header = [' ']
        for level, level_stats in sorted_levels:
            row = [level]
            sorted_stats = sorted(level_stats.items(), key=lambda x: x[0])
            if len(header) == 1:
                header.extend([x[0] for x in sorted_stats])
                table.append(header)
            row.extend([x[1] for x in sorted_stats])
            table.append(row)
        print(tabulate(table, tablefmt=fmt), file=file_out)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='Rocksdb log parser',
        description='Parses log output from rocksdb'
    )

    parser.add_argument('--units_path', type=str, help="Requried if --db_log is used")
    parser.add_argument('--db_log', type=str)
    parser.add_argument('--bench_log', type=str)
    parser.add_argument('--out_fmt', type=str, default='table')
    parser.add_argument('--json_indent', type=int)

    args = parser.parse_args()
    if args.units_path == None and args.db_log != None:
        parser.error('--units_path is required when --db_log is used')

    if args.bench_log != None:
        bench_fd = open(args.bench_log, "r")
        bench_input = bench_fd.read()
        if args.out_fmt == 'json':
            json_dict = {
                "read" : get_stats("read", bench_input),
                "write": get_stats("write", bench_input)
            }
            print(json.dumps(json_dict, indent=args.json_indent))
        if args.out_fmt == 'table':
            print_op_stats(bench_input)
    if args.db_log != None:
        ureg = UnitRegistry(args.units_path)
        db_log_fd = open(args.db_log, "r")
        db_log_input = db_log_fd.read()
        db_stats_dict = get_db_stats(db_log_input)
        if args.out_fmt == 'json':
            print(json.dumps(stats_to_json_dict(db_stats_dict), indent=args.json_indent))
        if args.out_fmt == 'table':
            print_compaction_stats(db_stats_dict)
            print_db_stats(db_stats_dict)
