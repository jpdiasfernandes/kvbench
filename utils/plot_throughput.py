#!/usr/bin/env python3
import re
import sys
import pandas as pd
import matplotlib.pyplot as plt

float_pair = r'\((?P<first>\d+(\.\d+)?),(?P<second>\d+(\.\d+)?)\)'

entry_regex = r'(?P<date_time>\d{4}\/\d{2}\/\d{2}-\d{2}:\d{2}:\d{2})  \.\.\. thread (?P<thread_no>\d+): (?P<ops_pair>\(\d+,\d+\)) ops and (?P<ops_throughput_pair>\(\d+(\.\d+)?,(\d+(\.\d+)?)\)) ops/second in (?P<seconds_pair>\(\d+(\.\d+)?,(\d+(\.\d+)?)\)) seconds'

text = open(sys.argv[1], "r").read()

iterator = re.finditer(entry_regex, text)

hist_df = pd.DataFrame()

def to_datetime(date_string):
    return pd.to_datetime(date_string, format="%Y/%m/%d-%H:%M:%S")

for match_iter in iterator:
    date_time_str = match_iter.group('date_time')
    thread_no = match_iter.group('thread_no')

    date_time = to_datetime(date_time_str)
    throughput_pair = match_iter.group('ops_throughput_pair')
    throughput_match = re.match(float_pair, throughput_pair)

    if throughput_match:
        throughput = float(throughput_match.group('first'))/1000 #convert to KOps
        hist_df.at[date_time, 'thread_' + thread_no] = throughput

#remove .log extension
file_no_format = sys.argv[1][:-4]
print(file_no_format)
hist_df.plot()
plt.title('Thread throughput progression')
plt.ylabel('KOps/s')
plt.savefig(file_no_format + "-throughput.png")
