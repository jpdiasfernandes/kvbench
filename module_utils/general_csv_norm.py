#!/usr/bin/env python3
def rows_same_size(csv):
    changes = False
    header_length = len(csv[0].split(','))

    line_no = 1
    for line in csv[1:]:
        line_split = line.split(',')
        if len(line_split) > header_length:
            line_split = line_split[:header_length]
            csv[line_no] = ",".join(line_split) + "\n"
            changes = True
        line_no += 1

    return changes

def pcp_dstat_remove_headers(csv):
    csv = csv[5:]
    csv.pop(1)


def test():
    return "Hello world!"
