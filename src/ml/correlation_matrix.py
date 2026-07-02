import pandas as pd
import matplotlib.pyplot as plt

import seaborn as sns

DS_CSV="data/metrics-20260630-out.csv"

# read dataset
df = pd.read_csv(DS_CSV, sep=',', header=0)

# drop not useful columns
df=df.drop(columns=['_time'])

# get correlation matrix
c_m=df.corr()

# plot correlation matrix
axis_corr = sns.heatmap(c_m.round(2), vmin=-1, vmax=1, center=0,cmap=sns.diverging_palette(50, 500, n=500),annot=True,square=True)
plt.show()