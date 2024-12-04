from __future__ import (absolute_import, division, print_function, annotations)

__metaclass__ = type

DOCUMENTATION = r'''
---
module: plot_top_level_graphs

short_description: Plots top-level information about all deltas in a test_area.

version_added: "1.0.0"

description: Plots top-level information about all deltas in a test_area. Receives a
json with all deltas summary information.

options:
    summary_file:
        description: A json file with all the merged summary file for each delta
        required: true
        type: str
    area_name:
        description: The group/area name has it appears in the summary_file
        required: true
        type: str
    chdir:
        description: A path to the current working directory
        required: false
        type: str
    output_prefix:
        description: A path to the output prefix prepended to all figures paths
        required: false
        type: str
author:
    - José Pedro Fernandes (@jpdiasfernandes)
'''

EXAMPLES = r'''
- name: Generate all the top-level of memory delta
  plot_top_level_graphs:
      summary_file: summary.json
      area_name: memory
      chdir: /home/user/top_level_results
      output_prefix: memory
'''

RETURN =  r'''
'''

from ansible.module_utils.basic import AnsibleModule
import statistics
import matplotlib.pyplot as plt
import sys
import json
import re
import numpy as np
import os

delta_repetitions = []
delta_runs_values = {}
ylims = {
    "energy_consumed" : 160000,
    "energy_memory" : 7000,
    "energy_cpu_and_mem": 170000,
    "sys_cpu_energy": 210000,
    "total_ops" : 1300,
    "total_compactions": 1050,
    "total_flushes": 1200
}

def values_by_info_name(delta_metric_name, info_name):
    values = []
    for repetition_info in delta_repetitions:
        values.append(repetition_info["info"][delta_metric_name][info_name])
    return values

def get_stdev(delta_metric_name, info_name, factor=lambda x: x):
    repetitions_info_name = values_by_info_name(delta_metric_name, info_name)
    repetitions_info_name = [factor(x) for x in repetitions_info_name]
    print("stdev calculated with", repetitions_info_name, delta_metric_name)
    return statistics.stdev(repetitions_info_name)

def init_repetition(number_run):
    if len(delta_repetitions) <= number_run:
        delta_repetitions.extend([{ "deltas" : {}, "info" : {}} for _ in range(len(delta_repetitions), number_run + 1)])

def populate_delta_metric(delta_metric_name, info, repetition_info):
    delta = find_delta(delta_metric_name)
    repetition_info["info"][delta_metric_name] = info
    if delta not in repetition_info["deltas"]:
        repetition_info["deltas"][delta] = []
    repetition_info["deltas"][delta].append(delta_metric_name)

def sanitize_file_name(file_name):
    # Define a regex pattern that matches only valid characters for a file name
    valid_pattern = re.compile(r'[a-zA-Z0-9_\.\-]')

    # Filter the string to include only valid characters
    sanitized_name = ''.join(c for c in file_name if valid_pattern.match(c))

    # Prevent the file name from being '.' or '..'
    if sanitized_name in ['.', '..']:
        sanitized_name = ''

    return sanitized_name

def find_delta(full_name):
    delta_matchings = {
        #memory deltas
        r'^delta_cache_(.*?)(_zipf)?$' : "cache",
        r'^delta_write_buffer_size_(.*?)(_zipf)?$' : "write_buffer_size",
        r'^delta_max_write_buffer_number_(.*?)(_zipf)?$' : "max_write_buffer_number",
        #background deltas
        r'^delta_compaction-style_(.*?)(_zipf)?$' : "compaction-style",
        r'^delta_sync_(.*?)(_zipf)?$' : "sync",
        #concurrency
        r'^delta_(.*?)T(_zipf)?$' : "foreground",
        r'^delta_compactions_(.*?)(_zipf)?$' : "compactions",
        r'^delta_flushes_(.*?)(_zipf)?$' : "flushes",
        #base
        r'^delta_base_(.*?)(_zipf)?$' : "base"
    }

    delta = None
    for re_pattern, it_match in delta_matchings.items():
        if re.search(re_pattern, full_name) != None:
            delta = it_match
            if full_name.endswith("_zipf"):
                delta += "_zipf"
            #print("MATCH", delta, full_name, re_pattern)
            return delta

    return None

