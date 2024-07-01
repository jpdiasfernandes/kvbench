#!/usr/bin/env python3
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: generate_energy_report

short_description: Generates an energy report and also plots the report

version_added: "1.0.0"

description: Generates a comprehensive energy report and also plots various graphs
to visuazlize the results

options:
    energy_file:
        description: A csv file with a fixed structure relating to energy values of an application.
        required: true
        type: str
    event_file:
        description: A csv file with a fixed structure relating to kvs events.
        required: true
        type: str
    chdir:
        description: A path to the current working directory
        required: false
        type: str
    output_prefix
        description: A prefix for the output file name
        required: false
        type: str

author:
    - José Pedro Fernandes (@jpdiasfernandes)
'''

EXAMPLES = r'''
# Generate the energy report and also plot a visual presentation of the report
- name: Generate an energy report
    generate_energy_report:
        energy_file: pid-1234.csv
        event_file: rocksdb.log
        chdir: /home/user/tool_results
'''

RETURN = r'''

'''

from ansible.module_utils.basic import AnsibleModule
import sys
from datetime import datetime
import datetime as dt
from collections import namedtuple
import re
import json
import os
import matplotlib.pyplot as plt

def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        energy_file=dict(type='str', required=True),
        event_file=dict(type='str', Required=True),
        chdir=dict(type='str', required=False),
        output_prefix=dict(type='str', required=False)
    )

    # seed the result dict in the object
    result = dict(
        changed=True
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    if module.check_mode:
        module.exit_json(**result)

    if module.params['chdir'] != None:
        os.chdir(module.params['chdir'])
        print(os.getcwd())

    if module.params['output_prefix'] == None:
        filename = "energy_report.png"
    else:
        filename = module.params['output_prefix'] + ".png"

    new_event_json = generate_report(module.params['event_file'], module.params['energy_file'])

    plot_report(new_event_json, filename)
    module.exit_json(**result)

Interval = namedtuple("Interval", ["start", "end"])

def plot_report(event_json, output):
    energy_report = event_json["open_event"]["energy_report"]
    compaction_info = energy_report["compaction_report"]
    flush_info = energy_report["flush_report"]
    total_energy = energy_report["total_energy"]

    compactions_levels = list(compaction_info["levels_energy"].keys())
    compaction_energy = list(compaction_info["levels_energy"].values())

    total_compaction_energy = sum(compaction_energy)

    percentages_compaction = [(energy / total_compaction_energy) * 100 for energy in compaction_energy]

    x_labels_compactions = []
    for level in compactions_levels:
        level_regex = r'\((\d+), (\d+)\)'
        match_obj = re.match(level_regex, level)
        if match_obj != None:
            x_labels_compactions.append(f"{match_obj.group(1)}-{match_obj.group(2)}")

    events = ["compaction", "flush", "rest"]
    events_energy = [compaction_info["total_energy"], flush_info["total_energy"]]

    sum_events = sum(events_energy)
    rest_energy = total_energy - sum_events

    events_energy.append(rest_energy)

    percentages_events = [(energy/total_energy) * 100 for energy in events_energy]

    fig, axs = plt.subplots(1, 2, figsize=(15,6))


    axs[0].grid(True, which='both', axis='both', linestyle='--', linewidth=0.5, color='gray')
    axs[1].grid(True, which='both', axis='both', linestyle='--', linewidth=0.5, color='gray')

    # Plotting the first histogram
    bars1 = axs[0].bar(x_labels_compactions, percentages_compaction, color='skyblue', edgecolor='black')
    axs[0].set_xlabel('Levels')
    axs[0].set_ylabel('Percentage (%)')
    axs[0].set_title('Histogram of Levels (Percentage of Total Values)')

    # Plotting the second histogram with the misc bar
    bars2 = axs[1].bar(events, percentages_events, color='lightcoral', edgecolor='black')
    axs[1].set_xlabel('Events')
    axs[1].set_ylabel('Percentage (%)')
    axs[1].set_title('Histogram of Events (Percentage of Total Value)')

     # Ensure bars are in front of grid lines
    for bars in [bars1, bars2]:
        for bar in bars:
            bar.set_zorder(10)


    fig.tight_layout()
    fig.savefig(output)

    #plt.show()

def generate_event_energy_report(event_json, energy):
    sub_events = event_json["open_event"]["sub_events"]
    compaction_info = {
        "total_energy" : 0,
        "levels_energy" : {},
        "levels_num" : {},
        "avg_per_compaction" : {}
    }
    flush_info = {
        "total_energy": 0,
        "num" : 0
    }

    thread_info = {}
    for idx, event in enumerate(sub_events):
        event_energy = max(0, get_event_consumption(event, energy))

        event_json["open_event"]["sub_events"][idx]["energy"] = event_energy
        tid = str(event["thread_id_system"]["start"])

        event_type = event["name"].split("#")[0]

        if tid not in thread_info:
            thread_info[tid] = {
            }

        if event_type == "compaction":
            compaction_info["total_energy"] += event_energy
            # If older version of log and context was not available
            if "context" in event:
                level = str((event["context"]["level_info"]["from"], event["context"]["level_info"]["to"]))
                if level not in compaction_info["levels_energy"]:
                    compaction_info["levels_energy"][level] = 0
                    compaction_info["levels_num"][level] = 0

                compaction_info["levels_energy"][level] += event_energy
                compaction_info["levels_num"][level] += 1

            if "compaction" not in thread_info[tid]:
                thread_info[tid]["compaction"] = {
                        "total_energy" : 0,
                        "num" : 0
                    }

            thread_info[tid]["compaction"]["total_energy"] += event_energy
            thread_info[tid]["compaction"]["num"] += 1
        elif event_type == "flush":
            flush_info["total_energy"] += event_energy
            flush_info["num"] += 1

            if "flush" not in thread_info[tid]:
                thread_info[tid]["flush"] = {
                    "total_energy" : 0,
                    "num" : 0
                }

            thread_info[tid]["flush"]["total_energy"] += event_energy
            thread_info[tid]["flush"]["num"] += 1

        for level in compaction_info["levels_energy"].keys():
            avg = compaction_info["levels_energy"][level] /compaction_info["levels_num"][level]
            compaction_info["avg_per_compaction"][level] = round(avg, 4)

        if flush_info["num"] != 0:
            avg = flush_info["total_energy"] / flush_info["num"]
            flush_info["avg"] = round(avg, 4)

    return flush_info, compaction_info, thread_info

def add_energy_values(energy, header, line, ts):
    tid_col_regex = r' Tid (\d+) Energy'
    line_energy = 0
    for i in range(1, len(header) -1):
        res_match = re.fullmatch(tid_col_regex, header[i])
        if res_match != None:
            tid = int(res_match.group(1))
            consumed = float(line[i])
            if tid not in energy:
                energy[tid] = {}
                energy[tid]["total_energy"] = 0
            energy[tid][str(ts)] = consumed
            line_energy += consumed

    return line_energy

def parse_energy_file(path):
    # Organized as tid -> { time -> value }
    fd = open(path, "r")
    energy = {}
    total_energy = 0

    header = fd.readline()

    while header:
        line = fd.readline()
        splitted_header = header.split(';')
        splitted_line = line.split(';')
        ts_str = splitted_line[0]
        ts = datetime.fromisoformat(ts_str)
        total_energy += add_energy_values(energy, splitted_header, splitted_line, ts)

        # read header
        header = fd.readline()


    fd.close()

    return energy, total_energy


def round_seconds(obj):
    if obj.microsecond >= 500_000:
        obj += dt.timedelta(seconds=1)
    return obj.replace(microsecond=0)


def get_available_times(interval, tid):
    res = []
    interval_len = (interval.end - interval.start).seconds + 1
    for i in range(0, interval_len):
        time = interval.start + dt.timedelta(seconds=i)
        if str(time) in tid:
            res.append(time)
    # If there was a jump in measurements then it probably means that
    # the the timestamp was close to the next second so it makes sense
    # to count the second before the start
    # The start is the second after when the event started.
    if len(res) < interval_len:
        res.insert(0, interval.start - dt.timedelta(seconds=1))

    return res

def get_thread_consumption(interval, tid):
    times = get_available_times(interval, tid)
    event_energy = 0

    for time in times:
        try:
            event_energy += tid[str(time)]
        except:
            print("No energy value for " + str(time), file=sys.stderr)


    return event_energy

def get_interval(start, end):
    start_copy = start
    start_copy += dt.timedelta(seconds=1)
    start_copy = start_copy.replace(microsecond=0)

    end_copy = end
    end_copy += dt.timedelta(seconds=1)
    end_copy = end_copy.replace(microsecond=0)

    return Interval(start_copy, end_copy)

def get_event_consumption(event_json, energy_info):
    datetime_start = datetime.fromisoformat(event_json["date_time"]["start"])
    datetime_end = datetime.fromisoformat(event_json["date_time"]["end"])
    tid = event_json["thread_id_system"]["start"]
    interval = get_interval(datetime_start, datetime_end)
    event_consumption = get_thread_consumption(interval, energy_info[tid])
    return round(event_consumption, 4)

def generate_report(event_file, energy_file):
    event_fd = open(event_file, "r")
    event_json = json.load(event_fd)

    energy, total_energy = parse_energy_file(energy_file)

    flush_info, compaction_info, thread_info = generate_event_energy_report(event_json, energy)

    event_json["open_event"]["energy_report"] = {
        "total_energy" : total_energy,
        "compaction_report" : compaction_info,
        "flush_report" : flush_info,
        "thread_report" : thread_info
    }

    event_fd.close()

    event_fd = open("energy_report.log", "a")
    json.dump(event_json["open_event"]["energy_report"], event_fd, indent=2)

    event_fd.close()

    return event_json

if __name__ == "__main__":
    run_module()
