#!/usr/bin/env python3
import json
from datetime import datetime
import datetime as dt
import re
from collections import namedtuple
import numpy as np
from matplotlib.axes import Axes
from functools import reduce

from ansible.module_utils.plot_utils import Plot
#from plot_utils import Plot
Interval = namedtuple("Interval", ["start", "end"])

def get_duration(date_time: dt.datetime, first_date_time: dt.datetime):
    return (date_time - first_date_time).total_seconds()


class Report:
    def __init__(self, thread_time_series, events):
        self.tid_info = thread_time_series
        self.events = events

    @classmethod
    def from_files(cls, energy_file, event_file):
        report = cls(ThreadTimeSeries.from_energy_file(energy_file), [])
        event_fd = open(event_file, "r")
        events_json = json.load(event_fd)
        report.parse_events_json(events_json)
        return report

    @classmethod
    def load_json(cls, json_file):
        json_fd = open(json_file, "r")
        json_dict: dict = json.load(json_fd)
        return cls.from_json(json_dict)

    @classmethod
    def from_json(cls, json_dict):
        events = []
        thread_time_serie = ThreadTimeSeries.from_json(json_dict["thread_info"])
        for event_json_dict in json_dict["events"]:
            events.append(Event.from_json(event_json_dict))
        return cls(thread_time_serie, events)

    def parse_events_json(self, events_json):
        sub_events = events_json["open_event"]["sub_events"]
        self.events = []
        for event in sub_events:
            energy = self.get_event_json_energy(event)
            cpu = self.get_event_json_cpu(event)
            event_type = event["name"].split("#")[0]
            if event_type == "flush":
                self.events.append(EventFlush.from_event_json(energy, cpu, event))
            elif event_type == "compaction":
                self.events.append(EventCompaction.from_event_json(energy, cpu, event))
            elif event_type == "trivial":
                self.events.append(Event.from_event_json(energy, cpu, event))

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

    def group_compactions_by_level(self):
        levels = {}
        event: Event
        for event in self.events:
            if event.event_type == "compaction":
                to_level = event.context["level_info"]["to"]
                if to_level not in levels:
                    levels[to_level] = []
                levels[to_level].append(event)

        return levels

class DataPoint:
    def __init__(self, energy, cpu_cycles):
        self.energy = energy
        self.cpu_cycles = cpu_cycles

    @classmethod
    def from_json(cls, json_dict):
        return cls(json_dict["energy"], json_dict["cpu_cycles"])

    def to_json(self):
        res = {
            "energy" : self.energy,
            "cpu_cycles" : self.cpu_cycles
        }
        return res


class TimeSerie:
    def __init__(self, series, total_energy):
        self.series = series
        self.total_energy = total_energy

    @classmethod
    def default_constructor(cls):
        return cls({}, 0)

    @classmethod
    def from_json(cls, json_dict):
        time_serie = TimeSerie.default_constructor()
        for str_ts, json_data_point in json_dict.items():
            data_point = DataPoint.from_json(json_data_point)
            time_serie.series[str_ts] = data_point
            time_serie.total_energy += data_point.energy
        return time_serie

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

    def get_first_ts(self):
        str_ts = sorted(self.series.keys())[0]
        return datetime.fromisoformat(str_ts)
    def get_last_ts(self):
        str_ts = sorted(self.series.keys())[-1]
        return datetime.fromisoformat(str_ts)

