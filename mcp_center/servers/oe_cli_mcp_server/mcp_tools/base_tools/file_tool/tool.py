from typing import Dict, Optional
from pydantic import Field
from servers.oe_cli_mcp_server.config.base_config_loader import LanguageEnum
from servers.oe_cli_mcp_server.mcp_tools.base_tools.file_tool.base import (
    init_result_dict,
    FileManager,
    FileActionEnum,
    FileEncodingEnum,
    logger, lang
)

def file_tool(
        action: FileActionEnum = Field(..., description="操作类型（枚举：ls/cat/add/append/edit/rename/chmod/delete）"),
        file_path: str = Field(..., description="文件/目录路径（必填）"),
        content: Optional[str] = Field(None, description="写入/追加内容（add/edit/append必填）"),
        new_path: Optional[str] = Field(None, description="新路径（rename必填）"),
        mode: Optional[str] = Field(None, description="权限模式（chmod必填，如755）"),
        detail: bool = Field(False, description="ls是否显示详细信息"),
        overwrite: bool = Field(False, description="add是否覆盖已存在文件"),
        recursive: bool = Field(False, description="delete是否递归删除目录"),
        encoding: FileEncodingEnum = Field(FileEncodingEnum.UTF8, description="文件编码（默认utf-8）"),
) -> Dict:
    """
    统一文件管理工具（精简参数+枚举入参，适配大模型识别）
    """
    # 初始化结果字典
    result = init_result_dict()
    result["file_path"] = file_path.strip()
    fm = FileManager(lang=lang)
    is_zh = lang == LanguageEnum.ZH

    # 1. 核心参数校验
    if not file_path.strip():
        result["message"] = "文件路径不能为空" if is_zh else "File path cannot be empty"
        return result

    # 2. 按枚举操作类型执行
    try:
        if action == FileActionEnum.LS:
            result["result"] = fm.ls(file_path.strip(), detail=detail)
            result["success"] = True
            result["message"] = f"本地文件列表查询完成（路径：{file_path}）" if is_zh else f"Local file list queried (path: {file_path})"

        elif action == FileActionEnum.CAT:
            result["result"] = fm.cat(file_path.strip(), encoding=encoding)
            result["success"] = True
            result["message"] = f"本地文件内容读取完成（路径：{file_path}）" if is_zh else f"Local file content read (path: {file_path})"

        elif action == FileActionEnum.ADD:
            fm.add(file_path.strip(), overwrite=overwrite)
            result["success"] = True
            result["message"] = f"本地文件创建成功（路径：{file_path}）" if is_zh else f"Local file created (path: {file_path})"

        elif action == FileActionEnum.APPEND:
            if not content:
                result["message"] = "追加内容不能为空" if is_zh else "Append content cannot be empty"
                return result
            fm.append(file_path.strip(), content.strip(), encoding=encoding)
            result["success"] = True
            result["message"] = f"本地文件内容追加成功（路径：{file_path}）" if is_zh else f"Local file content appended (path: {file_path})"

        elif action == FileActionEnum.EDIT:
            if not content:
                result["message"] = "覆盖内容不能为空" if is_zh else "Edit content cannot be empty"
                return result
            fm.edit(file_path.strip(), content.strip(), encoding=encoding)
            result["success"] = True
            result["message"] = f"本地文件内容覆盖成功（路径：{file_path}）" if is_zh else f"Local file content overwritten (path: {file_path})"

        elif action == FileActionEnum.RENAME:
            if not new_path:
                result["message"] = "新路径不能为空" if is_zh else "New path cannot be empty"
                return result
            fm.rename(file_path.strip(), new_path.strip())
            result["success"] = True
            result["file_path"] = new_path.strip()
            result["message"] = f"本地文件重命名成功（{file_path} → {new_path}）" if is_zh else f"Local file renamed ({file_path} → {new_path})"

        elif action == FileActionEnum.CHMOD:
            if not mode:
                result["message"] = "权限模式不能为空（如755）" if is_zh else "Permission mode cannot be empty (e.g.755)"
                return result
            fm.chmod(file_path.strip(), mode.strip())
            result["success"] = True
            result["message"] = f"本地文件权限修改成功（路径：{file_path}，权限：{mode}）" if is_zh else f"Local file permission modified (path: {file_path}, mode: {mode})"

        elif action == FileActionEnum.DELETE:
            fm.delete(file_path.strip(), recursive=recursive)
            result["success"] = True
            result["message"] = f"本地文件删除成功（路径：{file_path}）" if is_zh else f"Local file deleted (path: {file_path})"

    except Exception as e:
        result["message"] = f"操作失败：{str(e)}" if is_zh else f"Operation failed: {str(e)}"
        logger.error(f"File manager error: {str(e)}")

    return result