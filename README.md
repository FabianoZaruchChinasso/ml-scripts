# WIFI Metric Scripts

This project provides Python scripts to collect WIFI metrics from InfluxDB and transform them into CSV datasets for analysis and ML workflows.

## Main scripts

- `src/get-metrics.py`: collect raw metrics from InfluxDB into CSV.
- `src/get-router.py`: collect router site-survey data.
- `src/get-client.py`: collect client site-survey data.
- `src/fn-metrics.py`: apply filter/normalization directives from a `.dsc` file to an input CSV.

## Directive format

Each directive line follows:

`name; data; operation; values`

- `name`: free text label
- `data`: one column name or a Python-style list of columns
- `operation`: operation name
- `values`: optional operation-specific values

## `fill-last` behavior

`fill-last` forward-fills NaN values.

- Without `values`: global forward fill (legacy behavior), fallback default is `0`.
- With `values` as `group_column,group_name`: fill only rows that belong to `group_name` in `group_column`.
- With `values` as `group_column::group_name`: same grouped behavior.
- With `values` as `group_column,group_name,default_value`: grouped behavior plus custom fallback for first empty row in the group.

Examples:

- `fl1; empty_col; fill-last`
- `fl2; empty_col; fill-last; 99`
- `fl3; empty_col; fill-last; measure_group, client`
- `fl4; empty_col; fill-last; measure_group::client`
- `fl5; empty_col; fill-last; measure_group,client,99`

## `fill-last-auto` behavior

`fill-last-auto` forward-fills NaN values by group, where the group is automatically read from each current row.

- `values` must contain the group column name.
- For each NaN cell in target columns, the script searches previous rows with the same group value and uses the last valid value in that same target column.
- If no previous valid value exists for that group, the NaN is filled with `0`.

Examples:

- `fla1; empty_col; fill-last-auto; measure_group`
- `fla2; ['v1','v2']; fill-last-auto; measure_group`

## Testing

Run tests with:

```bash
python -m unittest tests/test_fn_metrics.py
```
