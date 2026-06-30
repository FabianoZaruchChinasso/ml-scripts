import pandas as pd
import logging
import ast
from typing import Dict, List, Optional
from opers.directive_operation_itf import DirectiveOperationItf

class OperationParser:
  def __init__(self):
    self.operations: Dict[str, DirectiveOperationItf] = {}
    self.active_mask: Optional[pd.Series] = None
    self.last_if_mask: Optional[pd.Series] = None
    self.skipped_any = False

  def add_operation(self, name: str, operation_obj: DirectiveOperationItf):
    self.operations[name] = operation_obj

  def parse(self, line: str, df: pd.DataFrame) -> pd.DataFrame:
    if not line or line.strip().startswith('#') or ';' not in line:
      return df

    parts = [p.strip() for p in line.split(';')]
    if len(parts) < 3:
      return df

    directive_name = parts[0]
    data_field = parts[1]
    op_name = parts[2]
    op_values = parts[3].split(',') if len(parts) > 3 else []
    op_values = [v.strip() for v in op_values if v.strip()]

    # Parse data_field (column name or list)
    columns = []
    if data_field.startswith('[') and data_field.endswith(']'):
      try:
        columns = ast.literal_eval(data_field)
      except:
        columns = [data_field]
    else:
      columns = [data_field]

    # Handle 'else' separately as it's a flow control, not a standard operation in the map
    if op_name == 'else':
      if self.last_if_mask is not None:
        self.active_mask = ~self.last_if_mask
      else:
        logging.warning("Found 'else' without preceding 'if' operation.")
      return df

    if op_name not in self.operations:
      logging.warning(f"Unknown operation: {op_name}. Skipping directive '{directive_name}'.")
      self.skipped_any = True
      return df

    op_obj = self.operations[op_name]
    
    # Check if columns exist (except for rename where they might be about to change, 
    # but we still need the old ones to exist; and math which creates new columns)
    missing_cols = [c for c in columns if c not in df.columns]
    if missing_cols and op_name not in ['rename', 'math']:
      logging.warning(f"Columns {missing_cols} not found in dataset. Skipping directive '{directive_name}'.")
      self.skipped_any = True
      return df

    logging.info(f"Applying {directive_name} over {columns} for {op_name} with {op_values}")
    
    op_obj.set_values(op_values)

    # Check if it's an IF operation
    if op_name.startswith('if-'):
      # get_mask is expected to exist for IF operations
      if hasattr(op_obj, 'get_mask'):
        self.active_mask = op_obj.get_mask(df, columns, None) # IF usually starts a fresh condition
        self.last_if_mask = self.active_mask
      return df
    else:
      # Regular operation
      df = op_obj.do_operation(df, columns, self.active_mask)
      # Reset mask after one operation unless it's an IF/ELSE sequence?
      # Spec says: "The directive immediately following an if is applied only to the rows where the mask is True."
      # This implies we should probably reset the mask after applying that "next" directive.
      self.active_mask = None
      return df
