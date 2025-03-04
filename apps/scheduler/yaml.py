"""YAML表示器"""

def str_presenter(dumper, data):  # noqa: ANN001, ANN201, D103
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)
