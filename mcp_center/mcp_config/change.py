import json
import toml

def json_to_toml(json_data, toml_file_path, top_level_key="data"):
    """
    将JSON数据转换为TOML格式并写入文件
    
    参数:
        json_data: JSON数据，可以是字典、列表或JSON字符串
        toml_file_path: 输出的TOML文件路径
        top_level_key: 当输入为列表时，用于包装列表的顶级键名
    """
    try:
        # 如果输入是JSON字符串，则先解析为Python对象
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data
        
        # TOML不支持顶级列表，需要包装在字典中
        if isinstance(data, list):
            data = {top_level_key: data}
        
        # 将数据转换为TOML格式并写入文件
        with open(toml_file_path, 'w', encoding='utf-8') as f:
            toml.dump(data, f)
        
        print(f"成功将JSON数据转换为TOML并写入文件: {toml_file_path}")
        return True
    
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
    except Exception as e:
        print(f"转换过程中发生错误: {e}")
    return False

if __name__ == "__main__":
    # 示例JSON数据（列表形式）
    sample_json = [
        {
            "appType":"agent",
            "name":"hce运维助手",
            "description":"hce运维助手,用于诊断hce环境和执行shell命令",
            "mcpPath":[
                "remote_info_mcp",
                "shell_generator_mcp"
            ],
            "published":True
        }
    ]
    
    # 转换并写入TOML文件
    # 对于列表数据，指定一个顶级键名（如"applications"）使其符合TOML格式要求
    json_to_toml(sample_json, "mcp_to_app_config.toml", "applications")
    
    # 测试字典类型的JSON数据
    dict_json = {
        "name": "测试", 
        "version": "1.0.0",
        "features": ["简单", "易用"]
    }
    json_to_toml(dict_json, "from_dict.toml")
    
    # 测试JSON字符串
    json_str = '{"name": "字符串测试", "version": "2.0.0"}'
    json_to_toml(json_str, "from_string.toml")
    