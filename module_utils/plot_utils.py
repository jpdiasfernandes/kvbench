#!/usr/bin/env python3

from datetime import datetime
import datetime as dt
from matplotlib.figure import Figure
from matplotlib.axes import Axes
import matplotlib.pyplot as plt
import matplotlib.patches as patches

class TimeLineEvent:
    def __init__(self, start_x, end_x, height, hatch='..', edgecolor='black', facecolor='none', label=''):
        self.hatch = hatch
        self.edgecolor = edgecolor
        self.facecolor = facecolor
        self.label = label
        self.start_x = start_x
        self.width = end_x - start_x
        self.height = height

    def plot(self, axis, padding, y):
        new_height = self.height - 2*padding
        new_y = y + padding
        center_y = y + (self.height/2)
        center_x = self.start_x  + (self.width/2)
        axis.text(center_x, center_y, self.label, va='center', ha='center', color='black', fontsize='x-small',
                   bbox=dict(facecolor='white', boxstyle='round, pad=0.2', edgecolor='none'))
        axis.add_patch(patches.Rectangle((self.start_x, new_y), self.width, new_height, facecolor=self.facecolor, edgecolor=self.edgecolor, hatch=self.hatch, label=self.label))


class TimeLine:
    def __init__(self, bottom_y, height, padding, id: int, first_ts: dt.datetime, separator_color: str, separator_width, separator_style: str, title:str):
        self.bottom_y = bottom_y
        self.height = height
        self.padding = padding
        self.events = {}
        self.id_ = id
        self.first_ts = first_ts
        self.separator_color = separator_color
        self.separator_width = separator_width
        self.separator_style = separator_style
        self.title = title


    def get_total_height(self):
        return self.height

    def add_event(self, start_ts: dt.datetime, end_ts: dt.datetime, hatch='..', edgecolor='black', facecolor='none', label=''):
        start_x = (start_ts - self.first_ts).total_seconds()
        end_x = (end_ts - self.first_ts).total_seconds()
        self.events[(start_ts, end_ts)] = TimeLineEvent(start_x, end_x, self.height, hatch, edgecolor, facecolor, label)

    def plot(self, axis: Axes):
        timeline_event: TimeLineEvent
        axis.axhline(y=self.bottom_y, color=self.separator_color, linestyle=self.separator_style, lw=self.separator_width)
        bottom_ylim, upper_ylim = axis.get_ylim()
        total_dist = abs(upper_ylim - bottom_ylim)
        timeline_y = self.bottom_y
        dist_timeline = abs(timeline_y - bottom_ylim)
        ratio = dist_timeline / total_dist
        axis.text(1.08, ratio, self.title, ha='center', va='bottom', transform=axis.transAxes)
        for timeline_event in self.events.values():
            timeline_event.plot(axis, self.padding, self.bottom_y)

class TimeLineStack:
    def __init__(self, base_ylimit, first_ts: dt.datetime, separator_style='--', separator_color='black', line_width=1.5, timeline_height=5, padding=0.03):
        self.default_separator_linestyle = separator_style
        self.default_separator_color = separator_color
        self.default_line_width = line_width
        self.default_timeline_height = timeline_height
        self.default_padding = padding
        self.stack = []
        self.id_timeline = {}
        self.id = 0
        self.first_ts = first_ts
        self.base_ylimit = base_ylimit
        self.cur_ylimit = base_ylimit
        self.legends = {}


    def push_timeline(self, height, padding, separator_color, separator_width, separator_linestyle, title):
        res_id = self.id
        timeline = TimeLine(self.cur_ylimit, height, padding, res_id, self.first_ts, separator_color, separator_width, separator_linestyle, title)
        if res_id not in self.id_timeline.keys():
            self.stack.append(timeline)
            self.id_timeline[res_id] = timeline
            self.cur_ylimit += timeline.get_total_height()

            self.id += 1
            return res_id
        else:
            return -1

    def add_legend(self, hatch, short_description, facecolor):
        custom_legend = patches.Patch(edgecolor='black', hatch=hatch, facecolor=facecolor, label=short_description, linewidth=0.1)
        self.legends[hatch] = custom_legend

    def push_default_timeline(self):
        res = self.push_timeline(self.default_timeline_height, self.default_padding, self.default_separator_color, self.default_line_width, self.default_separator_linestyle, '')
        return res

    def add_event(self, timeline_id: int, start_ts: dt.datetime, end_ts: dt.datetime, hatch='..', edgecolor='black', facecolor='none', label=''):
        timeline: TimeLine = self.id_timeline[timeline_id]
        timeline.add_event(start_ts, end_ts, hatch, edgecolor, facecolor, label)

    def plot(self, axis: Axes, fig: Figure):
        axis.legend(handles=list(self.legends.values()), loc='center left', bbox_to_anchor=(1, 0.1))
        bottom_y,_ = axis.get_ylim()
        axis.set_ylim(bottom_y, self.cur_ylimit)
        for timeline in self.stack:
            timeline.plot(axis)
        fig.tight_layout()

