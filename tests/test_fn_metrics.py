import unittest
import pandas as pd
import io
import os
import sys
import tempfile
import numpy as np

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from transformer import Transformer
from opers.operation_parser import OperationParser
from opers.operation_drop import DirectiveOperationDrop
from opers.operation_rename import DirectiveOperationRename
from opers.operation_scale import DirectiveOperationScale
from opers.operation_normalize import DirectiveOperationNormalize
from opers.operation_multiply import DirectiveOperationMultiply
from opers.operation_subst_same import DirectiveOperationSubstSame
from opers.operation_subst_contains import DirectiveOperationSubstContains
from opers.operation_if_greater import DirectiveOperationIfGreater
from opers.operation_if_less import DirectiveOperationIfLess
from opers.operation_if_equal import DirectiveOperationIfEqual
from opers.operation_if_notequal import DirectiveOperationIfNotequal
from opers.operation_fill_empty import DirectiveOperationFillEmpty
from opers.operation_fill_last import DirectiveOperationFillLast
from opers.operation_suppress_eq import DirectiveOperationSuppressEq
from opers.operation_suppress_ne import DirectiveOperationSuppressNe
from opers.operation_suppress_empty_pct import DirectiveOperationSuppressEmptyPct

class TestFnMetrics(unittest.TestCase):
  def setUp(self):
    self.test_data_path = os.path.join(os.path.dirname(__file__), 'res', 'test_data.csv')
    self.df = pd.read_csv(self.test_data_path)
    self.parser = self.setup_parser()

  def setup_parser(self):
    parser = OperationParser()
    parser.add_operation('drop', DirectiveOperationDrop())
    parser.add_operation('rename', DirectiveOperationRename())
    parser.add_operation('scale', DirectiveOperationScale())
    parser.add_operation('normalize', DirectiveOperationNormalize())
    parser.add_operation('multiply', DirectiveOperationMultiply())
    parser.add_operation('subst-same', DirectiveOperationSubstSame())
    parser.add_operation('subst-contains', DirectiveOperationSubstContains())
    parser.add_operation('if-greater', DirectiveOperationIfGreater())
    parser.add_operation('if-less', DirectiveOperationIfLess())
    parser.add_operation('if-equal', DirectiveOperationIfEqual())
    parser.add_operation('if-notequal', DirectiveOperationIfNotequal())
    parser.add_operation('fill-empty', DirectiveOperationFillEmpty())
    parser.add_operation('fill-last', DirectiveOperationFillLast())
    parser.add_operation('suppress-eq', DirectiveOperationSuppressEq())
    parser.add_operation('suppress-ne', DirectiveOperationSuppressNe())
    parser.add_operation('suppress-empty-pct', DirectiveOperationSuppressEmptyPct())
    return parser

  def test_drop(self):
    line = "d1; RSSI; drop"
    df_result = self.parser.parse(line, self.df.copy())
    self.assertNotIn("RSSI", df_result.columns)
    self.assertIn("distance_m", df_result.columns)

  def test_rename(self):
    line = "r1; RSSI; rename; Signal"
    df_result = self.parser.parse(line, self.df.copy())
    self.assertNotIn("RSSI", df_result.columns)
    self.assertIn("Signal", df_result.columns)

  def test_scale(self):
    # SPEC: divide by value
    line = "s1; jitter_ms; scale; 1000"
    df_result = self.parser.parse(line, self.df.copy())
    # 16.18 / 1000 = 0.01618
    self.assertAlmostEqual(df_result.iloc[0]["jitter_ms"], 0.01618)

  def test_normalize(self):
    # SPEC: divide by max
    line = "n1; RSSI; normalize"
    df_result = self.parser.parse(line, self.df.copy())
    # RSSI max is -26. Row 0 is -34.
    # -34 / -26 = 1.307692...
    expected = -34 / -26
    self.assertAlmostEqual(df_result.iloc[0]["RSSI"], expected)

  def test_multiply(self):
    # SPEC: multiply by value
    line = "m1; speedtest_down_mbps; multiply; 2.5"
    df_result = self.parser.parse(line, self.df.copy())
    expected = self.df.iloc[0]["speedtest_down_mbps"] * 2.5
    self.assertAlmostEqual(df_result.iloc[0]["speedtest_down_mbps"], expected)

  def test_subst_same(self):
    line = "ss1; client_name; subst-same; netprobe-linux, 1, 0"
    df_result = self.parser.parse(line, self.df.copy())
    self.assertEqual(df_result.iloc[0]["client_name"], 1)
    self.assertEqual(df_result.iloc[1]["client_name"], 0)

  def test_subst_contains(self):
    line = "sc1; client_mode; subst-contains; WiFi 6, 1, 0"
    df_result = self.parser.parse(line, self.df.copy())
    self.assertEqual(df_result.iloc[0]["client_mode"], 1)
    self.assertEqual(df_result.iloc[1]["client_mode"], 0)

  def test_if_greater_else(self):
    # SPEC: "The directive immediately following an if is applied only to the rows where the mask is True."
    df = self.df.copy()
    # Scale jitter_ms by 10 (divide by 10) only if RSSI > -30
    df = self.parser.parse("if1; RSSI; if-greater; -30", df)
    df = self.parser.parse("s1; jitter_ms; scale; 10", df)
    # Else, scale jitter_ms by 100 (divide by 100)
    df = self.parser.parse("e1; ; else", df)
    df = self.parser.parse("s2; jitter_ms; scale; 100", df)
    
    # Row 0: RSSI -34 (<= -30) -> Else applies (divide by 100)
    # Row 1: RSSI -29 (> -30) -> If applies (divide by 10)
    self.assertAlmostEqual(df.iloc[0]["jitter_ms"], 16.18 / 100)
    self.assertAlmostEqual(df.iloc[1]["jitter_ms"], 271.42 / 10)

  def test_drop_list(self):
    line = "d2; ['RSSI', 'distance_m']; drop"
    df_result = self.parser.parse(line, self.df.copy())
    self.assertNotIn("RSSI", df_result.columns)
    self.assertNotIn("distance_m", df_result.columns)

  def test_scale_list(self):
    line = "sl1; ['speedtest_down_mbps', 'speedtest_up_mbps']; scale; 100"
    df_result = self.parser.parse(line, self.df.copy())
    self.assertAlmostEqual(df_result.iloc[0]["speedtest_down_mbps"], 3.9876)
    self.assertAlmostEqual(df_result.iloc[0]["speedtest_up_mbps"], 1.081)

  def test_rename_list(self):
    # SPEC: "The values contain the new name or a list of new names."
    # Note: OperationParser expects op_values to be a list of strings if semicolon separated.
    # But wait, rename op_values parsing in operation_parser.py:
    # op_values = parts[3].split(',') if len(parts) > 3 else []
    line = "rl1; ['RSSI', 'distance_m']; rename; Signal, Dist"
    df_result = self.parser.parse(line, self.df.copy())
    self.assertNotIn("RSSI", df_result.columns)
    self.assertIn("Signal", df_result.columns)
    self.assertNotIn("distance_m", df_result.columns)
    self.assertIn("Dist", df_result.columns)

  def test_fill_empty(self):
    # Default fill (0)
    line = "fe1; empty_col; fill-empty"
    df_result = self.parser.parse(line, self.df.copy())
    # Row 1 in test_data.csv is empty for empty_col
    self.assertEqual(df_result.iloc[1]["empty_col"], 0.0)
    # Row 0 is 1.0
    self.assertEqual(df_result.iloc[0]["empty_col"], 1.0)

    # Custom fill (99)
    line = "fe2; empty_col; fill-empty; 99"
    df_result = self.parser.parse(line, self.df.copy())
    self.assertEqual(df_result.iloc[1]["empty_col"], 99.0)

  def test_fill_last(self):
    line = "fl1; empty_col; fill-last"
    df_result = self.parser.parse(line, self.df.copy())
    # Row 0: 1.0
    # Row 1: empty -> should become 1.0
    # Row 2: 3.0
    # Row 3: empty -> should become 3.0
    self.assertEqual(df_result.iloc[0]["empty_col"], 1.0)
    self.assertEqual(df_result.iloc[1]["empty_col"], 1.0)
    self.assertEqual(df_result.iloc[2]["empty_col"], 3.0)
    self.assertEqual(df_result.iloc[3]["empty_col"], 3.0)

  def test_suppress_empty_pct(self):
    # Use columns ['empty_col', 'RSSI']
    # Row 0: [1.0, -34] -> 0% empty
    # Row 1: [NaN, -29] -> 50% empty
    # Row 2: [3.0, -41] -> 0% empty
    line = "sep1; ['empty_col', 'RSSI']; suppress-empty-pct; 0.4"
    df_result = self.parser.parse(line, self.df.copy())
    # Row 1 should be suppressed
    self.assertNotIn(self.df.index[1], df_result.index)
    self.assertIn(self.df.index[0], df_result.index)
    self.assertIn(self.df.index[2], df_result.index)

  def test_suppress_eq(self):
    # RSSI has -34 on row 0 in test_data.csv
    line = "se1; RSSI; suppress-eq; -34"
    self.assertEqual(len(self.df), 20)
    df_result = self.parser.parse(line, self.df.copy())
    self.assertEqual(len(df_result), 18)
    self.assertNotIn(-34, df_result["RSSI"].values)

  def test_suppress_ne(self):
    # RSSI has -34 on 2 rows out of 20 in test_data.csv.
    # Suppress when RSSI is NOT -34 -> 2 rows remain.
    line = "sne1; RSSI; suppress-ne; -34"
    self.assertEqual(len(self.df), 20)
    df_result = self.parser.parse(line, self.df.copy())
    self.assertEqual(len(df_result), 2)
    self.assertTrue((df_result["RSSI"] == -34).all())

  def test_transformer_integration(self):
    directives_content = "d1; RSSI; drop\nr1; jitter_ms; rename; delay"
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
      f.write(directives_content)
      temp_dsc = f.name
    
    try:
      transformer = Transformer(self.parser)
      transformer.load_dataset(self.test_data_path)
      transformer.apply_directives(temp_dsc)
      
      df_result = transformer.df
      self.assertNotIn("RSSI", df_result.columns)
      self.assertIn("delay", df_result.columns)
      self.assertEqual(len(df_result), 20)
    finally:
      if os.path.exists(temp_dsc):
        os.remove(temp_dsc)

if __name__ == '__main__':
  unittest.main()
