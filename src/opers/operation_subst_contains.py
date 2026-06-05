import pandas as pd
from typing import List, Optional
from opers.directive_operation_itf import DirectiveOperationItf

class DirectiveOperationSubstContains(DirectiveOperationItf):
  def __init__(self):
    self.match_str = ""
    self.replace_val = 1.0
    self.fallback_val = 0.0
    self.has_fallback = False

  def set_values(self, values: List[str]):
    self.has_fallback = len(values) >= 3
    if len(values) >= 1:
      self.match_str = values[0].strip().strip('"').strip("'")
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
        is_match = (df[col].astype(str).str.contains(self.match_str, na=False)) & target_mask
        is_fallback = (~df[col].astype(str).str.contains(self.match_str, na=False)) & target_mask
        
        df.loc[is_match, col] = self.replace_val

        if self.has_fallback:
          df.loc[is_fallback, col] = self.fallback_val

        # Attempt to convert back to numeric if possible
        try:
          df[col] = pd.to_numeric(df[col])
        except (ValueError, TypeError):
          pass
    return df