class ThreadTimeSeries:
    """Class that holds the time series for different thread ids"""

    def __init__(self, total_energy, timeseries):
        self.total_energy = total_energy
        self.timeseries = timeseries

    @classmethod
    def from_energy_file(cls, energy_file):
        thread_time_series = ThreadTimeSeries.default_constructor()
        thread_time_series.parse_energy_file(energy_file)
        return thread_time_series

    @classmethod
    def default_constructor(cls):
        return cls(0, {})
    @classmethod
    def from_json(cls, json_dict):
        thread_time_series = ThreadTimeSeries.default_constructor()
        for tid_str, time_serie_json in json_dict.items():
            time_serie: TimeSerie = TimeSerie.from_json(time_serie_json)
            thread_time_series.timeseries[int(tid_str)] = time_serie
            thread_time_series.total_energy += time_serie.total_energy

        return thread_time_series

    def to_json(self):
        res = {}
        for tid, time_series in self.timeseries.items():
            res[str(tid)] = time_series.to_json()
        return res

    def init_tid(self, tid):
        if tid not in self.timeseries:
            self.timeseries[tid] = TimeSerie.default_constructor()

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
    def get_first_ts(self, tid):
        if tid in self.timeseries.keys():
            time_serie :TimeSerie = self.timeseries[tid]
            return time_serie.get_first_ts()
        return None

    def get_last_ts(self, tid):
        if tid in self.timeseries.keys():
            time_serie: TimeSerie = self.timeseries[tid]
            return time_serie.get_last_ts()
        return None


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
    def from_json(cls, json_dict):
        event_type = json_dict["event_type"]
        if event_type == "compaction":
            return EventCompaction(json_dict["thread_id_system"],
                                   datetime.fromisoformat(json_dict["start"]),
                                   datetime.fromisoformat(json_dict["end"]),
                                   json_dict["energy"],
                                   json_dict["cpu_cycles"],
                                   json_dict["event_type"],
                                   json_dict["context"],
                                   json_dict["job_id"],
                                   json_dict["file_num"],
                                   json_dict["inputs_size_info"])
        elif event_type == "flush":
            return EventFlush(json_dict["thread_id_system"],
                              datetime.fromisoformat(json_dict["start"]),
                              datetime.fromisoformat(json_dict["end"]),
                              json_dict["energy"],
                              json_dict["cpu_cycles"],
                              json_dict["event_type"],
                              json_dict["context"],
                              json_dict["job_id"],
                              json_dict["num_memtables"],
                              json_dict["total_size"]
                              )
        else:
            return Event(json_dict["thread_id_system"],
                  datetime.fromisoformat(json_dict["start"]),
                  datetime.fromisoformat(json_dict["end"]),
                  json_dict["energy"],
                  json_dict["cpu_cycles"],
                  json_dict["event_type"],
                  json_dict["context"],
                  json_dict["job_id"])

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

