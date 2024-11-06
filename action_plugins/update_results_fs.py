from __future__ import (absolute_import, division, print_function)
from ansible.errors import AnsibleActionFail, AnsibleActionSkip, AnsibleError
from ansible.plugins.action import ActionBase

import os
import json
import re
import glob
from datetime import datetime

accepted_deltas = {
    "delta_cache",
    "delta_write_buffer_size",
    "delta_max_write_buffer_number",
    "delta_base",
    "delta_sync",
    "delta_compaction-style"
}

accepted_files = {
    r'dstat-(.*?)\.csv' : "dstat.csv",
    r'dstat-(.*?)-cpu\.png' : "dstat-cpu.png",
    r'dstat-(.*?)-mem\.png' : "dstat-mem.png",
    r'dstat-(.*?)-disk\.png' : "dstat-disk.png",
    r'temp-(.*?)\.csv' : "temp.csv",
    r'temp-(.*?)\.png' : "temp.png",
    r'sys-energy-(.*?)\.csv' : "sys-energy.csv",
    r'sys-hardware-(.*?)\.csv' : "sys-hardware.csv",
    r'rocksdb-(.*?)\.log' : "rocksdb.log",
    r'summary_info\.json' : "summary_info.json",
    r'sdpmonserver\.log'  : "sdpmonserver.log",
    r'pid-(.*?)\.csv' : "pid-energy.csv",
    r'bench-log-(.*?)\.log' : "bench-log.log",
    r'bench-log-(.*?)-throughput\.png' : "bench-log-throughput.png",
    r'options-(.*?)\.log' : "options.log",
    r'db-log-(.*?)\.log' : "db-log.log",
    r'energy-report-(.*?)\.log' : "energy-report.log"
}

def check_filemove(path):
    basename = os.path.basename(path)
    for re_pattern, new_basename in accepted_files.items():
        if re.search(re_pattern, basename) != None:
            #print(basename, re_pattern, new_basename)
            return new_basename
    return None

def pid_datetime(path):
    pid_fd = open(path, "r")
    head = [next(pid_fd) for _ in range(2)]
    data_line = head[-1]
    ts_str = data_line.split(';')[0]
    return datetime.fromisoformat(ts_str)

def get_pid_rep_num(path):
    basename: str = os.path.basename(path)
    if not basename.startswith("pid-"):
        return None

    #get all pid files from dirname
    dirname = os.path.dirname(path)
    pids = glob.glob(dirname + "/pid-*.csv")
    sorted_pids = sorted(pids, key=pid_datetime)

    rep = 0
    for pid_path in sorted_pids:
        basename_pid = os.path.basename(pid_path)
        if basename_pid == basename:
            return rep
        rep += 1

    return None


def get_rep_num(path):
    basename: str = os.path.basename(path)

    if basename.startswith("pid-"):
        return get_pid_rep_num(path)

    match = re.search(r'-(\d+)', basename)
    rep = 0
    if match != None:
        rep = int(match.group(1))
    return rep

def get_newfile_path(path):
    new_basename = check_filemove(path)

    if new_basename == None:
        return None

    rep = get_rep_num(path)
    absolute_path = os.path.abspath(path)
    dir_absolute_path = os.path.abspath(os.path.dirname(absolute_path))

    new_absolute_path = os.path.abspath(dir_absolute_path + f"/repetition-{rep}/" + new_basename)
    return new_absolute_path

def check_report(report_file):
    report_fd = open(report_file, "r")
    event_keys = ["thread_id_system", "energy", "event_type"]
    try:
        report_json = json.load(report_fd)
        if isinstance(report_json, list):
            return False
        if "events" not in report_json.keys():
            return False
        if not isinstance(report_json["events"], list):
            return False
        events: list = report_json["events"]
        if len(events) == 0:
            return False
        if not isinstance(events[0], dict):
            return False
        event: dict = events[0]
        for key in event_keys:
            if key not in event.keys():
                return False
        if "thread_info" not in report_json.keys():
            return False

        tid_info = report_json["thread_info"]
        if len(tid_info.keys()) == 0:
            return False

        return True
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False

def get_relative_path(absolute_path: str, absolute_base: str):
    if absolute_path.startswith(absolute_base):
        return absolute_path.split(absolute_base)[-1]
    return None

def delta_dir(dir_path):
    basename:str = os.path.basename(dir_path)
    delta: str
    for delta in accepted_deltas:
        if basename.startswith(delta):
            return True
    return False

class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()
        result = super(ActionModule, self).run(tmp, task_vars)

        del tmp # tmp no longer has any effect

        try:
            if self._task.check_mode:
                raise AnsibleActionSkip('check mode not (yet) supported for this module')

            validation_result, new_module_args = self.validate_argument_spec(
                argument_spec = {
                    'base_dir': {'type': 'str'}
                },
            )

            base_absolute_path = os.path.abspath(new_module_args['base_dir'])
            #Argument has to be a directory
            if os.path.isfile(base_absolute_path):
                result["error_msg"] = "base_dir arg has to be a directory"
                raise AnsibleActionFail

            files_mapping = {}
            visited_files = set()

            for root, dirs, files in os.walk(base_absolute_path):
                dir_absolute_path = os.path.abspath(root)
                if delta_dir(root):
                    for file in files:
                        file_absolute_path = dir_absolute_path + '/' + file
                        new_path = get_newfile_path(file_absolute_path)
                        if new_path != None and (file_absolute_path not in visited_files):
                            visited_files.add(file_absolute_path)
                            files_mapping[file_absolute_path] = new_path

            for abs_path, new_abs_path in files_mapping.items():
                #Make sure the intermediate directories are created
                os.makedirs(os.path.dirname(new_abs_path), exist_ok=True)
                os.rename(abs_path, new_abs_path)

        except AnsibleError:
            result['failed'] = True
            result['changed'] = False
        return result
