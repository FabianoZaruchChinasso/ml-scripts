import argparse
import logging
import sys
from opers.operation_parser import OperationParser
from transformer import Transformer
from opers.operation_drop import DirectiveOperationDrop
from opers.operation_rename import DirectiveOperationRename
from opers.operation_scale import DirectiveOperationScale
from opers.operation_normalize import DirectiveOperationNormalize
from opers.operation_multiply import DirectiveOperationMultiply
from opers.operation_subst_same import DirectiveOperationSubstSame
from opers.operation_subst_contains import DirectiveOperationSubstContains
from opers.operation_if_greater import DirectiveOperationIfGreater
from opers.operation_if_less import DirectiveOperationIfLess
from opers.operation_if_equal import DirectiveOperationIfEqual
from opers.operation_if_notequal import DirectiveOperationIfNotequal
from opers.operation_fill_empty import DirectiveOperationFillEmpty
from opers.operation_math import DirectiveOperationMath

def setup_parser():
  parser = OperationParser()
  parser.add_operation('drop', DirectiveOperationDrop())
  parser.add_operation('rename', DirectiveOperationRename())
  parser.add_operation('scale', DirectiveOperationScale())
  parser.add_operation('normalize', DirectiveOperationNormalize())
  parser.add_operation('multiply', DirectiveOperationMultiply())
  parser.add_operation('subst-same', DirectiveOperationSubstSame())
  parser.add_operation('subst-contains', DirectiveOperationSubstContains())
  parser.add_operation('if-greater', DirectiveOperationIfGreater())
  parser.add_operation('if-less', DirectiveOperationIfLess())
  parser.add_operation('if-equal', DirectiveOperationIfEqual())
  parser.add_operation('if-notequal', DirectiveOperationIfNotequal())
  parser.add_operation('fill-empty', DirectiveOperationFillEmpty())
  parser.add_operation('math', DirectiveOperationMath())
  return parser

def main():
  logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
  
  arg_parser = argparse.ArgumentParser(description="Filter and normalize metrics dataset.")
  arg_parser.add_argument("-i", "--input", required=True, help="Input CSV file")
  arg_parser.add_argument("-o", "--output", required=True, help="Output CSV file")
  arg_parser.add_argument("-d", "--directives", required=True, help="Directives file (fn.dsc)")
  args = arg_parser.parse_args()

  op_parser = setup_parser()
  transformer = Transformer(op_parser)

  try:
    transformer.load_dataset(args.input)
    transformer.apply_directives(args.directives)
    
    should_save = True
    if transformer.has_skipped_directives():
      logging.warning("Some directives were skipped due to errors.")
      response = input("Do you want to save the output file anyway? (y/n): ").strip().lower()
      if response != 'y':
        should_save = False
        logging.info("Output file saving cancelled by user.")
    
    if should_save:
      transformer.save_dataset(args.output)
      print(f"Successfully processed {args.input} -> {args.output}")

  except Exception as e:
    logging.error(f"An error occurred: {e}")
    sys.exit(1)

if __name__ == "__main__":
  main()
