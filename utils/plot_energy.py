#!/usr/bin/env python3

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: plot_energy

short_description: Plots different information from a custom Fine-Grained energy monitoring tool.

version_added: "1.0.0"

description: Plots different information from a custom Fine-Grained energy monitoring tool.

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

author:
    - José Pedro Fernandes (@jpdiasfernandes)
'''

EXAMPLES = r'''
# Generate the energy plots of a certain application
- name Generate all types of energy plots from the application
    plot_energy:
        energy_file: pid-1234.csv
        event_file: rocksdb.log
        chdir: /home/user/tool_results
'''

RETURN = r'''

'''

from ansible.module_utils.basic import AnsibleModule
import matplotlib.pyplot as plt
import pandas as pd
import os
import json

def to_datetime(date_string):
    return pd.to_datetime(date_string, format="%d-%m %H:%M:%S")

def to_datetime_nodate(date_string):
    return pd.to_datetime(date_string, format="%H:%M:%S")

def to_datetime_year(date_string):
    return pd.to_datetime(date_string, format="%Y-%m-%d %H:%M:%S").floor("S")

def get_duration(date_time, first_date):
    return (date_time - first_date).total_seconds()

def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        energy_file=dict(type='str', required=True),
        event_file=dict(type='str', required=True),
        output_prefix=dict(type='str', required=False),
        chdir=dict(type='str', required=False)
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
        print(os.getcwd())

    if module.params['output_prefix'] == None:
        file_no_format = module.params['energy_file'][:-4]
    else:
        file_no_format = module.params['output_prefix']

    energy_pd = open(module.params['energy_file'])
    metrics = {}
    fields = []


    header = energy_pd.readline()

    first_date_time = None


    while header:
        line = energy_pd.readline()

        # store metrics
        splitted_header = header.split(';')
        splitted_line = line.split(';')
        timestamp = splitted_line[0]
        if first_date_time == None:
            first_date_time = to_datetime_year(timestamp)
        metrics[timestamp] = {}
        for i in range(1, len(splitted_header)-1):
            metrics[timestamp][splitted_header[i]] = splitted_line[i]
            if not splitted_header[i] in fields:
                fields.append(splitted_header[i])

        # read header
        header = energy_pd.readline()

    energy_pd.close()

    df = pd.DataFrame()


    last_dur = 1
    for time, metric in metrics.items():
        for key, value in metric.items():
            dur = get_duration(to_datetime_year(time), first_date_time)
            last_dur = dur
            df.at[dur, key] = float(value)

    threads_df = df.filter(regex=(r' Tid \d+ Energy'))
    pid_acc = df.filter(regex=(r' Pid \d+ Accumulated Energy'))
    pids = df.filter(regex=(r' Pid \d+ Energy'))


    threads_df.plot()
    plt.title('Threads Energy')
    plt.ylabel('J')
    plt.xlabel('seconds')
    plt.savefig(file_no_format + "-tids-energy.png")

    pid_acc.plot()
    plt.title('Pid Accumulated Energy')
    plt.ylabel('J')
    plt.xlabel('seconds')
    plt.savefig(file_no_format + "-acc-energy.png")

    pids.plot()
    plt.title('Process and Descendants Energy')
    plt.ylabel('J')
    plt.xlabel('seconds')
    plt.savefig(file_no_format + "-pids-energy.png")

    events = open(module.params['event_file'], "r")

    event_json = json.load(events)

    sub_events = event_json["open_event"]["sub_events"]

    plt.figure().set_figwidth(last_dur/2)

    event_tids = []
    for event in sub_events:
        tid = event["thread_id_system"]["start"]
        if tid not in event_tids:
            event_tids.append(tid)
            name = ' Tid ' + str(tid) + ' Energy'
            label = 'Tid ' + str(tid) + ' energy'
            plt.plot(threads_df.index.tolist(), threads_df[name].tolist(), label=label, linestyle='dashed')

    for event in sub_events:
        split_name = event["name"].split("#")
        event_type = split_name[0]
        tid = event["thread_id_system"]["start"]
        date_time_start = event["date_time"]["start"]
        date_time_end = event["date_time"]["end"]
        dur_start = get_duration(to_datetime_year(date_time_start), first_date_time)
        dur_end = get_duration(to_datetime_year(date_time_end), first_date_time)
        collumn_name = ' Tid ' + str(tid) + ' Energy'


        if dur_start in threads_df.index:
            y = threads_df.loc[dur_start, collumn_name]
            if event_type == "compaction":
                plt.plot([dur_start], [y], ">", color="b")
            elif event_type == "flush":
                plt.plot([dur_start], [y], ">", color="r")

        if dur_end in threads_df.index:
            y = threads_df.loc[dur_end, collumn_name]
            if event_type == "compaction":
                plt.plot([dur_end], [y], "x", color="b")
            elif event_type == "flush":
                plt.plot([dur_start], [y], "x", color="r")



    #lines_events = events.readlines()

    #for event in lines_events[1:]:
    #    splited = event.split(";")
    #    tid = splited[2].split(" ")[1].strip("\n")
    #    if tid not in event_tids:
    #        event_tids.append(tid)
    #        name = ' Tid ' + str(tid) + ' Energy'
    #        label = 'Tid ' + str(tid) + ' energy'
    #        plt.plot(threads_df.index.tolist(), threads_df[name].tolist(), label=label, linestyle='dashed')

    #for event in lines_events[1:]:
    #    splited = event.split(";")
    #    event_type = splited[0]
    #    timestamp = splited[1]
    #    dur = get_duration(to_datetime_nodate(timestamp), first_date_time)
    #    tid = splited[2].split(" ")[1].strip("\n")
    #    collumn_name = ' Tid ' + str(tid) + ' Energy'

    #    if dur in threads_df.index:
    #        y = threads_df.loc[dur, collumn_name]
    #        if event_type == "Compaction":
    #            plt.plot([dur], [y], "p", color="b")
    #        elif event_type == "Flush":
    #            plt.plot([dur], [y], "s", color="r")

    plt.xlabel('Time (seconds)')
    plt.ylabel("Energy (Joules)")
    plt.legend()
    plt.savefig(file_no_format + '-tids-energy-events.png')

    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()

#file_no_format = sys.argv[1][:-4]
#
#plt.title('Package CPU power')
#plt.ylabel('W')
#plt.savefig(file_no_format + ".png")
