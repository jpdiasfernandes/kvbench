#!/usr/bin/env python3

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: log_summary_info

short_description: Lists metrics that could be of interest for analysing the results.

version_added: "1.0.0"

description: Lists metrics that could be of interest for analysing the results.

options:
    energy_file:
        description: A csv file with a fixed structure relating to energy values of an application.
        required: true
        type: str
    event_file:
        description: A csv file with a fixed structure relating to kvs events.
        required: true
        type: str
    throughput_file:
        description: A log file from a rocksdb exectution ouput containing throughput information.
        required: true
        type: str
    chdir:
        description: A path to the current working directory
        required: false
        type: str
    output_prefix:
        description: The output prefix to replace, otherwise assume a prefix of summary_info
        required: false
        type: str
    repo_url:
        description: The repo url where the results for this workload are going to be stored
        required: true
        type: str

author:
    - José Pedro Fernandes (@jpdiasfernandes)
'''

EXAMPLES = r'''
# Generate a summary of important metrics.
- name: Generate a summary of execution metrics.
    plot_energy:
        energy_file: pid-1234.csv
        event_file: rocksdb.log
        throughput_file: rocksdb-bench.log
        chdir: /home/user/tool_results
        repo_url: www.github.com/repo/dir/subdir/workload
'''

RETURN = r'''

'''

from ansible.module_utils.basic import AnsibleModule
import os
import json
from datetime import datetime
import re
import math

def to_datetime_year(date_string):
    return datetime.fromisoformat(date_string)

def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        energy_file=dict(type='str', required=True),
        event_file=dict(type='str', required=True),
        throughput_file=dict(type='str', required=True),
        chdir=dict(type='str', required=False),
        output_prefix=dict(type='str', required=False),
        repo_url=dict(type='str', required=True)
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=True
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        module.exit_json(**result)

    if module.params['chdir'] != None:
        os.chdir(module.params['chdir'])

    if module.params['output_prefix'] == None:
        out_prefix = "summary_info"
    else:
        out_prefix= module.params['output_prefix']

    energy_fd = open(module.params['energy_file'])
    event_fd = open(module.params['event_file'])
    throughput_fd = open(module.params['throughput_file'])
    repo_url = module.params['repo_url']

    try:
        summary_fd = open(out_prefix + ".json", "r")
        input_json = json.load(summary_fd)
    except:
        input_json = {
            "repo": repo_url,
            "tests": []
        }

    res_json = {}

    ################# Get all the metrics from energy file #################
    # The duration will be taken from energy log as an aproximation to the
    # real duration. It might be off for +-2s

    energy_consumed = 0
    first_date_time = None
    last_date_time = None
    pid_energy_regex = r' Pid \d+ Accumulated Energy'

    header = energy_fd.readline()

    while header:
        line = energy_fd.readline()

        # store metrics
        splitted_header = header.split(';')
        splitted_line = line.split(';')
        timestamp = splitted_line[0]
        if first_date_time == None:
            first_date_time = to_datetime_year(timestamp)
        last_date_time = to_datetime_year(timestamp)
        for i in range(1, len(splitted_header)-1):
            if re.match(pid_energy_regex, splitted_header[i]) != None:
                energy_consumed += float(splitted_line[i])
                break
        # read header
        header = energy_fd.readline()


    if first_date_time != None and last_date_time != None:
        duration_sec = int((last_date_time - first_date_time).total_seconds())
        res_json["duration"] = duration_sec
        res_json["energy_consumed"] = math.floor(energy_consumed)
        res_json["avg_power"] = math.floor(energy_consumed / duration_sec)



    energy_fd.close()

    ################# End of getting all metrics from energy file  #################

    ################# Get all the metrics from the throughput file #################

    ops_regex = r'micros\/op.*?(?P<ops_sec>\d+(\.\d+)?).*?ops\/sec.*?\d+(\.\d+)?.*?seconds.*?(?P<ops_total>\d+).*?operations'

    throughput_text = throughput_fd.read()

    ops_match = re.search(ops_regex, throughput_text)

    if ops_match != None:
        res_json['total_ops'] = math.floor(float(ops_match.group('ops_total')))
        res_json['ops/sec'] = math.floor(float(ops_match.group('ops_sec')))
        res_json['j/ops'] = res_json['energy_consumed'] / res_json['total_ops']

    ################# End of getting all metrics from energy file  #################

    ################# Get all the metrics from the event file #################

    event_text = event_fd.read()
    event_json = json.loads(event_text)

    compactions_count = 0
    flush_count = 0

    for name, count in event_json["open_event"]["stats"]["counters"].items():
        split_name = name.split("#")
        if split_name[0] == "compaction":
            compactions_count += count
        elif split_name[0] == "flush":
            flush_count += count

    res_json['total_compactions'] = compactions_count
    res_json['total_flushes'] = flush_count


    input_json["tests"].append(res_json)
    output_fd = open(out_prefix + ".json", "w")

    print(json.dumps(input_json, indent=2), file=output_fd)

def main():
    run_module()

if __name__ == '__main__':
    main()
