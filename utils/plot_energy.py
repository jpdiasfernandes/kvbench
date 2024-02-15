#!/usr/bin/env python3
import matplotlib.pyplot as plt
import pandas as pd
import sys

energy_pd = open(sys.argv[1])

metrics = {}
fields = []

def to_datetime(date_string):
    return pd.to_datetime(date_string, format="%H:%M:%S")

def get_duration(date_time, first_date):
    return (date_time - first_date).total_seconds()

header = energy_pd.readline()

first_date_time = None


while header:
    line = energy_pd.readline()

    # store metrics
    splitted_header = header.split(';')
    splitted_line = line.split(';')
    timestamp = splitted_line[0]
    if first_date_time == None:
        first_date_time = to_datetime(timestamp)
    metrics[timestamp] = {}
    for i in range(1, len(splitted_header)-1):
        metrics[timestamp][splitted_header[i]] = splitted_line[i]
        if not splitted_header[i] in fields:
            fields.append(splitted_header[i])

    # read header
    header = energy_pd.readline()

energy_pd.close()

df = pd.DataFrame()

for time, metric in metrics.items():
    for key, value in metric.items():
        dur = get_duration(to_datetime(time), first_date_time)
        df.at[dur, key] = float(value)

threads_df = df.filter(regex=(r' Tid \d+ Energy'))
pid_acc = df.filter(regex=(r' Pid \d+ Accumulated Energy'))
pids = df.filter(regex=(r' Pid \d+ Energy'))

print(threads_df)
print(pid_acc)
print(pids)

file_no_format = sys.argv[1][:-4]

threads_df.plot()
plt.title('Threads Energy')
plt.ylabel('J')
plt.xlabel('seconds')
plt.savefig(file_no_format + "-tids-energy.png")

pid_acc.plot()
plt.title('Pid Accumulated Energy')
plt.ylabel('J')
plt.xlabel('seconds')
plt.savefig(file_no_format + "-acc-energy.png")

pids.plot()
plt.title('Process and Descendants Energy')
plt.ylabel('J')
plt.xlabel('seconds')
plt.savefig(file_no_format + "-pids-energy.png")

events = open(sys.argv[2], "r")
lines_events = events.readlines()


plt.figure().set_figwidth(22)

event_tids = []
for event in lines_events[1:]:
    splited = event.split(";")
    tid = splited[2].split(" ")[1].strip("\n")
    if tid not in event_tids:
        event_tids.append(tid)
        name = ' Tid ' + str(tid) + ' Energy'
        label = 'Tid ' + str(tid) + ' energy'
        plt.plot(threads_df.index.tolist(), threads_df[name].tolist(), label=label, linestyle='dashed')

for event in lines_events[1:]:
    splited = event.split(";")
    event_type = splited[0]
    timestamp = splited[1]
    dur = get_duration(to_datetime(timestamp), first_date_time)
    tid = splited[2].split(" ")[1].strip("\n")
    collumn_name = ' Tid ' + str(tid) + ' Energy'

    print(dur)
    print(threads_df.index)
    if dur in threads_df.index:
       y = threads_df.loc[dur, collumn_name]
       if event_type == "Compaction":
           plt.plot([dur], [y], "p", color="b")
       elif event_type == "Flush":
           plt.plot([dur], [y], "s", color="r")


plt.xlabel('Time (seconds)')
plt.ylabel("Energy (Joules)")

plt.legend()
name = file_no_format + 'tids-energy-events'
plt.savefig(name)

#file_no_format = sys.argv[1][:-4]
#
#plt.title('Package CPU power')
#plt.ylabel('W')
#plt.savefig(file_no_format + ".png")
