from __future__ import (absolute_import, division, print_function)
from ansible.errors import AnsibleActionFail, AnsibleActionSkip, AnsibleError
from ansible.plugins.action import ActionBase
import os
import json
import re

def get_rep_num(report_basename):
    match = re.search(r'(.*?)(-\d+)?\.log', report_basename)
    if match:
        if match.group(2) == None:
            return 0
        return int(match.group(2).strip('-'))
    return -1

def inc_counter(rep_dict, directory):
    if directory not in rep_dict:
        rep_dict[directory] = 1
    else:
        rep_dict[directory] += 1

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
                argument_spec= {
                    'base_dir': {'type': 'str'},
                    'out_base_dir' : {'type': 'str'}
                },
                required_together=[
                    ['base_dir', 'out_base_dir']
                ]
            )

            report_mapping = {}
            visited_reports = set()
            base_absolute_path = os.path.abspath(new_module_args['base_dir'])
            out_base_absolute_path = os.path.abspath(new_module_args['out_base_dir'])
            #Argument has to be a directory
            if os.path.isfile(out_base_absolute_path):
                result["error_msg"] = "out_base_dir arg has to be a directory"
                raise AnsibleActionFail

            os.makedirs(out_base_absolute_path, exist_ok=True)
            #Only accept empty directories
            if os.listdir(out_base_absolute_path):
                result["error_msg"] = "out_base_dir arg has to be an empty directory"
                raise AnsibleActionFail

            for root, dirs, files in os.walk(new_module_args['base_dir']):
                dir_absolute_path = os.path.abspath(root)

                for file in files:
                    file_absolute_path = dir_absolute_path + '/' + file
                    relative_file_path = get_relative_path(file_absolute_path, base_absolute_path)
                    if relative_file_path:
                        if check_report(file_absolute_path) and (file_absolute_path not in visited_reports):
                            report_dir = os.path.dirname(relative_file_path)
                            report_basename = os.path.basename(relative_file_path)
                            rep_num = get_rep_num(report_basename)
                            rep_dir = "graphs_" + str(rep_num)
                            link_path = out_base_absolute_path + report_dir + "/" +  rep_dir + "/" + report_basename
                            report_mapping[file_absolute_path] = link_path
                            visited_reports.add(file_absolute_path)


            for original_path, link_path in report_mapping.items():
                link_dir = os.path.dirname(link_path)
                os.makedirs(link_dir, exist_ok=True)
                print(link_path)
                os.symlink(original_path, link_path)


        except AnsibleError:
            result['failed'] = True
            result['changed'] = False
        return result
