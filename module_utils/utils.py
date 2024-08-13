#!/usr/bin/env python3

from collections import namedtuple
from datetime import datetime
import datetime as dt
import re
from typing import Type
import matplotlib.pyplot as plt
import json
import sys
import statistics


Interval = namedtuple("Interval", ["start", "end"])

class HashUtils:
    def micro_from_dt(self, ts):
        minutes = (ts.hour * 60) + ts.minute
        seconds = (minutes * 60) + ts.second
        micro = (seconds * 1000 * 1000) + ts.microsecond
        return micro

    def micro_from_td(self, td):
        seconds = (td.days * 24 * 3600) + td.seconds
        micro = (seconds * 1000 * 1000) + td.microseconds
        return micro

    def round_or_trunc(self, ts, micro):
        micro_ts = self.micro_from_dt(ts)
        if (micro_ts%(micro)) >= (micro/2):
            return "round"
        else:
            return "trunc"

    def round_micro(self, ts, micro):
        micro_ts = self.micro_from_dt(ts)
        if (micro_ts%(micro)) >= (micro/2):
            ts += dt.timedelta(microseconds= micro)
        ts -= dt.timedelta(microseconds=(micro_ts%micro))
        return ts

    def hash_time(self, ts, timedelta):
        if timedelta.days == 0:
            return self.round_micro(ts, self.micro_from_td(timedelta))
        return ts

class DataPoint:
    def __init__(self, energy, cpu_cycles):
        self.energy = energy
        self.cpu_cycles = cpu_cycles

class TimeSerie:
    def __init__(self):
        self.series = {}
        self.total_energy = 0
        self.hash_utils = HashUtils()

    def add_value(self, ts, data_point):
        self.series[str(ts)] = data_point
        self.total_energy += data_point.energy

    def get_next_time(self, ts, number_steps):
        for str_ts in sorted(self.series.keys()):
            ts_series = datetime.fromisoformat(str_ts)
            if ts_series > ts:
                number_steps -= 1
            if number_steps == 0:
                return ts_series
        return None

    def get_prev_time(self, ts, number_steps):
        for str_ts in sorted(self.series.keys(), reverse=True):
            ts_series = datetime.fromisoformat(str_ts)
            if ts_series < ts:
                number_steps -= 1
            if number_steps == 0:
                return ts_series
        return None

    def get_energy_range(self, start, end):
        start_time_point = self.get_next_time(start, 2)
        end_time_point = self.get_prev_time(end, 1)
        if start_time_point and end_time_point:
            return Interval(start_time_point, end_time_point)
        return None


    def get_thread_cpu_cycles(self, start, end):
        #Discards the first block and last block
        interval = self.get_energy_range(start, end)
        cpu_cycles = 0

        if interval:
            for str_ts in sorted(self.series.keys()):
                ts = datetime.fromisoformat(str_ts)
                if ts >= interval.start and ts <= interval.end:
                    cpu_cycles += self.series[str_ts].cpu_cycles

        return cpu_cycles






    def get_thread_energy(self, start, end):
        #Discards the first block and last block
        interval = self.get_energy_range(start, end)
        energy = 0
        if interval:
            for str_ts in sorted(self.series.keys()):
                ts = datetime.fromisoformat(str_ts)
                if ts >= interval.start and ts <= interval.end:
                    energy += self.series[str_ts].energy

        return energy


