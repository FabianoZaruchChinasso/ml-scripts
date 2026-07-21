import pandas as pd
import numpy as np
import ast
import logging
from typing import List, Optional
from opers.directive_operation_itf import DirectiveOperationItf

class DirectiveOperationMath(DirectiveOperationItf):
  def __init__(self):
    self.formulas: List[str] = []

  def _eval_arithmetic_expression(self, expression: str):
    def _eval(node):
      if isinstance(node, ast.Expression):
        return _eval(node.body)
      if isinstance(node, ast.Constant):
        return node.value
      if isinstance(node, ast.BinOp):
        left = _eval(node.left)
        right = _eval(node.right)
        if isinstance(node.op, ast.Add):
          return left + right
        if isinstance(node.op, ast.Sub):
          return left - right
        if isinstance(node.op, ast.Mult):
          return left * right
        if isinstance(node.op, ast.Div):
          return left / right
        if isinstance(node.op, ast.FloorDiv):
          return left // right
        if isinstance(node.op, ast.Mod):
          return left % right
        if isinstance(node.op, ast.Pow):
          return left ** right
      if isinstance(node, ast.UnaryOp):
        value = _eval(node.operand)
        if isinstance(node.op, ast.UAdd):
          return +value
        if isinstance(node.op, ast.USub):
          return -value
      raise ValueError(f"Unsupported arithmetic expression: {expression}")

    tree = ast.parse(expression, mode='eval')
    return _eval(tree)

  def set_values(self, values: List[str]):
    # values comes from op_values which was split by ',' in OperationParser
    self.formulas = values

  def do_operation(self, df: pd.DataFrame, columns: List[str], mask: Optional[pd.Series] = None) -> pd.DataFrame:
    if not self.formulas:
      for col in columns:
        if col not in df.columns:
          continue

        target_index = df.index if mask is None else df.index[mask]
        for idx in target_index:
          value = df.at[idx, col]
          if pd.isna(value) or not isinstance(value, str):
            continue

          expression = value.strip()
          if not expression:
            continue

          try:
            df.at[idx, col] = self._eval_arithmetic_expression(expression)
          except Exception as e:
            logging.error(f"Failed to evaluate arithmetic expression '{expression}' in column '{col}' at index '{idx}': {e}")

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
