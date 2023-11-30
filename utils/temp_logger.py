#!/usr/bin/env python3

from time import sleep
import signal
import sys
import subprocess
import json
import argparse

def sigint_handler(sig, frame):
    exit()

def get_temp_dict(chip):
    result = subprocess.run(["sensors", args.chip, "-A", "-j" ], stdout=subprocess.PIPE)
    return json.loads(result.stdout)

def write_header(sensor_dict, out, chip, sep):
    header = ""
    for key in sensor_dict[chip].keys():
        header += (key + sep)

    print(header[:-1], file=out)

def write_entry(sensor_dict, out, chip, sep):
    entry = ""
    input_num = 1
    for key, value in sensor_dict[chip].items():
        value_key = "temp" + str(input_num) + "_input"
        input_num += 1
        entry += (str(value[value_key]) + sep)

    print(entry[:-1], file=out)

parser = argparse.ArgumentParser(
    prog="temp-logger",
    description="Logs CPU temperature to a csv format"
)

parser.add_argument('filename', nargs='?', help='if filename empty stdout is used as default')
parser.add_argument('-c', '--chip', type=str, nargs=1, default='coretemp-isa-0000',
                    help='which chip to retrieve temperature information from')
parser.add_argument('-i', '--interval', type=int, nargs=1, default=1)
parser.add_argument('-s', '--separator', type=str, nargs=1, default=',')
signal.signal(signal.SIGINT, sigint_handler)

args = parser.parse_args()

if args.filename == None:
    file = sys.stdout
else:
    file = open(args.filename, "a")


temp_dict = get_temp_dict(args.chip)
write_header(temp_dict, file, args.chip, args.separator)

while True:
    temp_dict = get_temp_dict(args.chip)
    write_entry(temp_dict, file, args.chip, args.separator)
    sleep(args.interval)
