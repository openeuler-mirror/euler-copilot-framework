import sys
import argparse
from typing import Union

# 版本标记和依赖检测
try:
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap
    USING_RUAMEL = True
except ImportError:
    try:
        import yaml  # PyYAML 回退
        USING_RUAMEL = False
    except ImportError as e:
        sys.stderr.write("错误：需要 YAML 处理库\n")
        sys.stderr.write("请选择以下方式之一安装：\n")
        sys.stderr.write("1. (推荐) ruamel.yaml: pip install ruamel.yaml\n")
        sys.stderr.write("2. PyYAML: pip install PyYAML\n")
        sys.exit(1)

def parse_value(value: str) -> Union[str, int, float, bool]:
    """智能转换值的类型"""
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
    
    # 处理引号包裹的字符串
    if len(value) > 1 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    
    return value

def set_nested_value(data: dict, key_path: str, value: str) -> None:
    """递归设置嵌套字典的值"""
    keys = key_path.split('.')
    current = data
    
    try:
        for key in keys[:-1]:
            # 自动创建不存在的层级
            if key not in current:
                current[key] = CommentedMap() if USING_RUAMEL else {}
            current = current[key]
        
        final_key = keys[-1]
        current[final_key] = parse_value(value)
    except TypeError as e:
        raise ValueError(f"路径 {key_path} 中存在非字典类型的中间节点") from e

def main():
    parser = argparse.ArgumentParser(
        description='YAML 配置文件修改工具',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('input', help='输入YAML文件路径')
    parser.add_argument('output', help='输出YAML文件路径')
    parser.add_argument('--set', 
                       action='append',
                       required=True,
                       help='格式: path.to.key=value (可多次使用)',
                       metavar='KEY_PATH=VALUE')

    args = parser.parse_args()

    # 初始化 YAML 处理器
    if USING_RUAMEL:
        yaml_processor = YAML()
        yaml_processor.preserve_quotes = True
        yaml_processor.indent(mapping=2, sequence=4, offset=2)
    else:
        yaml_processor = yaml  # 使用 PyYAML 模块

    # 读取文件（修正后的部分）
    try:
        with open(args.input, 'r') as f:  # 确保这行正确闭合
            if USING_RUAMEL:
                data = yaml_processor.load(f)
            else:
                data = yaml.safe_load(f)
    except Exception as e:
        raise SystemExit(f"读取文件失败: {str(e)}")

    # 处理修改参数
    for item in args.set:
        if '=' not in item:
            raise ValueError(f"无效格式: {item}，应使用 KEY_PATH=VALUE 格式")
        
        key_path, value = item.split('=', 1)
        if not key_path:
            raise ValueError("键路径不能为空")
        
        try:
            set_nested_value(data, key_path, value)
        except Exception as e:
            raise SystemExit(f"设置 {key_path} 时出错: {str(e)}")

    # 写入文件
    try:
        with open(args.output, 'w') as f:
            if USING_RUAMEL:
                yaml_processor.dump(data, f)
            else:
                yaml.dump(data, f, default_flow_style=False, indent=2)
    except Exception as e:
        raise SystemExit(f"写入文件失败: {str(e)}")

if __name__ == '__main__':
    main()
