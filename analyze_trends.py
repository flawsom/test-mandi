"""Analyze long-term price trends to calibrate the ensemble damped trend model."""
import sys
sys.path.insert(0, '.')
import pandas as pd
import numpy as np
from scipy import stats
from mandi_rdd.storage.duckdb_store import get_connection

conn = get_connection(read_only=True)

print(f'{"Commodity":28s} {"Months":6s} {"First":8s} {"Last":8s} {"Endpoint":10s} {"MedianDiff":10s} {"OLS Slope":10s}')
print('-' * 80)

for comm in ['Wheat', 'Rice', 'Garlic', 'Carrot', 'Bhindi(Ladies Finger)', 'Onion']:
    df = conn.execute('''
        SELECT arrival_date, AVG(modal_price) as price
        FROM prices WHERE commodity = ?
        GROUP BY arrival_date ORDER BY arrival_date
    ''', [comm]).fetchdf()

    df['arrival_date'] = pd.to_datetime(df['arrival_date'])
    df['ym'] = df['arrival_date'].dt.to_period('M').astype(str)
    mon = df.groupby('ym')['price'].mean().reset_index().sort_values('ym')
    p = mon['price'].values
    n = len(p)

    if n > 2:
        first, last = p[0], p[-1]
        end_trend = (last - first) / n
        med_diff = np.median(np.diff(p))
        if n > 5:
            slope, _, _, _, _ = stats.linregress(range(n), p)
        else:
            slope = 0
        print(f'{comm:28s} {n:6d} {first:8.0f} {last:8.0f} {end_trend:10.2f} {med_diff:10.2f} {slope:10.2f}')

conn.close()