def find_metric(full_name):
    available_size_units = r'G|MB|KB|B|M'
    metrics_matchings = {
        #memory deltas metrics
        fr'^delta_cache_(\d+)({available_size_units})(_zipf)?$' : {"group" : 1, "type": int},
        r'^delta_cache_(base)(_zipf)?$' : {"group" : 1, "type" : str},
        fr'^delta_write_buffer_size_(\d+)({available_size_units})(_zipf)?$' : {"group" : 1, "type": int},
        r'^delta_write_buffer_size_(base)(_zipf)?$' : {"group" : 1, "type": str},
        r'^delta_max_write_buffer_number_(\d+)(_zipf)?$' : {"group" : 1, "type": int},
        r'^delta_max_write_buffer_number_(base)(_zipf)?$' : {"group" : 1, "type": str},
        #background delta metrics
        r'^delta_compaction-style_(universal|base)(_zipf)?$' : {"group" : 1, "type": str},
        r'^delta_sync_(\d+)(_zipf)?$' : {"group" : 1, "type": int},
        r'^delta_sync_(base)(_zipf)?$' : {"group" : 1, "type": str},
        #concurrency delta metrics
        r'^delta_(\d+)T(_zipf)?$' : {"group" : 1, "type": int},
        r'^delta_(base)T(_zipf)?$' : {"group" : 1, "type": str},
        r'^delta_compactions_(\d+)(_zipf)?$' : {"group" : 1, "type": int},
        r'^delta_compactions_(base)(_zipf)?$' : {"group" : 1, "type": str},
        r'^delta_flushes_(\d+)(_zipf)?$' : {"group" : 1, "type": int},
        r'^delta_flushes_(base)(_zipf)?$' : {"group" : 1, "type": str},
        #base delta metrics
        r'^delta_base_(\d+_\d+)(_zipf)?$' : {"group" : 1, "type": str},
        r'^delta_base_(\w)(_zipf)?$' : {"group" : 1, "type": str}
    }

    metric = None
    for re_pattern, match_info in metrics_matchings.items():
        if (match := re.search(re_pattern, full_name) ) != None:
            group = match_info["group"]
            type_info = match_info["type"]
            metric = match.group(group)
            if issubclass(type_info, int):
                metric = int(metric)
            #print("MATCH", metric, full_name, re_pattern)
            return metric

    return None

def get_timestamp(timestamp_dict):
    for timestamp in timestamp_dict.keys():
        return timestamp


def find_unit(full_name):
    available_size_units = r'G|MB|KB|B|M'
    units_matchings = {
        #memory deltas metrics
        fr'^delta_cache_(\d+)({available_size_units})(_zipf)?$' : {"group" : 2, "type": str},
        fr'^delta_write_buffer_size_(\d+)({available_size_units})(_zipf)?$' : {"group" : 2, "type": str}
    }

    units_factor = {
        "G" : 1024 * 1024 * 1024,
        "MB" : 1024 * 1024,
        "M" : 1024 * 1024,
        "KB" : 1024,
        "B" : 1
    }

    unit = None
    for re_pattern, match_info in units_matchings.items():
        if (match := re.search(re_pattern, full_name) ) != None:
            group = match_info["group"]
            unit = match.group(group)
            return units_factor[unit]
    return None

def sort_metrics(full_name : str):
    delta = find_delta(full_name)
    metric = find_metric(full_name)
    if delta == None:
        return -sys.maxsize
    if metric == None:
        return -sys.maxsize

    if delta.endswith("_zipf"):
        delta = delta[:-5]

    compaction_style_sorting = {
        "base" : 0,
        "universal" : 1
    }

    base_sorting = {
        "e": 0,
        "0_100" : 2,
        "25_75" : 3,
        "50_50" : 4,
        "66_33" : 5,
        "75_25" : 6,
        "d": 7, #95% reads 5%reads
        "b": 8, #95% reads 5%updates 95.24 % reads 4.76% writes
        "100_0" : 9
    }

    delta_sorts_funcs = {
        #memory delta sorts
        "cache" : {
            str: lambda x: 0 if x == "base" else x,
            int: lambda x: x * find_unit(full_name)
        },
        "write_buffer_size" : {
            str: lambda x: 0 if x == "base" else x,
            int: lambda x: x * find_unit(full_name)
        },
        "max_write_buffer_number" : {
            str: lambda x: 0 if x == "base" else x,
            int: lambda x: x
        },
        "compaction-style" : {
            str: lambda x: compaction_style_sorting[x] if x in compaction_style_sorting else x
        },
        "sync" : {
            str: lambda x: 0 if x == "base" else x,
            int: lambda x: x
        },
        "foreground" : {
            str: lambda x: 0 if x == "base" else x,
            int: lambda x: x
        },
        "compactions" : {
            str: lambda x: 0 if x == "base" else x,
            int: lambda x: x
        },
        "flushes" : {
            str: lambda x: 0 if x == "base" else x,
            int: lambda x: x
        },
        "base" : {
            str: lambda x : base_sorting[x] if x in base_sorting else x
        }
    }

    return delta_sorts_funcs[delta][type(metric)](metric)

