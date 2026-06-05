import pandas as pd
from typing import List, Optional
import ast
from opers.directive_operation_itf import DirectiveOperationItf

class DirectiveOperationRename(DirectiveOperationItf):
  def __init__(self):
    self.new_names = []

  def set_values(self, values: List[str]):
    # values might be a single string or a list-like string
    if not values:
      return
    
    val_str = values[0].strip()
    if val_str.startswith('[') and val_str.endswith(']'):
      try:
        self.new_names = ast.literal_eval(val_str)
      except:
        self.new_names = [v.strip() for v in values]
    else:
      self.new_names = [v.strip() for v in values]

  def do_operation(self, df: pd.DataFrame, columns: List[str], mask: Optional[pd.Series] = None) -> pd.DataFrame:
    # Rename usually applies to the whole column regardless of row mask
    rename_map = {}
    for i, col in enumerate(columns):
      if i < len(self.new_names):
        rename_map[col] = self.new_names[i]
    
    return df.rename(columns=rename_map)
