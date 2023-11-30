#!/usr/bin/env python3
import matplotlib.pyplot as plt
import pandas as pd
import sys

energy_pd = pd.read_csv(sys.argv[1])

file_no_format = sys.argv[1][:-4]

energy_pd.plot()
plt.title('Package CPU power')
plt.ylabel('W')
plt.savefig(file_no_format + ".png")
