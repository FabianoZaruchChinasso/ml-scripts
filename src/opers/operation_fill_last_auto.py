import logging
import pandas as pd
from typing import List, Optional
from opers.directive_operation_itf import DirectiveOperationItf

class DirectiveOperationFillLastAuto(DirectiveOperationItf):
  def __init__(self):
    self.group_column: Optional[str] = None

  def set_values(self, values: List[str]):
    self.group_column = None
    if values:
      self.group_column = values[0].strip().strip('"').strip("'")

  def do_operation(self, df: pd.DataFrame, columns: List[str], mask: Optional[pd.Series] = None) -> pd.DataFrame:
    if self.group_column is None or not self.group_column:
      logging.warning("fill-last-auto requires a group column in values. Skipping operation.")
      return df

    if self.group_column not in df.columns:
      logging.warning(f"Column ['{self.group_column}'] not found in dataset for fill-last-auto. Skipping operation.")
      return df

    target_mask = mask if mask is not None else pd.Series(True, index=df.index)

    for col in columns:
      if col in df.columns:
        grouped_filled = df.groupby(self.group_column, dropna=False)[col].ffill().fillna(0.0)
        nan_mask = df[col].isna() & target_mask
        df.loc[nan_mask, col] = grouped_filled.loc[nan_mask]
    return df