class ThreadTimeSeries:
    """Class that holds the time series for different thread ids"""

    def __init__(self, energy_file):
        self.total_energy = 0
        self.timeseries = {}
        self.hash_utils = HashUtils()
        self.parse_energy_file(energy_file)

    def init_tid(self, tid):
        if tid not in self.timeseries:
            self.timeseries[tid] = TimeSerie()

    def add_values(self, header, line, ts):
        tid_col_regex = r' Tid (\d+) Energy'
        line_energy = 0
        for i in range(1, len(header) -1):
            res_match = re.fullmatch(tid_col_regex, header[i])
            if res_match != None:
                tid = int(res_match.group(1))
                consumed = float(line[i])
                # HARDCODED! on the current logs the sys usage relative to the tid is always
                # after the tid energy values
                cpu = int(float(line[i + 1]) * int(line[1]) / 100)
                self.add_value(tid, ts, DataPoint(consumed, cpu))
                line_energy += consumed

        return line_energy

    def add_value(self, tid, ts, data_point):
        self.init_tid(tid)
        self.timeseries[tid].add_value(ts, data_point)

    def get_thread_energy(self, start, end, tid):
        self.init_tid(tid)
        return self.timeseries[tid].get_thread_energy(start, end)

    def get_thread_cpu_cycles(self, start, end, tid):
        self.init_tid(tid)
        return self.timeseries[tid].get_thread_cpu_cycles(start, end)

    def parse_energy_file(self, energy_file):
        fd = open(energy_file, "r")

        header = fd.readline()

        while header:
            line = fd.readline()
            splitted_header = header.split(';')
            splitted_line = line.split(';')
            ts_str = splitted_line[0]
            ts = datetime.fromisoformat(ts_str)
            self.total_energy += self.add_values(splitted_header, splitted_line, ts)

            # read header
            header = fd.readline()


        fd.close()


class Event:
    def __init__(self, tid, start_ts, end_ts, energy, cpu, event_type, context, job_id, file_num, inputs_size_info):
        self.tid = tid
        self.energy = energy
        self.cpu_cycles = cpu
        self.event_type = event_type
        self.context = context
        self.start_ts = start_ts
        self.end_ts = end_ts
        self.job_id = job_id
        self.file_num = file_num
        self.inputs_size_info = inputs_size_info

    @classmethod
    def from_event_json(cls, energy, cpu, event_json, event_size_info):
        tid = event_json["thread_id_system"]["start"]
        event_type = event_json["name"].split("#")[0]
        context = event_json["context"]
        start_ts = datetime.fromisoformat(event_json["date_time"]["start"])
        end_ts = datetime.fromisoformat(event_json["date_time"]["end"])
        if event_json["context"] != None and event_json["context"]["job_id"] != None:
            job_id = event_json["context"]["job_id"]
        else:
            job_id = -1

        if event_size_info != None and "quantity" in event_size_info.keys():
            if "quantity" in event_size_info.keys():
                file_num = event_size_info["quantity"]
            else:
                file_num = None
            if "inputs" in event_size_info.keys(): # Case where the log did not contain the end of some compactions
                inputs_size_info = event_size_info["inputs"]
            else:
                inputs_size_info = None
        else:
            file_num = None
            inputs_size_info = None

        return cls(tid, start_ts, end_ts, energy, cpu, event_type, context, job_id, file_num, inputs_size_info)

    def get_duration(self):
        return (self.end_ts - self.start_ts)/dt.timedelta(microseconds=1)

    def to_json(self):
        res = {}
        res["thread_id_system"] = self.tid
        res["energy"] = self.energy
        res["cpu_cycles"] = self.cpu_cycles
        res["event_type"] = self.event_type
        res["context"] = self.context
        res["start"] = str(self.start_ts)
        res["end"] = str(self.end_ts)
        res["job_id"] = self.job_id
        # Sometimes the parser logs the beggining of the compaction but not the summary
        if self.inputs_size_info != None:
            res["file_num"] = self.file_num
            res["inputs_size_info"] = self.inputs_size_info
        return res

