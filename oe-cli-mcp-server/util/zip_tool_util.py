import os
import zipfile
import logging
from typing import Optional
import shutil

from util.get_project_root import get_project_root

# 全局目标目录（转为绝对路径，避免相对路径混乱）
target_dir = os.path.join(get_project_root(),"mcp_tools/personal_tools/")

def clean_zip_extract_dir(dir_path: str) -> None:
    """清理指定目录（递归删除，确保无残留）"""
    if not os.path.exists(dir_path):
        return
    try:
        shutil.rmtree(dir_path)
        logging.info(f"已清理旧目录：{dir_path}")
    except Exception as e:
        logging.error(f"清理目录 {dir_path} 失败：{e}")
        raise  # 清理失败终止解压，避免残留干扰

def unzip_tool(zip_path: str, extract_to: Optional[str] = None) -> bool:
    """
    解压工具包到指定目录（仅一层路径，无嵌套）
    :param zip_path: 工具包zip文件路径（相对/绝对路径）
    :param extract_to: 解压目标目录（可选），默认 target_dir
    :return: 解压是否成功
    """
    # 1. 基础校验：ZIP文件是否存在
    if not os.path.exists(zip_path):
        logging.error(f"错误：工具包文件 {zip_path} 不存在。")
        return False
    
    # 2. 确定最终解压根目录（默认 target_dir，支持自定义）
    extract_root_dir = os.path.abspath(extract_to) if extract_to else target_dir
    
    # 3. 提取ZIP文件名（无后缀），作为最终的「一层路径」名称
    zip_filename = os.path.basename(zip_path)
    final_extract_dir = os.path.join(extract_root_dir, os.path.splitext(zip_filename)[0])
    
    # 4. 清理旧目录（若已存在，避免文件冲突）
    if os.path.exists(final_extract_dir):
        clean_zip_extract_dir(final_extract_dir)
    
    # 5. 创建最终解压目录（确保父目录存在）
    try:
        os.makedirs(final_extract_dir, exist_ok=True)
        logging.info(f"已创建解压目录：{final_extract_dir}")
    except PermissionError as e:
        logging.error(f"错误：创建目录 {final_extract_dir} 权限不足：{e}")
        return False
    except Exception as e:
        logging.error(f"错误：创建目录 {final_extract_dir} 失败：{e}")
        return False
    
    # 6. 核心逻辑：解压并跳过ZIP内部顶层目录，直接提取内容到最终目录
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # 获取ZIP内部所有文件的路径
            zip_file_list = zip_ref.namelist()
            if not zip_file_list:
                logging.error(f"错误：ZIP文件 {zip_path} 为空。")
                clean_zip_extract_dir(final_extract_dir)
                return False
            
            # 找到ZIP内部的顶层目录（假设压缩时是「文件夹+内容」，顶层目录唯一）
            # 例如：ZIP内部路径是「custom_gpu_tool/xxx.py」，顶层目录就是「custom_gpu_tool/」
            top_level_dirs = set()
            for file_path in zip_file_list:
                # 分割路径，取第一级目录（如「custom_gpu_tool/xxx.py」→ 「custom_gpu_tool」）
                top_level = file_path.split(os.sep)[0]
                if top_level:  # 排除空路径（避免异常）
                    top_level_dirs.add(top_level)
            
            # 处理两种情况：ZIP内部有顶层目录 / 无顶层目录（直接是文件）
            if len(top_level_dirs) == 1:
                # 情况1：有唯一顶层目录（大多数Linux zip压缩的情况）
                top_dir = next(iter(top_level_dirs)) + os.sep  # 拼接路径分隔符（如「custom_gpu_tool/」）
                for file_path in zip_file_list:
                    # 跳过顶层目录本身（只提取其下内容）
                    if file_path == top_dir:
                        continue
                    # 构建目标路径：去掉顶层目录前缀，直接放到 final_extract_dir 下
                    target_file_path = os.path.join(final_extract_dir, file_path[len(top_dir):])
                    # 创建目标文件的父目录（避免因子目录不存在报错）
                    os.makedirs(os.path.dirname(target_file_path), exist_ok=True)
                    # 提取文件并写入目标路径
                    with zip_ref.open(file_path) as source, open(target_file_path, 'wb') as target:
                        shutil.copyfileobj(source, target)
                    logging.debug(f"已提取：{file_path} → {target_file_path}")
            else:
                # 情况2：ZIP内部无顶层目录（直接是文件/多个子目录），直接提取所有内容
                zip_ref.extractall(path=final_extract_dir)
                logging.debug(f"ZIP无统一顶层目录，直接提取所有内容到 {final_extract_dir}")
        
        logging.info(f"成功：文件 {zip_path} 已解压到 {final_extract_dir}（仅一层路径）")
        return True
    
    except zipfile.BadZipFile:
        logging.error(f"错误：文件 {zip_path} 不是有效的ZIP文件。")
    except PermissionError as e:
        logging.error(f"错误：解压权限不足（目标目录不可写或文件被占用）：{e}")
    except Exception as e:
        logging.error(f"错误：解压文件 {zip_path} 时发生异常：{e}")
    
    # 解压失败，清理临时目录
    clean_zip_extract_dir(final_extract_dir)
    return False

# 示例调用
if __name__ == "__main__":
    # 配置日志（按需调整级别）
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # 测试：解压 custom_gpu_tool.zip，最终路径为 mcp_tools/personal_tools/custom_gpu_tool/xxx
    result = unzip_tool(zip_path="/home/tsn/cli_mcp_server/test_tool.zip")
    print(f"解压结果：{'成功' if result else '失败'}")