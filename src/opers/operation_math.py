import pandas as pd
import numpy as np
from typing import List, Optional
from opers.directive_operation_itf import DirectiveOperationItf

class DirectiveOperationMath(DirectiveOperationItf):
  def __init__(self):
    self.formulas: List[str] = []

  def set_values(self, values: List[str]):
    # values comes from op_values which was split by ',' in OperationParser
    self.formulas = values

  def do_operation(self, df: pd.DataFrame, columns: List[str], mask: Optional[pd.Series] = None) -> pd.DataFrame:
    if not self.formulas:
      return df
    
    # We might have one formula per column or one formula for multiple columns (unlikely but possible)
    # Most common use case: columns=['new_col'], formulas=['col1 + col2']
    # Or: columns=['c1', 'c2'], formulas=['a+b', 'c*d']
    
    for i, col in enumerate(columns):
      if i < len(self.formulas):
        formula = self.formulas[i]
        try:
          # Evaluate formula
          result = df.eval(formula)
          
          # Initialize column if it doesn't exist
          if col not in df.columns:
            df[col] = np.nan
            
          if mask is not None:
            df.loc[mask, col] = result
          else:
            df[col] = result
        except Exception as e:
          import logging
          logging.error(f"Failed to evaluate math formula '{formula}' for column '{col}': {e}")
          
    return df
