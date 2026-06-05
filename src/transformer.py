import pandas as pd
import logging
from opers.operation_parser import OperationParser

class Transformer:
  def __init__(self, parser: OperationParser):
    self.parser = parser
    self.df = None

  def load_dataset(self, csv_path: str):
    try:
      self.df = pd.read_csv(csv_path)
      logging.info(f"Loaded dataset from {csv_path} with {len(self.df)} rows.")
    except Exception as e:
      logging.error(f"Failed to load dataset: {e}")
      raise

  def apply_directives(self, dsc_path: str):
    if self.df is None:
      logging.error("No dataset loaded.")
      return

    try:
      with open(dsc_path, 'r') as f:
        for line in f:
          line = line.strip()
          if not line or line.startswith('#'):
            continue
          self.df = self.parser.parse(line, self.df)
    except Exception as e:
      logging.error(f"Error processing directives file {dsc_path}: {e}")
      raise

  def save_dataset(self, output_path: str):
    if self.df is None:
      logging.error("No dataset to save.")
      return

    try:
      self.df.to_csv(output_path, index=False)
      logging.info(f"Saved transformed dataset to {output_path}")
    except Exception as e:
      logging.error(f"Failed to save dataset: {e}")
      raise

  def has_skipped_directives(self) -> bool:
    return self.parser.skipped_any