class Report:
    def __init__(self, energy_file, events_json, events_size_info_json):
        self.tid_info = ThreadTimeSeries(energy_file)
        events_fd = open(events_json, "r")
        events_size_info_fd = open(events_size_info_json, "r")
        self.events_json = json.load(events_fd)
        self.events_size_info_json = json.load(events_size_info_fd)
        events_fd.close()
        self.events = self.parse_events_json()
        self.report = self.generate_json_report()

    def dump(self, output):
        fd = open(output, "a")
        json.dump(self.report, fd, indent=2)

        fd.close()

    def plot_compaction_level_energy_histogram(self, level, output):
        list_energy = [x.energy for x in self.events if x.context != None and x.event_type == "compaction" and x.context['level_info']['from'] == level]

        plt.clf()
        plt.hist(list_energy, bins=45, color='skyblue', edgecolor='black')

        plt.xlabel('Energy values for compaction from level:' + str(level) + " to:" + str(level + 1))
        plt.ylabel('Frequency')
        plt.title('Histrogram depicting energy values for compactions')
        plt.savefig(output)
    def plot_compaction_level_duration_histogram(self, level, output):
        list_duration = [x.get_duration()/1000000 for x in self.events if x.context != None and x.event_type == "compaction" and x.context['level_info']['from'] == level and x.get_duration() > 0]
        plt.clf()
        plt.hist(list_duration, bins=45, color='skyblue', edgecolor='black')

        plt.xlabel('Duration values for compaction from level:' + str(level) + " to:" + str(level + 1))
        plt.ylabel('Frequency')
        plt.title('Histrogram depicting duration values for compactions')
        plt.savefig(output)


    def get_event_size_info(self, job_id):
        if str(job_id) in self.events_size_info_json.keys():
            return self.events_size_info_json[str(job_id)]
        return None

    def parse_events_json(self):
        sub_events = self.events_json["open_event"]["sub_events"]
        events = []
        for event in sub_events:
            energy = self.get_event_json_energy(event)
            cpu = self.get_event_json_cpu(event)
            if event["context"] != None and "job_id" in event["context"].keys():
                event_size_info = self.get_event_size_info(event["context"]["job_id"])
                events.append(Event.from_event_json(energy, cpu, event, event_size_info))
            else: #Case when flush did not have job_id
                events.append(Event.from_event_json(energy, cpu, event, None))


        return events

    def get_event_json_cpu(self, event_json):
        tid = event_json["thread_id_system"]["start"]
        start = datetime.fromisoformat(event_json["date_time"]["start"])
        end = datetime.fromisoformat(event_json["date_time"]["end"])
        return self.tid_info.get_thread_cpu_cycles(start, end, tid)

    def get_event_json_energy(self, event_json):
        tid = event_json["thread_id_system"]["start"]
        start = datetime.fromisoformat(event_json["date_time"]["start"])
        end = datetime.fromisoformat(event_json["date_time"]["end"])
        return self.tid_info.get_thread_energy(start, end, tid)


    def init_compaction_level_info(self, level, report):
        if level not in report["compaction_info"]["levels_energy"]:
            report["compaction_info"]["levels_energy"][level] = 0
            report["compaction_info"]["levels_num"][level] = 0
            report["compaction_info"]["levels_avg_power"][level] = 0
            report["compaction_info"]["events"][level] = []
            report["duration_info"]["levels_duration"][level] = 0
            report["duration_info"]["levels_avg_duration"][level] = 0

    def add_compaction_info_to_report(self, report, event):
        level = str((event.context["level_info"]["from"], event.context["level_info"]["to"]))
        self.init_compaction_level_info(level, report)
        report["compaction_info"]["total_energy"] += event.energy
        report["compaction_info"]["levels_energy"][level] += event.energy
        report["compaction_info"]["levels_num"][level] += 1
        report["compaction_info"]["events"][level].append(event.to_json())
        report["duration_info"]["levels_duration"][level] += event.get_duration()

    def init_trivial_level_info(self, level, report):
        if level not in report["trivial_info"]["levels_num"]:
            report["trivial_info"]["levels_num"][level] = 0

    def add_trivial_info_to_report(self, report, event):
        level = str((event.context["level_info"]["from"], event.context["level_info"]["to"]))
        self.init_trivial_level_info(level, report)
        report["trivial_info"]["levels_num"][level] += 1

    def init_thread_info(self, tid, event_type, report):
        if tid not in report["thread_info"]:
            report["thread_info"][tid] = {}

        if event_type not in report["thread_info"][tid]:
            report["thread_info"][tid][event_type] = {
                "total_energy": 0,
                "num": 0,
                "duration": 0
            }

    def add_thread_info(self, report, event):
        self.init_thread_info(event.tid, event.event_type, report)
        report["thread_info"][event.tid][event.event_type]["total_energy"] += event.energy
        report["thread_info"][event.tid][event.event_type]["num"] += 1
        report["thread_info"][event.tid][event.event_type]["duration"] += event.get_duration()

    def add_flush_info_to_report(self, report, event):
        report["flush_info"]["total_energy"] += event.energy
        report["flush_info"]["num"] += 1

    def add_event_to_report(self, event, report):
        event_json = event.to_json()
        report["events"].append(event_json)


        if event.event_type == "trivial":
            self.add_trivial_info_to_report(report, event)
        elif event.event_type == "compaction":
            self.add_compaction_info_to_report(report, event)
        elif event.event_type == "flush":
            self.add_flush_info_to_report(report, event)
        self.add_thread_info(report, event)


    def create_averages(self, report):
        if report["flush_info"]["num"] != 0:
            avg = report["flush_info"]["total_energy"] / report["flush_info"]["num"]
            report["flush_info"]["avg"] = round(avg, 4)

        for level in report["compaction_info"]["levels_energy"].keys():
            avg = report["compaction_info"]["levels_energy"][level] / report["compaction_info"]["levels_num"][level]
            report["compaction_info"]["avg_per_compaction"][level] = round(avg, 4)

            report["duration_info"]["levels_duration"][level] = report["duration_info"]["levels_duration"][level]/ 1000000
            avg_duration = report["duration_info"]["levels_duration"][level] / report["compaction_info"]["levels_num"][level]
            report["duration_info"]["levels_avg_duration"][level] = round(avg_duration, 4)

            avg_power = report["compaction_info"]["levels_energy"][level] / report["duration_info"]["levels_duration"][level]
            report["compaction_info"]["levels_avg_power"][level] = avg_power

            event_energy_level = [x["energy"] for x in report["compaction_info"]["events"][level]]
            median_energy = statistics.median(event_energy_level)
            report["compaction_info"]["levels_median_energy"][level] = median_energy

            event_cpu_cycles_level = [x["cpu_cycles"] for x in report["compaction_info"]["events"][level]]
            mean_cpu_cycles = statistics.mean(event_cpu_cycles_level)
            report["compaction_info"]["avg_cycles"][level] = round(mean_cpu_cycles, 4)


    def init_report(self):
        report = {}
        report["events"] = []
        report["total_energy"] = self.tid_info.total_energy
        report["compaction_info"] = {
            "total_energy": 0,
            "levels_energy": {},
            "levels_num": {},
            "avg_per_compaction": {},
            "avg_cycles": {},
            "levels_median_energy": {},
            "levels_avg_power" : {},
            "events": {}
        }
        report["flush_info"] = {
            "total_energy": 0,
            "num": 0
        }
        report["trivial_info"] = {
            "levels_num": {}
        }
        report["duration_info"] = {
            "levels_duration" : {},
            "levels_avg_duration" : {}
        }
        report["thread_info"] = {}

        return report

    def generate_json_report(self):
        report = self.init_report()

        for event in self.events:
            self.add_event_to_report(event, report)

        self.create_averages(report)

        return report

    def plot(self, output):
        compaction_info = self.report["compaction_info"]
        flush_info = self.report["flush_info"]
        total_energy = self.report["total_energy"]

        compactions_levels = list(compaction_info["levels_energy"].keys())
        compaction_energy = list(compaction_info["levels_energy"].values())

        total_compaction_energy = sum(compaction_energy)

        percentages_compaction = [(energy / total_compaction_energy) * 100 for energy in compaction_energy]

        x_labels_compactions = []
        for level in sorted(compactions_levels):
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
        axs[0].set_title('Histogram of Levels (Percentage of Total Energy)')

        # Plotting the second histogram with the misc bar
        bars2 = axs[1].bar(events, percentages_events, color='lightcoral', edgecolor='black')
        axs[1].set_xlabel('Events')
        axs[1].set_ylabel('Percentage (%)')
        axs[1].set_title('Histogram of Events (Percentage of Total Energy)')

        # Ensure bars are in front of grid lines
        for bars in [bars1, bars2]:
            for bar in bars:
                bar.set_zorder(10)


        fig.tight_layout()
        fig.savefig(output)
