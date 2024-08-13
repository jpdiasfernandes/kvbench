#!/usr/bin/env python3
from __future__ import (absolute_import, division, print_function)

stdout_lines = []
DOCUMENTATION = r'''
---
module: parse_compaction_size_info.py

short_description: Parses the rocksdb LOG file in search of compactions input files information

version_added: "1.0.0"

description: Parses the rocksdb LOG file and singles out lines where information about compactions
input files is given, saving that information in a json where the keys are the job_id and the values
the job files information

options:
    log_file:
        description: A rocksdb LOG file
        required: true
        type: str
    chdir:
        description: A path to the current working directory
        required: false
        type: str
    output
        description: A prefix for the output file name
        required: false
        type: str

author:
    - José Pedro Fernandes (@jpdiasfernandes)
'''

EXAMPLE = r'''
# Parse the rocksdb LOG file to extract all the compactions input files information
- name: Parse rocksdb LOG file
    parse_compaction_size_info:
        log_file: LOG
        chdir: /home/user/tool_results
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.event_input_size_parser import parser
import sys
import os
import json

def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        log_file=dict(type='str', required=True),
        chdir=dict(type='str', required=False),
        output=dict(type='str', required=False)
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
        stdout_lines.append(os.getcwd())

    if module.params['output'] == None:
        filename = "event_size_info"
    else:
        filename = module.params['output']

    log = open(module.params['log_file'], "r")
    for line in log.readlines():
        parser.parse(line)

    out = open(filename + ".log", "w")
    json.dump(parser.compactions, out)
    stdout_lines.append("Compactions processed: " + str(parser.compaction_number))
    result["stdout_lines"] = stdout_lines
    module.exit_json(**result)

if __name__ == "__main__":
    run_module()
