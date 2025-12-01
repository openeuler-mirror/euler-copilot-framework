# util/venv_util.py（适配 openEuler 系统，仅保留 yum 逻辑）
import logging
import os
import subprocess
import toml

def get_current_venv_pip() -> str:
    """
    获取当前激活的mcp虚拟环境的pip路径（仅适配 openEuler/Linux 系统）
    :return: pip可执行文件的绝对路径
    :raises Exception: 未激活虚拟环境时抛出异常
    """
    
    # 逻辑：通过VIRTUAL_ENV环境变量定位虚拟环境（激活后自动生成该变量）
    venv_path = os.getenv("VIRTUAL_ENV")
    if not venv_path:
        raise Exception("未激活mcp虚拟环境，请先执行 source ./venv/global/bin/activate（文档2-142节）")
    
    return os.path.join(venv_path, "bin", "pip")

def execute_simple_deps_script(deps_script_path: str):
    """
    执行简化版deps.toml脚本
    安装逻辑：先装系统依赖（yum），再装Python依赖（当前虚拟环境pip）
    :param deps_script_path: 简化版deps.toml的路径
    :raises FileNotFoundError: 依赖脚本不存在时抛出异常
    :raises subprocess.CalledProcessError: 依赖安装命令执行失败时抛出异常
    """
    
    # 1. 读取deps.toml内容
    if not os.path.exists(deps_script_path):
        raise FileNotFoundError(f"依赖脚本不存在：{deps_script_path}")
    with open(deps_script_path, "r", encoding="utf-8") as f:
        deps_data = toml.load(f)
    
    # 2. 安装系统依赖
    system_deps = deps_data.get("system_deps", {})
    if system_deps:
        logging.info("=== 开始安装系统依赖（openEuler yum）===")
        for dep_name, yum_cmd in system_deps.items():
            # 检查依赖是否已安装（通过 --version 或专用命令验证）
            verify_cmd = f"{dep_name} --version" if dep_name != "docker" else "docker --version"
            # 静默执行验证命令，返回码为0表示已安装
            if subprocess.run(verify_cmd, shell=True, capture_output=True, text=True).returncode == 0:
                logging.info(f"系统依赖[{dep_name}]已安装，跳过")
                continue
            
            # 执行 yum 安装命令（openEuler 专用）
            logging.info(f"正在安装系统依赖[{dep_name}]：{yum_cmd}")
            # check=True 确保命令失败时抛异常，便于上层捕获
            subprocess.run(yum_cmd, shell=True, check=True, text=True)
            logging.info(f"系统依赖[{dep_name}]安装完成\n")
    
    # 3. 安装Python依赖
    pip_deps = deps_data.get("pip_deps", {})
    if pip_deps:
        logging.info("=== 开始安装Python依赖（当前虚拟环境）===")
        pip_path = get_current_venv_pip()
        for dep_name, version in pip_deps.items():
            # 构造pip安装命令
            install_cmd = [pip_path, "install", "-q", f"{dep_name}{version}"]  # -q 静默安装，减少输出
            logging.info(f"正在安装Python依赖[{dep_name}]：{' '.join(install_cmd)}")
            subprocess.run(install_cmd, check=True, text=True)
            logging.info(f"Python依赖[{dep_name}]安装完成\n")
    
    logging.info(f"所有依赖安装完成（依赖脚本：{deps_script_path}）")