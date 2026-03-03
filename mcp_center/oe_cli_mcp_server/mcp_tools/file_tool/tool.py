from typing import Dict, Optional
from pydantic import Field
from config.public.base_config_loader import LanguageEnum
from oe_cli_mcp_server.mcp_tools.file_tool.base import (
    init_result_dict,
    FileManager,
    FileActionEnum,
    FileEncodingEnum,
    logger, lang
)


def file_tool(
        action: FileActionEnum = Field(...,
                                       description="操作类型（枚举：ls/cat/add/append/edit/rename/chmod/delete/mkdir）"),
        path: str = Field(..., description="文件/目录路径（必填）"),
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
    result["path"] = path.strip()
    fm = FileManager(lang=lang)
    is_zh = lang == LanguageEnum.ZH

    # 1. 核心参数校验
    if not path.strip():
        result["message"] = "文件路径不能为空" if is_zh else "File path cannot be empty"
        return result

    # 2. 按枚举操作类型执行
    try:
        if action == FileActionEnum.LS:
            result["result"] = fm.ls(path.strip(), detail=detail)
            result["success"] = True
            result["message"] = (
                f"本地文件列表查询完成（路径：{path}）"
                if is_zh
                else f"Local file list queried (path: {path})")

        elif action == FileActionEnum.CAT:
            result["result"] = fm.cat(path.strip(), encoding=encoding)
            result["success"] = True
            result["message"] = (
                f"本地文件内容读取完成（路径：{path}）"
                if is_zh
                else f"Local file content read (path: {path})")

        elif action == FileActionEnum.ADD:
            add_content = content.strip() if content is not None else None
            fm.add(
                file_path=path.strip(),
                overwrite=overwrite,
                content=add_content,
                encoding=encoding.value  # 传递编码（枚举值转字符串）
            )
            result["success"] = True
            # 优化提示：区分是否写入内容
            if add_content:
                result["message"] = (
                    f"本地文件创建并写入内容成功（路径：{path}）"
                    if is_zh
                    else f"Local file created and content written (path: {path})")
            else:
                result["message"] = (
                    f"本地文件创建成功（路径：{path}）"
                    if is_zh
                    else f"Local file created (path: {path})")
        elif action == FileActionEnum.MKDIR:
            fm.mkdir(
                dir_path=path
            )
            result["success"] = True
            result["message"] = (
                f"本地目录创建成功（路径：{path}）"
                if is_zh
                else f"Local directory created successfully (path: {path})"
            )

        elif action == FileActionEnum.APPEND:
            if not content:
                result["message"] = "追加内容不能为空" if is_zh else "Append content cannot be empty"
                return result
            fm.append(path.strip(), content.strip(), encoding=encoding)
            result["success"] = True
            result["message"] = (
                f"本地文件内容追加成功（路径：{path}）"
                if is_zh
                else f"Local file content appended (path: {path})")

        elif action == FileActionEnum.EDIT:
            if not content:
                result["message"] = "覆盖内容不能为空" if is_zh else "Edit content cannot be empty"
                return result
            fm.edit(path.strip(), content.strip(), encoding=encoding)
            result["success"] = True
            result["message"] = (
                f"本地文件内容覆盖成功（路径：{path}）"
                if is_zh
                else f"Local file content overwritten ("f"path: {path})")

        elif action == FileActionEnum.RENAME:
            if not new_path:
                result["message"] = "新路径不能为空" if is_zh else "New path cannot be empty"
                return result
            fm.rename(path.strip(), new_path.strip())
            result["success"] = True
            result["path"] = new_path.strip()
            result["message"] = (
                f"本地文件重命名成功（{path} → {new_path}）"
                if is_zh
                else f"Local file renamed ("f"{path} → {new_path})")

        elif action == FileActionEnum.CHMOD:
            if not mode:
                result["message"] = "权限模式不能为空（如755）" if is_zh else "Permission mode cannot be empty (e.g.755)"
                return result
            fm.chmod(path.strip(), mode.strip())
            result["success"] = True
            result["message"] = f"本地文件权限修改成功（路径：{path}，权限：{mode}）" if is_zh else (
                f"Local file permission modified ("
                f"path: {path}, "
                f"mode: {mode})")

        elif action == FileActionEnum.DELETE:
            fm.delete(path.strip(), recursive=recursive)
            result["success"] = True
            result["message"] = f"本地文件删除成功（路径：{path}）" if is_zh else f"Local file deleted (path: {path})"

    except Exception as e:
        result["message"] = f"操作失败：{str(e)}" if is_zh else f"Operation failed: {str(e)}"
        logger.error(f"File manager error: {str(e)}")

    return result
