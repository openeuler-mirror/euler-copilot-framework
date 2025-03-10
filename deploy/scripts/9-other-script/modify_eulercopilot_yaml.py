import argparse
import subprocess
import sys

# 尝试导入 YAML 库
try:
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap

    USING_RUAMEL = True
except ImportError:
    try:
        import yaml as pyyaml  # 回退到 PyYAML

        USING_RUAMEL = False
    except ImportError:
        print("未检测到 YAML 处理库，正在自动安装 ruamel.yaml...")
        try:
            # 优先尝试安装 ruamel.yaml
            subprocess.check_call([sys.executable, "-m", "pip", "install", "ruamel.yaml"])
            from ruamel.yaml import YAML
            from ruamel.yaml.comments import CommentedMap

            USING_RUAMEL = True
            print("ruamel.yaml 安装成功")
        except Exception as e:
            print(f"安装 ruamel.yaml 失败: {e}, 改为尝试安装 PyYAML")
            try:
                # 回退安装 PyYAML
                subprocess.check_call([sys.executable, "-m", "pip", "install", "PyYAML"])
                import yaml as pyyaml

                USING_RUAMEL = False
                print("PyYAML 安装成功")
            except Exception as e:
                print(f"安装 PyYAML 也失败: {e}")
                sys.exit(1)


def parse_value(value):
    """智能转换值的类型"""
    value = value.strip()
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            pass
    return value


def set_nested_value(data, key_path, value):
    """递归设置嵌套字典的值"""
    keys = key_path.split(".")
    current = data
    for key in keys[:-1]:
        if key not in current:
            # 根据可用库选择适当的字典类型
            current[key] = CommentedMap() if USING_RUAMEL else {}
        current = current[key]
    current[keys[-1]] = parse_value(value)


def main():
    parser = argparse.ArgumentParser(description="YAML字段修改工具")
    parser.add_argument("input", help="输入YAML文件路径")
    parser.add_argument("output", help="输出YAML文件路径")
    parser.add_argument("--set", action="append", help="格式: path.to.key=value (可多次使用)", metavar="KEY_PATH=VALUE")

    args = parser.parse_args()

    if USING_RUAMEL:
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.indent(mapping=2, sequence=4, offset=2)
    else:
        yaml = pyyaml  # 使用PyYAML模块

    # 读取YAML文件
    with open(args.input, "r") as f:
        if USING_RUAMEL:
            data = yaml.load(f)
        else:
            data = yaml.safe_load(f)

    # 处理所有--set参数
    if args.set:
        for item in args.set:
            if "=" not in item:
                raise ValueError(f"Invalid format: {item}. Use KEY_PATH=VALUE")
            key_path, value = item.split("=", 1)
            set_nested_value(data, key_path, value)

    # 写入修改后的YAML
    with open(args.output, "w") as f:
        if USING_RUAMEL:
            yaml.dump(data, f)
        else:
            # PyYAML的缩进设置
            yaml.dump(data, f, default_flow_style=False, indent=2)


if __name__ == "__main__":
    main()
