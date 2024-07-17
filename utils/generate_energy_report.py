#!/usr/bin/env python3
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

stdout_lines = []

levels_energy = {}
levels_power = {}

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
from ansible.module_utils.utils import Report
import sys
from datetime import datetime
import datetime as dt
from collections import namedtuple
import re
import json
import os
import matplotlib.pyplot as plt
import statistics

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
        changed=True,
        stdout_lines=[]
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
        filename = "energy_report"
    else:
        filename = module.params['output_prefix']

    report = Report(module.params['energy_file'], module.params['event_file'])

    report.dump("energy_report.log")
    report.plot(filename)
    report.plot_compaction_level_energy_histogram(3, "level_3_compaction_energy")
    report.plot_compaction_level_energy_histogram(2, "level_2_compaction_energy")
    report.plot_compaction_level_energy_histogram(1, "level_1_compaction_energy")
    report.plot_compaction_level_duration_histogram(3, "level_3_compaction_duration")
    report.plot_compaction_level_duration_histogram(2, "level_2_compaction_duration")
    report.plot_compaction_level_duration_histogram(1, "level_1_compaction_duration")

    result["stdout_lines"] = stdout_lines
    module.exit_json(**result)

if __name__ == "__main__":
    run_module()
