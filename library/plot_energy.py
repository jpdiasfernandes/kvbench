from __future__ import (absolute_import, division, print_function)

from module_utils.energy_report import DiskPlotter
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
    io_file:
        description: Fine grained disk io activity file path
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
        io_file: io.json
'''

RETURN = r'''

'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.energy_report import Report, ReportPlotter
import matplotlib.pyplot as plt
import pandas as pd
import os
import json
import re

def get_tid_from_col(col_string):
    tid_col_regex = r'.*?Tid (\d+) Energy'
    match_tid = re.match(tid_col_regex, col_string)
    if match_tid != None:
        return int(match_tid.group(1))

    #If did could not match return None
    return None

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
        report_file=dict(type='str', required=True),
        output_prefix=dict(type='str', required=False),
        chdir=dict(type='str', required=False),
        io_file=dict(type='str', required=False)
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False
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
        file_no_format = module.params['report_file'][:-4]
    else:
        file_no_format = module.params['output_prefix']

    report = Report.load_json(module.params['report_file'])
    plotter = ReportPlotter(report)
    plotter.foreground_energy(file_no_format + "-foreground-energy.pdf")
    result['changed'] = True
    plotter.compaction_energy(file_no_format + "-compaction-energy.pdf")
    plotter.flush_energy(file_no_format + "-flush-energy.pdf")
    plotter.compaction_events_energy(file_no_format + "-compaction-events-energy.pdf", height=20, width=25)
    plotter.compaction_level_report(file_no_format + "-compaction_level_info.pdf")

    if module.params['io_file']:
        io_file = module.params['io_file']
        disk_plotter = DiskPlotter(io_file)
        disk_plotter.plot_compaction_io_info(plotter, 0.1, "events-io-activity.pdf")
    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()
