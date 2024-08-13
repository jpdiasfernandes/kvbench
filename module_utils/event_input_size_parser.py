#!/usr/bin/env python3
from datetime import datetime

def init_compaction(job):
    if job not in parser.compactions.keys():
        parser.compactions[job] = {
        }

def convert_dt_str(dt):
    fmt = "%Y/%m/%d-%H:%M:%S.%f"
    converted_dt = datetime.strptime(dt, fmt)
    return str(converted_dt)


import ply.lex as lex
######################################## Lexer #######################################

tokens = ["TIME", "START", "ORIGINAL_LOG_TIME", "FILELINE", "END", "NUM", "JOB", "DEFAULT", "SUMMARY", "BASE_LEVEL", "BASE_VERSION", "INPUTS", "NL", "SIZE"]

literals= "[ ] ( ) , + @".split(" ")

def t_TIME(t):
    r'\d{4}\/\d{2}\/\d{2}-\d{2}:\d{2}:\d{2}\.\d{6}'
    return t

def t_FILELINE(t):
    r'[^ \.\n\[\]]+?(\/[^\ \.\n\[\]]+?)*(\.[^\ \.\n\[\]]+?):\d+'
    return t

def t_SUMMARY(t):
    r'Compaction\ start\ summary'
    return t

def t_START(t):
    r'Compacting'
    return t


def t_BASE_LEVEL(t):
    r'Base\ level'
    return t

def t_BASE_VERSION(t):
    r'Base\ version'
    return t

def t_END(t):
    r'Compacted'
    return t

def t_ORIGINAL_LOG_TIME(t):
    r'Original\ Log\ Time'
    return t

def t_JOB(t):
    r'JOB'
    return t

def t_INPUTS(t):
    r'inputs:'
    return t

def t_DEFAULT(t):
    r'default'
    return t

def t_SIZE(t):
    r'((MB)|(KB)|(GB)|(B))'
    return t

def t_NL(t):
    r'\n'
    return t

def t_NUM(t):
    r'[+-]?[0-9]+\.?[0-9]*'
    return t

def t_error(t):
    #print('Carácter inválido', t.value[0])
    t.lexer.skip(1)

t_ignore = ' \t\r'
lexer = lex.lex()


############################### Parser ###############################
import ply.yacc as yacc

def p_Log(p):
    "Log : Lines"
    p[0] = p[1]

def p_Lines_List(p):
    "Lines : Lines Line"
    p[0] = p[1] + [p[2]]

def p_Lines_Empty(p):
    "Lines : "
    p[0] = []

def p_Line_Compacting(p):
    "Line : LineCont NL"
    p[0] = p[1]



def p_LineCont_Start(p):
    "LineCont : TIME NUM '[' FILELINE ']' '[' DEFAULT ']' '[' JOB NUM ']' START CompactionAt '+' CompactionAt NUM ',' NUM"
    #   0         1   2   3      4     5   6     7     8   9   10  11  12  13       14        15      16       17 18   19
    compaction_no = int(p[11])
    init_compaction(compaction_no)
    parser.compactions[compaction_no]["quantity"] = {
        p[14][1] : p[14][0],
        p[16][1] : p[16][0]
    }
    parser.compactions[compaction_no]["start"] = convert_dt_str(p[1])
    parser.compactions[compaction_no]["thread"] = int(p[2])
    parser.compaction_number += 1
    parser.current_job = compaction_no
    parser.compactions[compaction_no]["job_id"] = int(p[11])

    #print("In start of", compaction_no)

def p_LineCont_Summary(p):
    "LineCont : TIME NUM '[' FILELINE ']' '[' DEFAULT ']' SUMMARY BASE_VERSION NUM BASE_LEVEL NUM ',' INPUTS InputInfo"
    #   0         1   2   3      4     5   6      7    8     9          10      11      12     13  14   15      16
    init_compaction(parser.current_job)
    #print("In summary of job", parser.current_job)
    parser.compactions[parser.current_job]["inputs"] = p[16]

def p_LineCont_End(p):
    "LineCont : TIME NUM '(' ORIGINAL_LOG_TIME TIME ')' '[' FILELINE ']' '[' DEFAULT ']' '[' JOB NUM ']' END CompactionAt '+' CompactionAt NUM NUM"
    #   0         1   2   3            4         5   6   7     8     9    10  11      12  13 14  15  16  17      18       19     20         21 22
    compaction_no = int(p[15])
    init_compaction(compaction_no)
    parser.compactions[compaction_no]["end"] = convert_dt_str(p[5])
    #print("In end of compaction", compaction_no)

def p_CompactionAt(p):
    "CompactionAt : NUM '@' NUM"
    p[0] = int(p[1]),int(p[3])

def p_InputInfo(p):
    "InputInfo : InputInfo ',' InfoList"
    p[0] = p[1] + [p[3]]

def p_InputInfo_Empty(p):
    "InputInfo : InfoList"
    p[0] = [p[1]]

def p_InfoList_List(p):
    "InfoList : '[' InfoContList ']'"
    info_map = {}
    #print(p[2])
    for key, value in p[2]:
        info_map[key] = value

    p[0] = info_map

def p_InfoContList(p):
    "InfoContList : InfoContList InfoCont"
    p[0] = p[1] + [p[2]]

def p_InfoContList_One(p):
    "InfoContList : InfoCont"
    #print(p[1])
    p[0] = [p[1]]

def p_InfoCont(p):
    "InfoCont : NUM '(' NUM SIZE ')'"
    #  0         1   2   3    4
    if p[4] == 'GB':
        multiplier = 10**9
    elif p[4] == 'MB':
        multiplier = 10**6
    elif p[4] == 'KB':
        multiplier = 10**3
    elif p[4] == 'B':
        multiplier = 1


    p[0] = (int(p[1]), (float(p[3]) * multiplier))


def p_error(p):
    #if p is not None:
    #    print ("Line %s, illegal token %s" % (p.lineno, p.value))
    #else:
    #    print('Unexpected end of input')
    pass


parser = yacc.yacc(debug=False, write_tables=False)
parser.compactions = {}
parser.compaction_number = 0
parser.current_job = 0
