import pandas as pd
from typing import List, Optional
from opers.directive_operation_itf import DirectiveOperationItf

class DirectiveOperationSubstSame(DirectiveOperationItf):
  def __init__(self):
    self.match_val = ""
    self.match_num = None
    self.replace_val = 1.0
    self.fallback_val = 0.0
    self.has_fallback = False

  def set_values(self, values: List[str]):
    self.has_fallback = len(values) >= 3
    self.match_num = None
    if len(values) >= 1:
      self.match_val = values[0].strip().strip('"').strip("'")
      try:
        self.match_num = float(self.match_val)
      except ValueError:
        self.match_num = None
    if len(values) >= 2:
      try:
        self.replace_val = float(values[1])
      except ValueError:
        self.replace_val = values[1].strip().strip('"').strip("'")
    if self.has_fallback:
      try:
        self.fallback_val = float(values[2])
      except ValueError:
        self.fallback_val = values[2].strip().strip('"').strip("'")

  def do_operation(self, df: pd.DataFrame, columns: List[str], mask: Optional[pd.Series] = None) -> pd.DataFrame:
    for col in columns:
      if col in df.columns:
        # Convert column to object type to allow mixed/numeric replacement without type errors
        df[col] = df[col].astype(object)
        
        target_mask = mask if mask is not None else pd.Series(True, index=df.index)
        
        # Calculate masks before modifying the column
        if self.match_num is not None:
          numeric_col = pd.to_numeric(df[col], errors='coerce')
          is_match = (numeric_col == self.match_num) & target_mask
        else:
          is_match = (df[col].astype(str) == self.match_val) & target_mask
        is_fallback = (df[col].astype(str) != self.match_val) & target_mask

        if self.has_fallback and self.match_num is not None:
          is_fallback = (~is_match) & target_mask
        
        df.loc[is_match, col] = self.replace_val

        if self.has_fallback:
          df.loc[is_fallback, col] = self.fallback_val
        
        # Attempt to convert back to numeric if possible (only if everything is numeric now)
        try:
          df[col] = pd.to_numeric(df[col])
        except (ValueError, TypeError):
          pass
    return df