class ReportPlotter:
    def __find_event_threads(self, report: Report):
        compaction_tids = set()
        flush_tids = set()
        event: Event
        for event in report.events:
            if event.event_type == "compaction":
                compaction_tids.add(event.tid)
            elif event.event_type == "flush":
                flush_tids.add(event.tid)
        return compaction_tids, flush_tids

    def __get_tids(self, tid_info: ThreadTimeSeries):
        tids_set = set()
        for tid, _ in tid_info.timeseries.items():
            tids_set.add(tid)

        return tids_set

    def __init__(self, report: Report, power_min_ylim = 0, power_max_ylim = 200, acc_energy_max_ylim = 40000, acc_energy_min_ylim = 0):
        self.report = report
        self.compaction_tids, self.flush_tids = self.__find_event_threads(report)
        self.tids = self.__get_tids(report.tid_info)
        self.foreground_tids = self.tids - (self.compaction_tids | self.flush_tids)
        self.power_min_ylim = power_min_ylim
        self.power_max_ylim = power_max_ylim
        self.acc_energy_max_ylim = acc_energy_max_ylim
        self.acc_energy_min_ylim = acc_energy_min_ylim
        self.cache_group_by_level = None

    def __hash_datetime(self, datetime: dt.datetime):
        res_time = datetime.replace(microsecond=0)
        return res_time

    def __generic_power_xy(self, set_tid):
        timeseries = {}
        def __add_timeserie(datetime: dt.datetime, value):
            if datetime not in timeseries.keys():
                timeseries[datetime] = 0
            timeseries[datetime] += value
        timeserie: TimeSerie
        for tid in set_tid:
            timeserie: TimeSerie = self.report.tid_info.timeseries[tid]
            data_point: DataPoint
            for time_str, data_point in timeserie.series.items():
                hashed_ts = self.__hash_datetime(datetime.fromisoformat(time_str))
                __add_timeserie(hashed_ts, data_point.energy)

        duration = []
        energy = []


        timeseries_list = list(timeseries.keys())
        if len(timeseries_list) > 0:
            first_ts = timeseries_list[0]
            for ts, acc_energy in timeseries.items():
                duration.append(get_duration(ts, first_ts))
                energy.append(acc_energy)

        return duration, energy

    def __group_by_level(self):
        if self.cache_group_by_level == None:
            self.cache_group_by_level = self.report.group_compactions_by_level()
        return self.cache_group_by_level

    def __generic_power_plot(self, set_tid):
        duration, energy = self.__generic_power_xy(set_tid)
        res_plot = Plot()
        res_plot.plot_line(duration, energy)
        res_plot.set_labels("Seconds (s)", "Average power (W)")
        res_plot.set_ylim(self.power_min_ylim, self.power_max_ylim)
        return res_plot

    def foreground_energy(self, out_name):
        "Plots the accumulated energy of foreground threads"
        "The y value corresponds to the accumulated energy between the [x, x + 1[ seconds"
        plot = self.__generic_power_plot(self.foreground_tids)
        plot.set_title("Foreground threads average power between [x, x+1[ seconds")
        plot.save_fig(out_name)

    def compaction_energy(self, out_name):
        plot = self.__generic_power_plot(self.compaction_tids)
        plot.set_title("Compaction threads average power between [x, x+1[ seconds")
        plot.save_fig(out_name)

    def flush_energy(self, out_name):
        plot = self.__generic_power_plot(self.flush_tids)
        plot.set_title("Flush threads average power between [x, x+1[ seconds")
        plot.save_fig(out_name)

    def thread_energy(self, tid, out_name):
        tid_set = set([tid])
        plot = self.__generic_power_plot(tid_set)
        plot.set_title("Thread " + str(tid) + " average power between [x, x+1[ seconds")
        plot.save_fig(out_name)


    def compaction_events_energy(self, out_name, width=6.4, height=4.8):
        no_compaction_tids = len(self.compaction_tids)
        plot = Plot(no_compaction_tids, 1)

        compaction_info = {}
        available_levels_tids = {}
        level_timelines_tids = {}

        def __add_level_to_tid(tid, level):
            if tid not in available_levels_tids.keys():
                available_levels_tids[tid] = set()
            available_levels_tids[tid].add(level)

        def __add_timeline_to_tid(tid, timeline_id, level):
            if tid not in level_timelines_tids.keys():
                level_timelines_tids[tid] = {}
            level_timelines_tids[tid][level] = timeline_id


        event: Event
        for event in self.report.events:
            if event.event_type == "compaction":
                to = event.context["level_info"]["to"]
                job_id = event.job_id
                tid = event.tid
                __add_level_to_tid(tid, to)
                compaction_info[job_id] = event

        tid_row = {}
        for i, tid in enumerate(self.compaction_tids):
            duration, energy = self.__generic_power_xy(set({tid}))
            plot.plot_line(duration, energy, row=i)
            tid_row[tid] = i
            plot.set_ylim(self.power_min_ylim, self.power_max_ylim, row=i)
            tid_info = self.report.tid_info
            total_duration = int((tid_info.get_last_ts(tid) - tid_info.get_first_ts(tid)).total_seconds()) + 2
            plot.set_xlim(0,total_duration, row=i)

        for tid, available_levels in available_levels_tids.items():
            first_ts = self.report.tid_info.get_first_ts(tid)
            row = tid_row[tid]
            for level in sorted(available_levels):
                level_str = "Level " + str(level)
                timeline_id = plot.push_timeline(first_ts, level_str, '--', 'black', 1.5, 15, 1, row=row)
                __add_timeline_to_tid(tid, timeline_id, level)

        for job_id, event in compaction_info.items():
            row = tid_row[event.tid]
            to = event.context["level_info"]["to"]
            timeline_id = level_timelines_tids[event.tid][to]
            start_ts = event.start_ts
            end_ts = event.end_ts
            plot.add_event_to_timeline(timeline_id, start_ts, end_ts, row=row, hatch='///')
            plot.add_timeline_legend('///', 'Compaction', 'none', row=row)
            plot.set_title('Thread ' + str(event.tid) + ' energy and events', row=row)
        for row in tid_row.values():
            plot.plot_timeline_stack(row=row)
            #axis: Axes = plot.get_axis(row)
            #min_x, max_x = axis.get_xlim()
            #distance = abs(max_x - min_x)
            #major_ticks = np.arange(0, distance, 10)
            #axis.set_xticks(major_ticks)
            #axis.grid(axis='x')

        plot.fig.set_figheight(height)
        plot.fig.set_figwidth(width)
        plot.save_fig(out_name)

    def __generate_total_compaction_energy(self, plot: Plot, row=0, col=0):
        grouped_by_level = self.__group_by_level()
        compaction_level_energy = {level: reduce(lambda acc_energy, event: acc_energy + event.energy, list_events, 0) for level, list_events in grouped_by_level.items()}
        x = []
        height = []
        for level, energy in sorted(compaction_level_energy.items()):
            x.append(str(level))
            height.append(energy)

        plot.plot_bar(x,  height, hatch='///', bar_colors='none', row=row, col=col)
        plot.set_ylim(self.acc_energy_min_ylim, self.acc_energy_max_ylim, row, col)
        plot.set_labels("Compactions to output level", "Total Consumed Energy (J)", row, col)

    def __generate_total_compaction_number(self, plot, row=0, col=0):
        grouped_by_level = self.__group_by_level()
        compaction_level_number = {}
        for level, list_events in grouped_by_level.items():
            compaction_level_number[level] = len(list_events)

        x = []
        height = []
        for level, compactions in sorted(compaction_level_number.items()):
            x.append(str(level))
            height.append(height)

        plot.plot_bar(x, height, hatch='OO', bar_colors='none', row=row, col=col)
        plot.set_labels("Compactions to output level", "Total Number of Compactions", row, col)

    def __generate_total_compaction_duration(self, plot: Plot, row=0, col=0):
        grouped_by_level = self.__group_by_level()
        compaction_level_duration = {}
        for level, list_events in grouped_by_level.items():
            acc_duration = 0
            for event in list_events:
                acc_duration += (event.end_ts - event.start_ts).total_seconds()
            compaction_level_duration[level] = acc_duration

        x = []
        height = []
        for level, duration in sorted(compaction_level_duration.items()):
            x.append(str(level))
            height.append(duration)


        plot.plot_bar(x, height, hatch='**', bar_colors='none', row=row, col=col)
        plot.set_ylim(0, 720 * 4, row, col)
        plot.set_labels("Compactions to output level", "Total Duration Elapsed (seconds)", row, col)

    def __generate_total_compaction_size(self, plot: Plot, row=0, col=0):
        def get_size_from_inputs(input):
            acc_size = 0
            for input_level in input:
                for _, size_bytes in input_level.items():
                    acc_size += size_bytes
            return acc_size

        grouped_by_level = self.__group_by_level()
        compaction_level_size = {}
        for level, list_events in grouped_by_level.items():
            acc_size = 0
            for event in list_events:
                acc_size += get_size_from_inputs(event.context["input"])
            compaction_level_size[level] = acc_size

        x = []
        height = []
        for level, size in sorted(compaction_level_size.items()):
            x.append(str(level))
            size_gb = size / 1024 / 1024 / 1024
            height.append(size_gb)

        plot.plot_bar(x, height, hatch='++', bar_colors='none', row=row, col=col)
        plot.set_ylim(0, 150, row, col)
        plot.set_labels("Compactions to output level", "Total Accumulated File Size Compacted (GiB)", row, col)

    def __generate_avg_compaction_size(self, plot: Plot, row=0, col=0):
        def get_size_from_inputs(input):
            acc_size = 0
            for input_level in input:
                for _, size_bytes in input_level.items():
                    acc_size += size_bytes
            return acc_size

        grouped_by_level = self.__group_by_level()
        compaction_level_size = {}
        for level, list_events in grouped_by_level.items():
            acc_size = 0
            acc_number = 0
            for event in list_events:
                acc_number += 1
                acc_size += get_size_from_inputs(event.context["input"])
            compaction_level_size[level] = acc_size / acc_number

        x = []
        height = []
        for level, size in sorted(compaction_level_size.items()):
            x.append(str(level))
            size_gb = size / 1024 / 1024 / 1024
            height.append(size_gb)

        plot.plot_bar(x, height, hatch='++', bar_colors='none', row=row, col=col)
        plot.set_ylim(0, 2, row, col)
        plot.set_labels("Compactions to output level", "Average Accumulated File Size Compacted (GiB)", row, col)

    def __generate_avg_compaction_files(self, plot, row=0, col=0):
        def get_files_from_inputs(input):
            no_inputs = 0
            for input_level in input:
                list_fd = list(input_level.keys())
                no_inputs += len(list_fd)
            return no_inputs
        grouped_by_level = self.__group_by_level()
        compaction_level_files = {}
        for level, list_events in grouped_by_level.items():
            acc_files = 0
            acc_number = 0
            for event in list_events:
                acc_number += 1
                acc_files += get_files_from_inputs(event.context["input"])
            compaction_level_files[level] = acc_files / acc_number
        x = []
        height = []
        for level, files in sorted(compaction_level_files.items()):
            x.append(str(level))
            height.append(files)

        plot.plot_bar(x, height, hatch='\\', bar_colors='none', row=row, col=col)
        plot.set_ylim(0,10)
        plot.set_labels("Compactions to output level", "Average Files Involved", row, col)

    def __generate_avg_compaction_power(self, plot: Plot, row=0, col=0):
        grouped_by_level = self.__group_by_level()
        compaction_level_power = {}
        for level, list_events in grouped_by_level.items():
            acc_duration = 0
            acc_energy = 0
            for event in list_events:
                acc_duration += (event.end_ts - event.start_ts).total_seconds()
                acc_energy += event.energy
            compaction_level_power[level] = acc_energy / acc_duration

        x = []
        height = []
        for level, power in sorted(compaction_level_power.items()):
            x.append(str(level))
            height.append(power)


        plot.plot_bar(x, height, hatch='oo', bar_colors='none', row=row, col=col)
        plot.set_ylim(0, 70, row, col)
        plot.set_labels("Compactions to output level", "Compaction Power", row, col)


    def __generate_cpu_busy_frequency(self, plot: Plot, row=0, col=0):
        grouped_by_level = self.__group_by_level()
        compaction_level_usage = {}
        for level, list_events in grouped_by_level.items():
            acc_cycles = 0
            acc_duration = 0
            for event in list_events:
                acc_duration += (event.end_ts - event.start_ts).total_seconds()
                acc_cycles += event.cpu_cycles
            compaction_level_usage[level] = acc_cycles / acc_duration

        x = []
        height = []
        for level, freq in sorted(compaction_level_usage.items()):
            x.append(str(level))
            height.append(freq / 10 ** 9)

        plot.plot_bar(x, height, hatch='..', bar_colors='none', row=row, col=col)
        #plot.set_ylim(self.power_min_ylim, self.power_max_ylim, row, col)
        plot.set_labels("Compactions to output level", "Cpu Busy Frequency (GHz)", row, col)


    def compaction_level_report(self, out_name, width=10, height=30):
        plot = Plot(2,4)
        self.__generate_total_compaction_energy(plot, 0, 0)
        self.__generate_total_compaction_size(plot, 0, 1)
        self.__generate_avg_compaction_size(plot, 0, 2)
        self.__generate_avg_compaction_files(plot, 0, 3)
        self.__generate_total_compaction_duration(plot, 1, 0)
        self.__generate_total_compaction_number(plot, 1, 1)
        self.__generate_avg_compaction_power(plot, 1, 2)
        self.__generate_cpu_busy_frequency(plot, 1, 3)
        plot.fig.set_figheight(height)
        plot.fig.set_figwidth(width)
        plot.fig.tight_layout()
        plot.save_fig(out_name)
