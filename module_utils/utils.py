#!/usr/bin/env python3

from collections import namedtuple
from datetime import datetime
import datetime as dt
import re
from typing import Type
import matplotlib.pyplot as plt
import json
import sys

Interval = namedtuple("Interval", ["start", "end"])

class TimeSerie:
    def __init__(self):
        self.series = {}
        self.total_energy = 0

    def add_value(self, ts, energy):
        self.series[str(ts)] = energy
        self.total_energy += energy

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


    def get_thread_energy(self, start, end):
        #Discards the first block and last block
        interval = self.get_energy_range(start, end)
        energy = 0
        if interval:
            for str_ts in sorted(self.series.keys()):
                ts = datetime.fromisoformat(str_ts)
                if ts >= interval.start and ts <= interval.end:
                    energy += self.series[str_ts]

        return energy


class ThreadTimeSeries:
    """Class that holds the time series for different thread ids"""

    def __init__(self, energy_file):
        self.total_energy = 0
        self.timeseries = {}
        self.parse_energy_file(energy_file)

    def init_tid(self, tid):
        if tid not in self.timeseries:
            self.timeseries[tid] = TimeSerie()

    def add_energy_values(self, header, line, ts):
        tid_col_regex = r' Tid (\d+) Energy'
        line_energy = 0
        for i in range(1, len(header) -1):
            res_match = re.fullmatch(tid_col_regex, header[i])
            if res_match != None:
                tid = int(res_match.group(1))
                consumed = float(line[i])
                self.add_value(tid, ts, consumed)
                line_energy += consumed

        return line_energy

    def add_value(self, tid, ts, energy):
        self.init_tid(tid)
        self.timeseries[tid].add_value(ts, energy)

    def get_thread_energy(self, start, end, tid):
        self.init_tid(tid)
        return self.timeseries[tid].get_thread_energy(start, end)

    def parse_energy_file(self, energy_file):
        fd = open(energy_file, "r")

        header = fd.readline()

        while header:
            line = fd.readline()
            splitted_header = header.split(';')
            splitted_line = line.split(';')
            ts_str = splitted_line[0]
            ts = datetime.fromisoformat(ts_str)
            self.total_energy += self.add_energy_values(splitted_header, splitted_line, ts)

            # read header
            header = fd.readline()


        fd.close()


class Event:
    def __init__(self, tid, start_ts, end_ts, energy, event_type, context):
        self.tid = tid
        self.energy = energy
        self.event_type = event_type
        self.context = context
        self.start_ts = start_ts
        self.end_ts = end_ts

    @classmethod
    def from_event_json(cls, energy, event_json):
        tid = event_json["thread_id_system"]["start"]
        event_type = event_json["name"].split("#")[0]
        context = event_json["context"]
        start_ts = datetime.fromisoformat(event_json["date_time"]["start"])
        end_ts = datetime.fromisoformat(event_json["date_time"]["end"])
        return cls(tid, start_ts, end_ts, energy, event_type, context)

    def get_duration(self):
        return (self.end_ts - self.start_ts)/dt.timedelta(microseconds=1)

    def to_json(self):
        res = {}
        res["thread_id_system"] = self.tid
        res["energy"] = self.energy
        res["event_type"] = self.event_type
        res["context"] = self.context
        res["start"] = str(self.start_ts)
        res["end"] = str(self.end_ts)
        return res


class Report:
    def __init__(self, energy_file, events_json):
        self.tid_info = ThreadTimeSeries(dt.timedelta(milliseconds=100), energy_file)
        events_fd = open(events_json, "r")
        self.events_json = json.load(events_fd)
        events_fd.close()
        self.events = self.parse_events_json()
        self.report = self.generate_json_report()

    def dump(self, output):
        fd = open(output, "a")
        json.dump(self.report, fd, indent=2)

        fd.close()

    def parse_events_json(self):
        sub_events = self.events_json["open_event"]["sub_events"]
        events = []
        for event in sub_events:
            energy = self.get_event_json_energy(event)
            events.append(Event.from_event_json(energy, event))
        return events

    def get_event_json_energy(self, event_json):
        tid = event_json["thread_id_system"]["start"]
        start = datetime.fromisoformat(event_json["date_time"]["start"])
        end = datetime.fromisoformat(event_json["date_time"]["end"])
        return self.tid_info.get_thread_energy(start, end, tid)


    def add_event_to_report(self, event, report):
        event_json = event.to_json()
        report["events"].append(event_json)
        tid = event.tid


        if event.tid not in report["thread_info"]:
            report["thread_info"][event.tid] = {}

        if event.event_type == "trivial":
            if event.context != None:
                level = str((event.context["level_info"]["from"], event.context["level_info"]["to"]))
                if level not in report["trivial_info"]["levels_num"]:
                    report["trivial_info"]["levels_num"][level] = 0

                report["trivial_info"]["levels_num"][level] += 1
        elif event.event_type == "compaction":
            report["compaction_info"]["total_energy"] += event.energy
            level = str((event.context["level_info"]["from"], event.context["level_info"]["to"]))
            if level not in report["compaction_info"]["levels_energy"]:
                report["compaction_info"]["levels_energy"][level] = 0
                report["compaction_info"]["levels_num"][level] = 0
                report["compaction_info"]["levels_avg_power"][level] = 0
                report["duration_info"]["levels_duration"][level] = 0
                report["duration_info"]["levels_avg_duration"][level] = 0
            report["compaction_info"]["levels_energy"][level] += event.energy
            report["compaction_info"]["levels_num"][level] += 1
            report["duration_info"]["levels_duration"][level] += event.get_duration()
            if "compaction" not in report["thread_info"][tid]:
                report["thread_info"][tid]["compaction"] = {
                    "total_energy" : 0,
                    "num": 0,
                    "duration" : 0
                }

            report["thread_info"][tid]["compaction"]["total_energy"] += event.energy
            report["thread_info"][tid]["compaction"]["num"] += 1
            report["thread_info"][tid]["compaction"]["duration"] += event.get_duration()
        elif event.event_type == "flush":
            report["flush_info"]["total_energy"] += event.energy
            report["flush_info"]["num"] += 1

            if "flush" not in report["thread_info"][tid]:
                report["thread_info"][tid]["flush"] = {
                    "total_energy" : 0,
                    "num" : 0,
                    "duration": 0
                }

            report["thread_info"][tid]["flush"]["total_energy"] += event.energy
            report["thread_info"][tid]["flush"]["num"] += 1
            report["thread_info"][tid]["flush"]["duration"] += event.get_duration()




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




    def generate_json_report(self):
        report = {}
        report["events"] = []
        report["total_energy"] = self.tid_info.total_energy
        report["compaction_info"] = {
            "total_energy": 0,
            "levels_energy": {},
            "levels_num": {},
            "avg_per_compaction": {},
            "levels_avg_power" : {}
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
