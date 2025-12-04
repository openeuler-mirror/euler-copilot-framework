from typing import Dict, Optional
from servers.oe_cli_mcp_server.config.base_config_loader import LanguageEnum
from servers.oe_cli_mcp_server.mcp_tools. base_tools. file_tools. base import (
    get_remote_auth,
    run_local_command,
    run_remote_command,
    init_result_dict,
    escape_shell_content
)

def file_grep_tool(
        target: Optional[str] = None,
        file_path: str = "",
        pattern: str = "",
        options: str = "",
        lang: Optional[LanguageEnum] = LanguageEnum.ZH
) -> Dict:
    is_zh = lang
    target_host = target.strip() if (target and isinstance(target, str)) else "127.0.0.1"
    result = init_result_dict(target_host)

    # 基础参数校验
    if not file_path.strip():
        result["message"] = "文件路径不能为空" if is_zh else "File path cannot be empty"
        return result
    if not pattern.strip():
        result["message"] = "搜索模式不能为空" if is_zh else "Search pattern cannot be empty"
        return result

    # 构建grep命令（内容转义，避免shell注入）
    escaped_pattern = escape_shell_content(pattern.strip())
    escaped_file = escape_shell_content(file_path.strip())
    grep_cmd = f"grep {options.strip()} '{escaped_pattern}' {escaped_file}"

    # 本地执行
    if target_host == "127.0.0.1":
        return run_local_command(
            cmd=grep_cmd,
            result=result,
            success_msg_zh=f"本地文件搜索完成（路径：{file_path}）",
            success_msg_en=f"Local file search completed (path: {file_path})",
            is_list_result=True
        )

    # 远程执行
    remote_auth = get_remote_auth(target_host)
    if not remote_auth:
        result["message"] = f"未找到远程主机（{target_host}）的认证配置" if is_zh else f"Authentication config for remote host ({target_host}) not found"
        return result
    if not (remote_auth["username"] and remote_auth["password"]):
        result["message"] = "远程执行需用户名和密码" if is_zh else "Username and password required for remote execution"
        return result

    return run_remote_command(
        cmd=grep_cmd,
        remote_auth=remote_auth,
        result=result,
        success_msg_zh=f"远程文件搜索完成（主机：{target_host}，路径：{file_path}）",
        success_msg_en=f"Remote file search completed (host: {target_host}, path: {file_path})",
        is_list_result=True
    )

def file_sed_tool(
        target: Optional[str] = None,
        file_path: str = "",
        pattern: str = "",
        in_place: bool = False,
        options: str = "",
        lang: Optional[LanguageEnum] = LanguageEnum.ZH
) -> Dict:
    is_zh = lang
    target_host = target.strip() if (target and isinstance(target, str)) else "127.0.0.1"
    result = init_result_dict(target_host, result_type="str")

    # 基础校验
    if not file_path.strip():
        result["message"] = "文件路径不能为空" if is_zh else "File path cannot be empty"
        return result
    if not pattern.strip() or "s/" not in pattern:
        result["message"] = "替换模式格式错误（需含s/）" if is_zh else "Replacement pattern format error (must contain s/)"
        return result

    # 构建sed命令（内容转义）
    escaped_pattern = escape_shell_content(pattern.strip())
    escaped_file = escape_shell_content(file_path.strip())
    in_place_opt = "-i" if in_place else ""
    sed_cmd = f"sed {options.strip()} {in_place_opt} '{escaped_pattern}' {escaped_file}"

    # 本地执行
    if target_host == "127.0.0.1":
        msg_zh = "原文件已修改" if in_place else "替换后内容已输出"
        msg_en = "original file modified" if in_place else "replaced content output"
        return run_local_command(
            cmd=sed_cmd,
            result=result,
            success_msg_zh=f"本地sed执行成功（{msg_zh}，路径：{file_path}）",
            success_msg_en=f"Local sed executed successfully ({msg_en}, path: {file_path})",
            is_list_result=False,
            in_place=in_place
        )

    # 远程执行
    remote_auth = get_remote_auth(target_host)
    if not remote_auth or not (remote_auth["username"] and remote_auth["password"]):
        result["message"] = "远程认证配置缺失" if is_zh else "Remote authentication config missing"
        return result

    msg_zh = "原文件已修改" if in_place else "替换后内容已输出"
    msg_en = "original file modified" if in_place else "replaced content output"
    return run_remote_command(
        cmd=sed_cmd,
        remote_auth=remote_auth,
        result=result,
        success_msg_zh=f"远程sed执行成功（{msg_zh}，主机：{target_host}）",
        success_msg_en=f"Remote sed executed successfully ({msg_en}, host: {target_host})",
        is_list_result=False,
        in_place=in_place
    )

