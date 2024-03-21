#!/usr/bin/env python3

import sys
import re
import shutil
dstat_output = open(sys.argv[1], "r")

csv_lines = dstat_output.readlines()

csv = csv_lines

ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


fixed_csv = open(sys.argv[1] + ".new", "w")

for line in csv:
    tmp_text = ansi_escape.sub('', line)
    print(tmp_text, file=fixed_csv, end='')

dstat_output.close()
fixed_csv.close()

shutil.move(sys.argv[1] + ".new", sys.argv[1])
