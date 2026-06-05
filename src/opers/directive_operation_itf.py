import pandas as pd
from typing import List, Optional

class DirectiveOperationItf:
  def set_values(self, values: List[str]):
    raise NotImplementedError

  def do_operation(self, df: pd.DataFrame, columns: List[str], mask: Optional[pd.Series] = None) -> pd.DataFrame:
    raise NotImplementedError