def file_awk_tool(
        target: Optional[str] = None,
        file_path: str = "",
        script: str = "",
        options: str = "",
        lang: Optional[LanguageEnum] = LanguageEnum.ZH
) -> Dict:
    is_zh = lang
    target_host = target.strip() if (target and isinstance(target, str)) else "127.0.0.1"
    result = init_result_dict(target_host)

    # 基础参数校验
    if not file_path.strip():
        result["message"] = "文件路径不能为空，请传入有效的文件路径（如\"/etc/passwd\"）" if is_zh else "File path cannot be empty, please pass a valid path (e.g. \"/etc/passwd\")"
        return result
    if not script.strip():
        result["message"] = "awk脚本不能为空，请传入有效的处理逻辑（如\"'{print $1,$3}'\"）" if is_zh else "awk script cannot be empty, please pass valid logic (e.g. \"'{print $1,$3}'\")"
        return result

    # 构建awk命令（内容转义）
    escaped_script = escape_shell_content(script.strip())
    escaped_file = escape_shell_content(file_path.strip())
    options_clean = options.strip()
    awk_cmd = f"awk {options_clean} {escaped_script} {escaped_file}"

    # 本地执行
    if target_host == "127.0.0.1":
        return run_local_command(
            cmd=awk_cmd,
            result=result,
            success_msg_zh=f"本地awk处理成功（文件：{file_path.strip()}）",
            success_msg_en=f"Local awk processing succeeded (file: {file_path.strip()})",
            is_list_result=True
        )

    # 远程执行
    remote_auth = get_remote_auth(target_host)
    if not remote_auth:
        result["message"] = f"未找到远程主机（{target_host}）的认证配置，请检查配置文件中的remote_hosts" if is_zh else f"Authentication config for remote host ({target_host}) not found, check remote_hosts in config"
        return result
    if not (remote_auth.get("username") and remote_auth.get("password")):
        result["message"] = f"远程主机（{target_host}）的认证配置缺失用户名或密码，无法建立SSH连接" if is_zh else f"Remote host ({target_host}) auth config lacks username/password, cannot establish SSH connection"
        return result

    return run_remote_command(
        cmd=awk_cmd,
        remote_auth=remote_auth,
        result=result,
        success_msg_zh=f"远程awk处理成功（主机：{target_host}，文件：{file_path.strip()}）",
        success_msg_en=f"Remote awk processing succeeded (host: {target_host}, file: {file_path.strip()})",
        is_list_result=True
    )

def file_sort_tool(
        target: Optional[str] = None,
        file_path: str = "",
        options: str = "",
        output_file: str = "",
        lang: Optional[LanguageEnum] = LanguageEnum.ZH
) -> Dict:
    is_zh = lang
    target_host = target.strip() if (target and isinstance(target, str)) else "127.0.0.1"
    result = init_result_dict(target_host)

    # 参数校验
    if not file_path.strip():
        result["message"] = "文件路径不能为空，请提供有效的文件路径" if is_zh else "File path cannot be empty, please provide a valid path"
        return result

    # 构建sort命令（内容转义）
    escaped_file = escape_shell_content(file_path.strip())
    escaped_output = escape_shell_content(output_file.strip()) if output_file.strip() else ""
    options_clean = options.strip()
    if output_file.strip():
        sort_cmd = f"sort {options_clean} {escaped_file} -o {escaped_output}"
    else:
        sort_cmd = f"sort {options_clean} {escaped_file}"

    # 本地执行
    if target_host == "127.0.0.1":
        success_msg_zh = f"本地排序完成，结果已保存至：{output_file.strip()}" if output_file.strip() else f"本地排序完成"
        success_msg_en = f"Local sort completed, result saved to: {output_file.strip()}" if output_file.strip() else f"Local sort completed"
        return run_local_command(
            cmd=sort_cmd,
            result=result,
            success_msg_zh=success_msg_zh,
            success_msg_en=success_msg_en,
            is_list_result=True,
            in_place=bool(output_file.strip())
        )

    # 远程执行
    remote_auth = get_remote_auth(target_host)
    if not remote_auth:
        result["message"] = f"未找到远程主机（{target_host}）的认证配置" if is_zh else f"Authentication config for remote host ({target_host}) not found"
        return result
    if not (remote_auth.get("username") and remote_auth.get("password")):
        result["message"] = f"远程主机（{target_host}）的认证信息不完整（缺少用户名或密码）" if is_zh else f"Remote host ({target_host}) auth info incomplete (missing username/password)"
        return result

    success_msg_zh = f"远程排序完成，结果已保存至：{output_file.strip()}（主机：{target_host}）" if output_file.strip() else f"远程排序完成（主机：{target_host}）"
    success_msg_en = f"Remote sort completed, result saved to: {output_file.strip()} (host: {target_host})" if output_file.strip() else f"Remote sort completed (host: {target_host})"
    return run_remote_command(
        cmd=sort_cmd,
        remote_auth=remote_auth,
        result=result,
        success_msg_zh=success_msg_zh,
        success_msg_en=success_msg_en,
        is_list_result=True,
        in_place=bool(output_file.strip())
    )

