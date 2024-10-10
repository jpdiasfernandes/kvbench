#!/usr/bin/env python3

from collections import namedtuple
from datetime import datetime
import datetime as dt
import re
import matplotlib.pyplot as plt
import json
import statistics

from pandas.core import series


Interval = namedtuple("Interval", ["start", "end"])

#class HashUtils:
#    def micro_from_dt(self, ts):
#        minutes = (ts.hour * 60) + ts.minute
#        seconds = (minutes * 60) + ts.second
#        micro = (seconds * 1000 * 1000) + ts.microsecond
#        return micro
#
#    def micro_from_td(self, td):
#        seconds = (td.days * 24 * 3600) + td.seconds
#        micro = (seconds * 1000 * 1000) + td.microseconds
#        return micro
#
#    def round_or_trunc(self, ts, micro):
#        micro_ts = self.micro_from_dt(ts)
#        if (micro_ts%(micro)) >= (micro/2):
#            return "round"
#        else:
#            return "trunc"
#
#    def round_micro(self, ts, micro):
#        micro_ts = self.micro_from_dt(ts)
#        if (micro_ts%(micro)) >= (micro/2):
#            ts += dt.timedelta(microseconds= micro)
#        ts -= dt.timedelta(microseconds=(micro_ts%micro))
#        return ts
#
#    def hash_time(self, ts, timedelta):
#        if timedelta.days == 0:
#            return self.round_micro(ts, self.micro_from_td(timedelta))
#        return ts

class DataPoint:
    def __init__(self, energy, cpu_cycles):
        self.energy = energy
        self.cpu_cycles = cpu_cycles

    def to_json(self):
        res = {
            "energy" : self.energy,
            "cpu_cycles" : self.cpu_cycles
        }
        return res


class TimeSerie:
    def __init__(self):
        self.series = {}
        self.total_energy = 0

    def to_json(self):
        res = {}
        for str_ts in sorted(self.series.keys()):
            res[str_ts] = self.series[str_ts].to_json()
        return res

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
        self.parse_energy_file(energy_file)

    def to_json(self):
        res = {}
        for tid, time_series in self.timeseries.items():
            res[str(tid)] = time_series.to_json()
        return res

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
    def __init__(self, tid, start_ts, end_ts, energy, cpu, event_type, context, job_id):
        self.tid = tid
        self.energy = energy
        self.cpu_cycles = cpu
        self.event_type = event_type
        self.context = context
        self.start_ts = start_ts
        self.end_ts = end_ts
        self.job_id = job_id

    @classmethod
    def from_event_json(cls, energy, cpu, event_json):
        tid = event_json["thread_id_system"]["start"]
        event_type = event_json["name"].split("#")[0]
        context = event_json["context"]
        start_ts = datetime.fromisoformat(event_json["date_time"]["start"])
        end_ts = datetime.fromisoformat(event_json["date_time"]["end"])
        job_id = event_json["context"]["job_id"]

        return cls(tid, start_ts, end_ts, energy, cpu, event_type, context, job_id)

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
        return res

class EventCompaction(Event):
    def __init__(self, tid, start_ts, end_ts, energy, cpu, event_type, context, job_id, file_num, inputs_size_info):
        super().__init__(tid, start_ts, end_ts, energy, cpu, event_type, context, job_id)
        self.file_num = file_num
        self.inputs_size_info = inputs_size_info
    @classmethod
    def from_event_json(cls, energy, cpu, event_json):
        base = Event.from_event_json(energy, cpu, event_json)
        file_num = event_json["context"]["quantity"]
        inputs_size_info = event_json["context"]["input"]
        return cls(base.tid, base.start_ts, base.end_ts, base.energy, base.cpu_cycles, base.event_type, base.context, base.job_id, file_num, inputs_size_info)

    def to_json(self):
        res = super().to_json()
        res["file_num"] = self.file_num
        res["inputs_size_info"] = self.inputs_size_info
        return res

class EventFlush(Event):
    def __init__(self, tid, start_ts, end_ts, energy, cpu, event_type, context, job_id, num_memtables, total_size):
        super().__init__(tid, start_ts, end_ts, energy, cpu, event_type, context, job_id)
        self.num_memtables = num_memtables
        self.total_size = total_size

    @classmethod
    def from_event_json(cls, energy, cpu, event_json):
        base = Event.from_event_json(energy, cpu, event_json)
        num_memtables = event_json["context"]["num_memtables"]
        total_size = event_json["context"]["total_data_size"]
        return cls(base.tid, base.start_ts, base.end_ts, base.energy, base.cpu_cycles, base.event_type, base.context, base.job_id, num_memtables, total_size)

    def to_json(self):
        res = super().to_json()
        res["num_memtables"] = self.num_memtables
        res["total_size"] = self.total_size
        return res

class Report:
    def __init__(self, energy_file, events_json):
        self.tid_info = ThreadTimeSeries(energy_file)
        events_fd = open(events_json, "r")
        self.events_json = json.load(events_fd)
        events_fd.close()
        self.events = self.parse_events_json()

    def parse_events_json(self):
        sub_events = self.events_json["open_event"]["sub_events"]
        events = []
        for event in sub_events:
            energy = self.get_event_json_energy(event)
            cpu = self.get_event_json_cpu(event)
            event_type = event["name"].split("#")[0]
            if event_type == "flush":
                events.append(EventFlush.from_event_json(energy, cpu, event))
            elif event_type == "compaction":
                events.append(EventCompaction.from_event_json(energy, cpu, event))
            elif event_type == "trivial":
                events.append(Event.from_event_json(energy, cpu, event))

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

    def to_json(self):
        res = {
            "events" : [],
            "thread_info" : self.tid_info.to_json()
        }

        for event in self.events:
            res["events"].append(event.to_json())

        return res

    def dump_json(self, output):
        fd = open(output, "a")
        json.dump(self.to_json(), fd)
        fd.close()
