#!/usr/bin/env python3
import matplotlib.pyplot as plt
import pandas as pd
import sys

temp_pd = pd.read_csv(sys.argv[1])


file_no_format = sys.argv[1][:-4]

temp_pd_package = temp_pd[["Package id 0"]]

temp_pd_package.plot()
plt.title('Package CPU temperature')
plt.ylabel('ºC')
plt.savefig(file_no_format + ".png")