def file_unique_tool(
        target: Optional[str] = None,
        file_path: str = "",
        options: str = "",
        output_file: str = "",
        lang: Optional[LanguageEnum] = LanguageEnum.ZH
) -> Dict:
    is_zh = lang
    target_host = target.strip() if (target and isinstance(target, str)) else "127.0.0.1"
    result = init_result_dict(target_host)

    # 参数校验
    if not file_path.strip():
        result["message"] = "文件路径不能为空" if is_zh else "File path cannot be empty"
        return result

    # 构建unique命令（内容转义）
    escaped_file = escape_shell_content(file_path.strip())
    escaped_output = escape_shell_content(output_file.strip()) if output_file.strip() else ""
    options_clean = options.strip()
    if output_file.strip():
        unique_cmd = f"uniq {options_clean} {escaped_file} {escaped_output}"
    else:
        unique_cmd = f"uniq {options_clean} {escaped_file}"

    # 本地执行
    if target_host == "127.0.0.1":
        success_msg_zh = f"本地去重完成，结果已保存至：{output_file.strip()}" if output_file.strip() else f"本地去重完成"
        success_msg_en = f"Local deduplication completed, result saved to: {output_file.strip()}" if output_file.strip() else f"Local deduplication completed"
        return run_local_command(
            cmd=unique_cmd,
            result=result,
            success_msg_zh=success_msg_zh,
            success_msg_en=success_msg_en,
            is_list_result=True,
            in_place=bool(output_file.strip())
        )

    # 远程执行
    remote_auth = get_remote_auth(target_host)
    if not remote_auth or not (remote_auth["username"] and remote_auth["password"]):
        result["message"] = "远程认证配置缺失" if is_zh else "Remote auth config missing"
        return result

    success_msg_zh = f"远程去重完成，结果已保存至：{output_file.strip()}（主机：{target_host}）" if output_file.strip() else f"远程去重完成（主机：{target_host}）"
    success_msg_en = f"Remote deduplication completed, result saved to: {output_file.strip()} (host: {target_host})" if output_file.strip() else f"Remote deduplication completed (host: {target_host})"
    return run_remote_command(
        cmd=unique_cmd,
        remote_auth=remote_auth,
        result=result,
        success_msg_zh=success_msg_zh,
        success_msg_en=success_msg_en,
        is_list_result=True,
        in_place=bool(output_file.strip())
    )

def file_echo_tool(
        target: Optional[str] = None,
        content: str = "",
        file_path: str = "",
        append: bool = False,
        lang: Optional[LanguageEnum] = LanguageEnum.ZH
) -> Dict:
    is_zh = lang
    target_host = target.strip() if (target and isinstance(target, str)) else "127.0.0.1"
    result = init_result_dict(target_host, result_type="str", include_file_path=True)

    # 参数校验
    if not content.strip():
        result["message"] = "写入内容不能为空" if is_zh else "Content to write cannot be empty"
        return result
    if not file_path.strip():
        result["message"] = "文件路径不能为空" if is_zh else "File path cannot be empty"
        return result

    # 构建echo命令（内容转义）
    escaped_content = escape_shell_content(content.strip())
    escaped_file = escape_shell_content(file_path.strip())
    redirect = ">>" if append else ">"
    echo_cmd = f"echo '{escaped_content}' {redirect} {escaped_file}"

    # 本地执行
    if target_host == "127.0.0.1":
        action = "追加" if append else "写入"
        action_en = "appended" if append else "written"
        return run_local_command(
            cmd=echo_cmd,
            result=result,
            success_msg_zh=f"本地{action}成功，文件路径：{file_path.strip()}",
            success_msg_en=f"Local {action_en} successfully, file path: {file_path.strip()}",
            is_list_result=False,
            in_place=True
        )

    # 远程执行
    remote_auth = get_remote_auth(target_host)
    if not remote_auth or not (remote_auth["username"] and remote_auth["password"]):
        result["message"] = "远程认证配置缺失" if is_zh else "Remote auth config missing"
        return result

    action = "追加" if append else "写入"
    action_en = "appended" if append else "written"
    return run_remote_command(
        cmd=echo_cmd,
        remote_auth=remote_auth,
        result=result,
        success_msg_zh=f"远程{action}成功（主机：{target_host}），文件路径：{file_path.strip()}",
        success_msg_en=f"Remote {action_en} successfully (host: {target_host}), file path: {file_path.strip()}",
        is_list_result=False,
        in_place=True
    )