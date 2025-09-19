"""
文件变量处理的通用辅助函数

提供统一的文件变量数据访问接口，确保新旧格式的兼容性
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FileVariableHelper:
    """文件变量处理辅助类 - 提供新旧格式兼容的统一接口"""
    
    @staticmethod
    def get_file_id(variable_value: Dict[str, Any]) -> Optional[str]:
        """
        从单文件变量中获取file_id
        
        :param variable_value: 变量值字典
        :return: 文件ID，如果不存在则返回None
        """
        if not isinstance(variable_value, dict):
            return None
        
        return variable_value.get("file_id")
    
    @staticmethod
    def get_file_ids(variable_value: Dict[str, Any]) -> List[str]:
        """
        从文件数组变量中获取file_ids列表
        
        :param variable_value: 变量值字典
        :return: 文件ID列表
        """
        if not isinstance(variable_value, dict):
            return []
        
        # 优先从file_ids字段获取
        file_ids = variable_value.get("file_ids", [])
        
        # 🔧 兼容性处理：如果file_ids为空，尝试从files数组中提取
        if not file_ids:
            files = variable_value.get("files", [])
            if isinstance(files, list):
                file_ids = [
                    file_info.get("file_id") 
                    for file_info in files 
                    if isinstance(file_info, dict) and file_info.get("file_id")
                ]
                if file_ids:
                    logger.debug(f"从files数组中提取到file_ids: {file_ids}")
        
        return file_ids
    
    @staticmethod
    def get_filename_by_file_id(variable_value: Dict[str, Any], file_id: str) -> Optional[str]:
        """
        根据file_id从变量中获取对应的文件名
        
        :param variable_value: 变量值字典
        :param file_id: 文件ID
        :return: 文件名，如果不存在则返回None
        """
        if not isinstance(variable_value, dict):
            return None
        
        # 单文件变量：直接获取filename字段
        if variable_value.get("file_id") == file_id:
            return variable_value.get("filename")
        
        # 文件数组变量：从files数组中查找匹配的file_id
        files = variable_value.get("files", [])
        if isinstance(files, list):
            for file_info in files:
                if isinstance(file_info, dict) and file_info.get("file_id") == file_id:
                    return file_info.get("filename")
        
        return None
    
    @staticmethod
    def get_all_filenames(variable_value: Dict[str, Any]) -> Dict[str, str]:
        """
        获取变量中所有文件的ID和文件名映射
        
        :param variable_value: 变量值字典
        :return: {file_id: filename} 映射字典
        """
        if not isinstance(variable_value, dict):
            return {}
        
        result = {}
        
        # 单文件变量
        file_id = variable_value.get("file_id")
        filename = variable_value.get("filename")
        if file_id and filename:
            result[file_id] = filename
        
        # 文件数组变量
        files = variable_value.get("files", [])
        if isinstance(files, list):
            for file_info in files:
                if isinstance(file_info, dict):
                    fid = file_info.get("file_id")
                    fname = file_info.get("filename")
                    if fid and fname:
                        result[fid] = fname
        
        return result
    
    @staticmethod
    def validate_file_variable_consistency(variable_value: Dict[str, Any], var_type: str) -> Tuple[bool, str]:
        """
        验证文件变量数据的一致性
        
        :param variable_value: 变量值字典
        :param var_type: 变量类型 (FILE 或 ARRAY_FILE)
        :return: (是否一致, 错误信息)
        """
        if not isinstance(variable_value, dict):
            return False, "变量值不是字典格式"
        
        if var_type == "FILE":
            # 单文件变量验证
            file_id = variable_value.get("file_id")
            if not file_id:
                return False, "单文件变量缺少file_id"
            
            # filename是可选的，但如果存在应该是字符串
            filename = variable_value.get("filename")
            if filename is not None and not isinstance(filename, str):
                return False, "filename字段应该是字符串类型"
                
        elif var_type == "ARRAY_FILE":
            # 文件数组变量验证
            file_ids = variable_value.get("file_ids", [])
            files = variable_value.get("files", [])
            
            if not isinstance(file_ids, list):
                return False, "file_ids应该是列表类型"
            
            if not isinstance(files, list):
                return False, "files应该是列表类型"
            
            # 如果两个都存在，长度应该一致
            if files and len(file_ids) != len(files):
                return False, f"file_ids长度({len(file_ids)})与files长度({len(files)})不一致"
            
            # 验证files数组中的每个元素
            for i, file_info in enumerate(files):
                if not isinstance(file_info, dict):
                    return False, f"files[{i}]不是字典格式"
                
                if not file_info.get("file_id"):
                    return False, f"files[{i}]缺少file_id"
                
                if not file_info.get("filename"):
                    return False, f"files[{i}]缺少filename"
            
            # 验证file_ids和files中的file_id是否匹配
            if files:
                files_file_ids = [f.get("file_id") for f in files]
                if set(file_ids) != set(files_file_ids):
                    return False, "file_ids与files中的file_id不匹配"
        
        return True, ""
    
    @staticmethod
    def normalize_file_variable(variable_value: Dict[str, Any], var_type: str) -> Dict[str, Any]:
        """
        标准化文件变量格式，确保新旧格式的一致性
        
        :param variable_value: 变量值字典
        :param var_type: 变量类型
        :return: 标准化后的变量值
        """
        if not isinstance(variable_value, dict):
            return {}
        
        normalized = variable_value.copy()
        
        if var_type == "ARRAY_FILE":
            # 确保file_ids和files的一致性
            file_ids = normalized.get("file_ids", [])
            files = normalized.get("files", [])
            
            # 如果只有file_ids没有files，尝试构建一个基本的files数组
            if file_ids and not files:
                normalized["files"] = [
                    {"file_id": fid, "filename": f"file_{fid}"} 
                    for fid in file_ids
                ]
                logger.debug(f"为file_ids构建了基本的files数组: {len(file_ids)}个文件")
            
            # 如果只有files没有file_ids，提取file_ids
            elif files and not file_ids:
                normalized["file_ids"] = [
                    f.get("file_id") for f in files 
                    if isinstance(f, dict) and f.get("file_id")
                ]
                logger.debug(f"从files数组中提取file_ids: {len(normalized['file_ids'])}个文件")
            
            # 🔧 修复：如果两者都存在但不匹配，以file_ids为准，重新构建files
            elif file_ids and files and len(file_ids) != len(files):
                # 创建file_id到filename的映射
                file_id_to_name = {}
                for file_info in files:
                    if isinstance(file_info, dict):
                        fid = file_info.get("file_id")
                        fname = file_info.get("filename")
                        if fid and fname:
                            file_id_to_name[fid] = fname
                
                # 基于file_ids重新构建files数组
                normalized["files"] = []
                for fid in file_ids:
                    filename = file_id_to_name.get(fid, f"file_{fid}")
                    normalized["files"].append({"file_id": fid, "filename": filename})
                
                logger.debug(f"已修复file_ids和files的不匹配: {len(file_ids)}个文件")
                
            # 🔧 修复：检查files中是否有file_ids中不存在的文件，如果有则移除
            elif file_ids and files:
                file_ids_set = set(file_ids)
                filtered_files = [
                    f for f in files 
                    if isinstance(f, dict) and f.get("file_id") in file_ids_set
                ]
                if len(filtered_files) != len(files):
                    normalized["files"] = filtered_files
                    logger.debug(f"已移除files中不在file_ids中的文件: {len(files)} -> {len(filtered_files)}")
        
        return normalized 