class Plot:
    def __init__(self, rows: int = 1, cols: int = 1):
        self.no_row = rows
        self.no_col = cols
        self.fig: Figure
        self.fig , self.ax = plt.subplots(rows, cols)
        self.timeline_manager = {}

    def __get_axis(self, row, col):
        if self.no_row == 1 and self.no_col == 1:
            return self.ax
        if self.no_row == 1 and self.no_col != 1:
            return self.ax[col]
        elif self.no_col == 1 and self.no_row != 1:
            return self.ax[row]
        else:
            return self.ax[row, col]

    def get_axis(self, row = 0, col = 0):
        return self.__get_axis(row, col)

    def set_title(self, title, row = 0, col = 0):
        axis: Axes
        axis = self.__get_axis(row, col)
        axis.set_title(title)

    def set_ylim(self, ymin:int, ymax:int, row = 0, col = 0):
        axis:Axes
        axis = self.__get_axis(row, col)
        axis.set_ylim(ymin, ymax)
    def set_xlim(self, xmin:int, xmax:int, row = 0, col = 0):
        axis:Axes
        axis = self.__get_axis(row, col)
        axis.set_xlim(xmin, xmax)

    def set_labels(self, xlabel = "", ylabel = "", row = 0, col = 0):
        axis:Axes
        axis = self.__get_axis(row, col)
        axis.set_xlabel(xlabel)
        axis.set_ylabel(ylabel)

    def plot_line(self, x, y, row = 0, col = 0, color='blue'):
        axis = self.__get_axis(row, col)
        axis.plot(x,y, color=color)

    def defaults_timeline_stack(self, first_ts: dt.datetime, separator_style='--', separator_color='black', line_width=1.5, timeline_height=5, padding=0.03, row = 0, col = 0):
        axis: Axes = self.__get_axis(row, col)
        if (row, col) not in self.timeline_manager.keys():
            _, upper_ylim = axis.get_ylim()
            self.timeline_manager[(row,col)] = TimeLineStack(upper_ylim, first_ts)
        stack: TimeLineStack = self.timeline_manager[(row,col)]
        stack.default_separator_linestyle = separator_style
        stack.default_separator_color = separator_color
        stack.default_line_width = line_width
        stack.default_timeline_height = timeline_height
        stack.default_padding = padding

    def push_default_timeline(self, first_ts: dt.datetime, row = 0, col = 0):
        axis:Axes
        axis = self.__get_axis(row, col)
        if (row, col) not in self.timeline_manager.keys():
            _,upper_ylim = axis.get_ylim()
            self.timeline_manager[(row,col)] = TimeLineStack(upper_ylim, first_ts)

        stack: TimeLineStack = self.timeline_manager[(row,col)]
        return stack.push_default_timeline()

    def push_timeline(self, first_ts: dt.datetime, title, separator_style, separator_color, line_width, timeline_height, padding, row = 0, col = 0):
        axis: Axes = self.__get_axis(row,col)
        if (row, col) not in self.timeline_manager.keys():
            _,upper_ylim = axis.get_ylim()
            self.timeline_manager[(row,col)] = TimeLineStack(upper_ylim, first_ts)

        stack: TimeLineStack = self.timeline_manager[(row,col)]
        return stack.push_timeline(timeline_height, padding, separator_color, line_width, separator_style, title)


    def add_event_to_timeline(self, timeline_id: int, start_ts: dt.datetime, end_ts: dt.datetime, hatch='..', edgecolor='black', facecolor='none', label='', row = 0, col = 0):
        if (row,col) in self.timeline_manager.keys():
            stack: TimeLineStack = self.timeline_manager[(row,col)]
            stack.add_event(timeline_id, start_ts, end_ts, hatch, edgecolor, facecolor, label)

    def plot_timeline_stack(self, row = 0, col = 0):
        if (row, col) in self.timeline_manager.keys():
            axis: Axes = self.__get_axis(row, col)
            stack: TimeLineStack = self.timeline_manager[(row,col)]
            stack.plot(axis, self.fig)

    def add_timeline_legend(self, hatch, short_description, facecolor='none', row = 0, col = 0):
        if (row, col) in self.timeline_manager.keys():
            stack: TimeLineStack = self.timeline_manager[(row,col)]
            stack.add_legend(hatch, short_description, facecolor)

    def show(self):
        plt.show()

    def save_fig(self, out_name):
        self.fig.savefig(out_name)
