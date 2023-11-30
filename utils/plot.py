#!/usr/bin/env python3

import pandas as pd
import matplotlib.pyplot as plt
from io import StringIO
import sys

workload_dstat = open(sys.argv[1], "r")
csv_lines = workload_dstat.readlines()

csv = csv_lines[5:]

csv.pop(1)

header_length = len(csv[0].split(','))

line_no = 1
for line in csv[1:]:
    line_split = line.split(',')
    if len(line_split) > header_length:
        line_split = line_split[:header_length]
        csv[line_no] = ",".join(line_split) + "\n"
    line_no += 1

csv_string_io = StringIO("".join(csv))

workload = pd.read_csv(csv_string_io)

workload['time'] = pd.to_datetime(workload['time'], format="%d-%m %H:%M:%S")

workload['usage'] = workload.apply(lambda row: row['total usage:usr'] + row['total usage:sys'], axis=1)

workload_cpu = workload[["usage"]]
workload_disk = workload[["dsk/total:read","dsk/total:writ"]]
workload_mem = workload[["used","cach"]]


# Remove .csv
file_no_format = sys.argv[1][:-4]
workload_cpu.plot()
plt.title('Execution phase CPU usage')
plt.ylabel('%')
plt.savefig(file_no_format + "-cpu.png")
workload_disk.plot()
plt.ylabel('KBytes')
plt.title('Execution phase Disk ops')
plt.savefig(file_no_format + "-disk.png")
workload_mem.plot()
plt.ylabel('KBytes')
plt.title('Execution phase Memory usage')
plt.savefig(file_no_format + "-mem.png")
