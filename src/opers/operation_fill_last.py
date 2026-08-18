import pandas as pd
import logging
from typing import List, Optional
from opers.directive_operation_itf import DirectiveOperationItf

class DirectiveOperationFillLast(DirectiveOperationItf):
  def __init__(self):
    self.fill_value = 0.0
    self.group_column: Optional[str] = None
    self.group_name: Optional[str] = None

  def set_values(self, values: List[str]):
    self.fill_value = 0.0
    self.group_column = None
    self.group_name = None
    if not values:
      return

    if len(values) >= 2:
      self.group_column = values[0].strip().strip('"').strip("'")
      self.group_name = values[1].strip().strip('"').strip("'")
      if len(values) >= 3:
        try:
          self.fill_value = float(values[2])
        except ValueError:
          self.fill_value = values[2]
      return

    single_value = values[0].strip()
    if '::' in single_value:
      group_parts = single_value.split('::', 1)
      self.group_column = group_parts[0].strip().strip('"').strip("'")
      self.group_name = group_parts[1].strip().strip('"').strip("'")
      return

    try:
      self.fill_value = float(values[0])
    except ValueError:
      self.fill_value = values[0]

  def _build_group_mask(self, df: pd.DataFrame) -> Optional[pd.Series]:
    if self.group_column is None or self.group_name is None:
      return None
    if self.group_column not in df.columns:
      logging.warning(f"Column ['{self.group_column}'] not found in dataset for fill-last group filter. Skipping grouped fill.")
      return pd.Series(False, index=df.index)

    col = df[self.group_column]
    if pd.api.types.is_numeric_dtype(col):
      try:
        group_val = float(self.group_name)
        return col == group_val
      except ValueError:
        pass

    return col.astype(str) == str(self.group_name)

  def do_operation(self, df: pd.DataFrame, columns: List[str], mask: Optional[pd.Series] = None) -> pd.DataFrame:
    group_mask = self._build_group_mask(df)

    for col in columns:
      if col in df.columns:
        if group_mask is None:
          filled = df[col].ffill().fillna(self.fill_value)
          if mask is not None:
            nan_mask = df[col].isna() & mask
            df.loc[nan_mask, col] = filled.loc[nan_mask]
          else:
            df[col] = filled
        else:
          group_filled = df.loc[group_mask, col].ffill().fillna(self.fill_value)
          if mask is not None:
            nan_mask = df[col].isna() & mask & group_mask
            df.loc[nan_mask, col] = group_filled.loc[nan_mask]
          else:
            nan_mask = df[col].isna() & group_mask
            df.loc[nan_mask, col] = group_filled.loc[nan_mask]
    return df
