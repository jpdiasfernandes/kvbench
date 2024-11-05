import time
import os
from datetime import datetime
import json
import argparse
import sys
import signal


log = {}
out_path = None
def exit_handler(sig, frame):
    if out_path != None and log != {}:
        out_fd = open(out_path, "w")
        json.dump(log, out_fd)
        print(f"Received Signal {sig} will dump log, stopped monitoring.", file=sys.stderr)
    exit()

def read_io_stats(tid):
    io_stats_path = f"/proc/{tid}/task/{tid}/io"
    io_data = {}

    try:
        with open(io_stats_path, 'r') as f:
            for line in f:
                key, value = line.split(':')
                io_data[key.strip()] = int(value.strip())
    except FileNotFoundError:
        print(f"Process with PID {pid} does not exist.")
        return None
    except Exception as e:
        print(f"Error reading I/O stats: {e}")
        return None

    return io_data

def iteration_monitored_tids(before_tids: dict, tids: dict):
    return before_tids.keys() & tids.keys()

def find_tids(pid):
    # Iterate through all directories in /proc that represent PIDs
    tids = set()
    try:
        for tid in os.listdir(f"/proc/{pid}/task"):
            tids.add(tid)
    finally:
        return tids


def iteration_io_stats(pid):
    tids = find_tids(pid)
    iteration_stats = {}
    for tid in tids:
        if tid_io_stats := read_io_stats(tid) != None:
            iteration_stats[tid] = tid_io_stats

    return iteration_stats

def diff_io_stats(io_stat_before, io_stat_after):
    res = {}
    for stat, value in io_stat_before.items():
        res[stat] = io_stat_after[stat] - value
    return res

def calc_diff_tids(tids, io_stats_before, io_stats_after):
    iteration_diffs = {}
    for tid in tids:
        iteration_diffs[tid] = diff_io_stats(io_stats_before[tid], io_stats_after[tid])
    return iteration_diffs

def add_iteration_diffs_to_log(log, iteration_diff, datetime):
    for tid, diff_io_stats in iteration_diff.items():
        if tid not in log.keys():
            log[tid] = {}
        else:
            log[tid][datetime] = diff_io_stats

def monitor_pid_io(pid, interval, out):
    if not os.path.isdir(f"/proc/{pid}"):
        print(f"Process with PID {pid} does not exist.")
        return

    print(f"Monitoring I/O for PID {pid} (interval: {interval}s)")
    print("Press Ctrl+C to stop.\n")

    before_io_stats = {}
    first_read = True
    global log
    while True:
        io_stats = iteration_io_stats(pid)
        if io_stats != {}:
            if not first_read:
                it_tids = iteration_monitored_tids(before_io_stats, io_stats)
                diff_io_stats = calc_diff_tids(it_tids, before_io_stats, io_stats)
                add_iteration_diffs_to_log(log, diff_io_stats, datetime.now().isoformat())
            else:
                first_read = False
            before_io_stats = io_stats
        else:
            print("No available data for pid: " + str(pid), file=sys.stderr)
            break

        time.sleep(interval)

    out_fd = open(out, "w")
    json.dump(log, out_fd)

def get_name_from_stats(pid_stats_path):
    stats_fd = open(pid_stats_path, "r")
    stats_str = stats_fd.read()
    splited_stats = stats_str.split(' ')
    pid_name = splited_stats[1]
    #remove parenthesis
    pid_name = pid_name[1:-1]
    return pid_name

def find_pid_name(pid_name):
    pid_dirs = os.listdir('/proc')
    for dir in pid_dirs:
        if not dir.isnumeric():
            continue
        try:
            if get_name_from_stats('/proc/' + dir + '/stat') == pid_name:
                return int(dir)
        except:
            pass
    return None

def wait_for_pid(pid_name, wait_for_pid):
    print("Will wait for pid with name: " + pid_name)
    while (pid := find_pid_name(pid_name)) == None:
        time.sleep(wait_for_pid)
    return pid

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='FinerIO',
        description='Monitors a process threads IO'
    )

    pid_input = parser.add_mutually_exclusive_group(required=True)
    pid_input.add_argument('--pid_name', type=str)
    pid_input.add_argument('--pid_num', type=int)
    parser.add_argument('--sample_period', type=float, default=1)
    parser.add_argument('--wait_pid_period', type=float, default=1)
    parser.add_argument('--out_path', type=str)
    signal.signal(signal.SIGINT, exit_handler)
    signal.signal(signal.SIGTERM, exit_handler)

    args = parser.parse_args()
    pid = None
    if args.pid_name != None:
        pid = wait_for_pid(args.pid_name, args.wait_pid_period)
    elif args.pid_num != None:
        name = get_name_from_stats("/proc/" + str(args.pid_num) + "/stat")
        pid = args.pid_num

    out_path = args.out_path
    if args.out_path == None:
        out_path = "io-" + str(pid) + ".json"

    monitor_pid_io(pid, args.sample_period, out_path)
