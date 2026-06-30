# Project Specification: Wifi Dataset filtering

## 1. Project Overview
This project has several Python scripts to collect WIFI metrics from Influx Database (Time Series DB) and handle as a Time Series dataset.
The files lead with 'get-', collect metrics in RAW mode and store 'as is' in a CSV dataset as Time Series where fist column is the timestamp.
The files lead with 'fn-' filter and nomalize metrics from a dataset in a CSV file and according to a filter and normalization description file (fn.dsc).

The filter and normalization description is a list of directives to handle the dataset columns present in description file, each line contains a directive in format:
- name; data; operation; values
Where:
name: is the directive name, just for description
data: is the column name or a collumn list name as python list (e.g. ['col1', 'col2'])
operation: the operation to be applied over colluns
values: optional values according used by operation when it is need, the values are separated by comma

The following operations are possible:
- drop: drop a column or a list of collumns
- rename: rename a column or a list of collumns. The values contain the new name or a list of new names.
- multiply: multiply the values of a column or collumns list with operation value
- scale: divide the values of a column or collumn list with operation value
- normalize: divide the values of a column or collumn list by the maximum value present in that collumn
- if-greater, if-less, if-equal, if-notequal: these operations create a boolean mask for the rows. The directive immediately following an `if` is applied only to the rows where the mask is True. If an `else` directive follows, the next directive after that is applied to the rows where the mask is False.
- subst-same: convert a string to a number. When collumn value matches the first operation value (string), it is replaced by the second value (typically 1). Otherwise, it is replaced by the third value (typically 0).
- subst-contains: similar to subst-same, but performs a substring match.
- fill-empty: fill empty (NaN) values in a column or list of columns with a specified value. If no value is provided, it defaults to 0.
- math: add a new column or a list of new columns to the dataset. The values are calculated according to one or more arithmetic formulas provided in the `values` field (separated by commas if multiple). Formulas support standard operators (`+`, `-`, `*`, `/`), parentheses for precedence, power operator (`**`), and advanced mathematical functions (e.g., `log`, `sqrt`, `exp`, `sin`, `cos`). Formulas can reference existing columns by name or use constants.
- suppress-eq: suppress (remove) rows from the dataset when a column's value is equal to the specified operation value.
- suppress-ne: suppress (remove) rows from the dataset when a column's value is not equal to the specified operation value.


## 2. Directory Structure

- `src/`: Core source code.
- `test/`: Unit and tests.

## 3. Architecture
The collection scripts ('get') are three:
1. get-metrics: collect metrics from InfluxDB. Parameters: `-o` (output file), `-s` (start time), `-e` (end time), `-u` (server URL), `-r` (org), `-b` (bucket). The Influx DB token MUST be provided via the `INFLUXDB_TOKEN` environment variable; the script will validate its presence. In addition to standard fields, it calculates two new features:
   - `router_opportunity_medium_use`: calculated by parsing the `router_site_survey_ap` map and counting neighbors using the same frequency.
   - `client_opportunity_medium_use`: calculated by parsing the `site_survey_client` map and counting neighbors using the same frequency.
   The raw JSON map fields are excluded from the output dataset.
2. get-router: get route site survey, which contains the client list metrics, each client metric is in a map. 
3. get-client: get client site survey, which contains the AP list metrics, each AP metric is in a map.
The scripts receive as parameters the output CSV file, the start and stop time to collect metrics and the influxdb address. The Influx DB token is an environment variable.


The script for filter and normalize metrics is divided in following classes:
- **DirectiveOperationItf**: it is an interface class which has interface functions:
  - *DoOperation*, which receives the following parameter: the dataset and an optional row mask.
  - *SetValues*, which receives the operation values.
- **DirectiveOperation<name>**: specific directive operation classes (e.g., `DirectiveOperationDrop`, `DirectiveOperationScale`, `DirectiveOperationMath`), derived from DirectiveOperationItf.
- **OperationParser**: responsible to register all operation in a map.
  - *AddOperation*: adds a mapping from operation name to object.
  - *Parse*: parses the directive line, logs the action, and calls the appropriate operation. It handles the 'if-else' logic by managing the active mask passed to DoOperation.
- **Transformer**: the main class that orchestrates the process.
  - Load input CSV file with pandas.
  - Process directives line-by-line using the OperationParser.
  - Save the dataset to output CSV file.

## 4. Error Handling
- If a directive references a column not present in the dataset, the script must issue a Warning log and skip that directive.
- If any directives were skipped due to errors, the script must prompt the user to confirm if the output file should still be saved.

## 5. Coding Standards
- **Indentation**: 2 spaces.
- Each class should be in your own file.
