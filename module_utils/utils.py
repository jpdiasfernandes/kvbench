#!/usr/bin/env python3

#class HashUtils:
#    def micro_from_dt(self, ts):
#        minutes = (ts.hour * 60) + ts.minute
#        seconds = (minutes * 60) + ts.second
#        micro = (seconds * 1000 * 1000) + ts.microsecond
#        return micro
#
#    def micro_from_td(self, td):
#        seconds = (td.days * 24 * 3600) + td.seconds
#        micro = (seconds * 1000 * 1000) + td.microseconds
#        return micro
#
#    def round_or_trunc(self, ts, micro):
#        micro_ts = self.micro_from_dt(ts)
#        if (micro_ts%(micro)) >= (micro/2):
#            return "round"
#        else:
#            return "trunc"
#
#    def round_micro(self, ts, micro):
#        micro_ts = self.micro_from_dt(ts)
#        if (micro_ts%(micro)) >= (micro/2):
#            ts += dt.timedelta(microseconds= micro)
#        ts -= dt.timedelta(microseconds=(micro_ts%micro))
#        return ts
#
#    def hash_time(self, ts, timedelta):
#        if timedelta.days == 0:
#            return self.round_micro(ts, self.micro_from_td(timedelta))
#        return ts

