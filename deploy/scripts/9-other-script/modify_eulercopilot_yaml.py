import sys
import argparse
from typing import Union

# Version marker and dependency detection
try:
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap
    USING_RUAMEL = True
except ImportError:
    try:
        import yaml  # PyYAML fallback
        USING_RUAMEL = False
    except ImportError as e:
        sys.stderr.write("Error: YAML processing library required\n")
        sys.stderr.write("Please install one of the following:\n")
        sys.stderr.write("1. (Recommended) ruamel.yaml: pip install ruamel.yaml\n")
        sys.stderr.write("2. PyYAML: pip install PyYAML\n")
        sys.exit(1)

def parse_value(value: str) -> Union[str, int, float, bool]:
    """Intelligently convert value types"""
    value = value.strip()
    lower_val = value.lower()

    if lower_val in {'true', 'false'}:
        return lower_val == 'true'
    if lower_val in {'null', 'none'}:
        return None

    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            pass

    # Handle quoted strings
    if len(value) > 1 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]

    return value

def set_nested_value(data: dict, key_path: str, value: str) -> None:
    """Recursively set nested dictionary values"""
    keys = key_path.split('.')
    current = data

    try:
        for key in keys[:-1]:
            # Automatically create missing levels
            if key not in current:
                current[key] = CommentedMap() if USING_RUAMEL else {}
            current = current[key]

        final_key = keys[-1]
        current[final_key] = parse_value(value)
    except TypeError as e:
        raise ValueError(f"Non-dictionary type intermediate node found in path {key_path}") from e

def main():
    parser = argparse.ArgumentParser(
        description='YAML configuration file modification tool',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('input', help='Input YAML file path')
    parser.add_argument('output', help='Output YAML file path')
    parser.add_argument('--set',
                       action='append',
                       required=True,
                       help='Format: path.to.key=value (can be used multiple times)',
                       metavar='KEY_PATH=VALUE')

    args = parser.parse_args()

    # Initialize YAML processor
    if USING_RUAMEL:
        yaml_processor = YAML()
        yaml_processor.preserve_quotes = True
        yaml_processor.indent(mapping=2, sequence=4, offset=2)
    else:
        yaml_processor = yaml  # Use PyYAML module

    # Read file (corrected section)
    try:
        with open(args.input, 'r') as f:  # Ensure this line is properly closed
            if USING_RUAMEL:
                data = yaml_processor.load(f)
            else:
                data = yaml.safe_load(f)
    except Exception as e:
        raise SystemExit(f"Failed to read file: {str(e)}")

    # Process modification parameters
    for item in args.set:
        if '=' not in item:
            raise ValueError(f"Invalid format: {item}, should use KEY_PATH=VALUE format")

        key_path, value = item.split('=', 1)
        if not key_path:
            raise ValueError("Key path cannot be empty")

        try:
            set_nested_value(data, key_path, value)
        except Exception as e:
            raise SystemExit(f"Error setting {key_path}: {str(e)}")

    # Write file
    try:
        with open(args.output, 'w') as f:
            if USING_RUAMEL:
                yaml_processor.dump(data, f)
            else:
                yaml.dump(data, f, default_flow_style=False, indent=2)
    except Exception as e:
        raise SystemExit(f"Failed to write file: {str(e)}")

if __name__ == '__main__':
    main()
