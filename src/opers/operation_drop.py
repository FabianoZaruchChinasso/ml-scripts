import pandas as pd
from typing import List, Optional
from opers.directive_operation_itf import DirectiveOperationItf

class DirectiveOperationDrop(DirectiveOperationItf):
  def set_values(self, values: List[str]):
    # Drop doesn't usually require extra values
    pass

  def do_operation(self, df: pd.DataFrame, columns: List[str], mask: Optional[pd.Series] = None) -> pd.DataFrame:
    # If a mask is provided, we can't 'drop' the column only for specific rows.
    # We drop the column entirely from the dataset.
    return df.drop(columns=columns, errors='ignore')