def plot_delta(repetition_info, delta, delta_zipf, ax, info_name, unit_name, factor):
    metrics = []
    values = {}
    stdev = {}
    values["Uniform"] = []
    values["Zipfian"] = []
    stdev["Uniform"] = []
    stdev["Zipfian"] = []
    #print(repetition_info["deltas"][delta])
    #uniform distribution
    for delta_metric_name in sorted(repetition_info["deltas"][delta], key=sort_metrics):
        metric = find_metric(delta_metric_name)
        #metrics are the same for both distributions, only need to add one time
        metrics.append(metric)
        values["Uniform"].append(factor(repetition_info["info"][delta_metric_name][info_name]))
        stdev["Uniform"].append(get_stdev(delta_metric_name, info_name, factor))
    for delta_metric_name in sorted(repetition_info["deltas"][delta_zipf], key=sort_metrics):
        metric = find_metric(delta_metric_name)
        values["Zipfian"].append(factor(repetition_info["info"][delta_metric_name][info_name]))
        stdev["Zipfian"].append(get_stdev(delta_metric_name, info_name, factor))

    print(stdev["Uniform"], "Uniform", delta)
    print(stdev["Zipfian"], "Zipfian", delta)

    x = np.arange(len(metrics))
    width = 0.25
    multiplier = 0

    for distribution, measurement in values.items():
        offset = width * multiplier
        rects = ax.bar(x + offset, measurement, width, label=distribution, yerr=stdev[distribution])
        ax.bar_label(rects, padding=3)
        multiplier += 1

    ax.set_title(delta)
    ax.set_xticks(x + width, metrics)
    ax.set_ylabel(unit_name)
    ax.legend(ncols=2)
    if info_name in ylims:
        ax.set_ylim(0, ylims[info_name])


def plot_repetition(repetition_info, axs, number_columns, info_name, unit_name, factor):
    ax_number = 0
    for delta in repetition_info["deltas"].keys():
        #We want to compare zipf and uniform side by side.
        #When we find the uniform we also find the zipf counterpart
        #Do not want to redo this step
        if not delta.endswith("_zipf"):
            if number_columns == 1:
                axis = axs
            else:
                axis = axs[ax_number]

            ax_number += 1
            delta_zipf = delta + "_zipf"
            plot_delta(repetition_info, delta, delta_zipf, axis, info_name, unit_name, factor)

def plot_repetitions(info_name, unit_name, base_path, module, results, factor=lambda x: x):
    repetitions = len(delta_repetitions)
    if repetitions < 1:
        return
    number_rows = repetitions
    number_different_delta = len(delta_repetitions[0]["deltas"].keys())
    #Compare zipfian and uniform side by side so we only want half
    #of columns
    number_columns = int(number_different_delta / 2)
    fig, axs = plt.subplots(number_rows, number_columns)
    fig.set_size_inches(20,15)

    for i, repetition in enumerate(delta_repetitions):
        if number_rows == 1:
            axis = axs
        else:
            axis = axs[i]

        plot_repetition(repetition, axis, number_columns, info_name, unit_name, factor)

    fig.tight_layout()
    if not module.check_mode:
        fig.savefig(base_path + sanitize_file_name(info_name) + ".pdf")
    else:
        results['stdout_lines'].append(f'Would create figure for {info_name} top level graph')

def main(group, base_path, module, results):
    for delta_metric, timestamp_dict in group.items():
        repetitions = timestamp_dict[get_timestamp(timestamp_dict)]["tests"]
        repetition_number = 0
        for info in repetitions:
            init_repetition(repetition_number)
            this_repetition = delta_repetitions[repetition_number]
            populate_delta_metric(delta_metric, info, this_repetition)
            repetition_number += 1

    plot_repetitions("energy_memory", "Energy (J)", base_path, module, results)
    plot_repetitions("energy_cpu_and_mem", "Energy (J)", base_path, module, results)
    plot_repetitions("energy_consumed", "Energy (J)", base_path, module, results)
    plot_repetitions("sys_cpu_energy", "Energy (J)", base_path, module, results)
    plot_repetitions("j/ops", "ops/J", base_path, module, results, lambda x: 1/x)
    plot_repetitions("total_ops", "MOps", base_path, module, results, lambda x : x/(10**6))
    plot_repetitions("total_compactions", "Number Compactions", base_path, module, results)
    plot_repetitions("total_flushes", "Number flushes", base_path, module, results)

def run_module():
    module_args = dict(
        summary_file=dict(type='str', required=True),
        area_name=dict(type='str', required=True),
        chdir=dict(type='str', required=False),
        output_prefix=dict(type='str', required=False)
    )

    result = dict(
        stdout_lines = []
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False
    )



    base_path = module.params['output_prefix']
    if base_path == None:
        base_path = '.'

    if module.params['chdir'] != None:
        os.chdir(module.params['chdir'])

    summary_fd = open(module.params['summary_file'], 'r')
    summary = json.load(summary_fd)
    area_name = module.params['area_name']

    if area_name not in summary:
        module.fail_json(msg="group/area not in summary info json", changed=False)

    group = summary[area_name]

    main(group, base_path, module, result)

    module.exit_json(**result)

if __name__ == '__main__':
    run_module()
