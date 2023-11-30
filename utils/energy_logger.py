#!/usr/bin/env python3
import signal
from time import sleep
import sys
import argparse
import subprocess

def sigint_handler(sig, frame):
    exit()

parser = argparse.ArgumentParser(
    prog='energy-logger',
    description='Logs CPU Package power to csv format'
)

def microJ_to_J(micro):
    return micro/10**6

def get_energy():
    result = subprocess.run(['cat', '/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj'], stdout=subprocess.PIPE)
    result_int = int(result.stdout.decode("utf-8", "ignore"))
    return microJ_to_J(result_int)

def get_power(before, interval):
    energy = get_energy()
    return ( float((energy - before))/interval, energy)


parser.add_argument('filename', nargs='?', help='if filename empty stdout is used as default')
parser.add_argument('-i', '--interval', type=int, nargs=1, default=1)
parser.add_argument('-s', '--separator', type=str, nargs=1, default=',')

args = parser.parse_args()

signal.signal(signal.SIGINT, sigint_handler)

if args.filename == None:
    file = sys.stdout
else:
    file = open(args.filename, "a")

print("Package-0", file=file)

before = get_energy()

while True:
    sleep(args.interval)
    cur_power, energy_read = get_power(before, args.interval)
    before = energy_read
    print("{:.2f}".format(cur_power), file=file)
