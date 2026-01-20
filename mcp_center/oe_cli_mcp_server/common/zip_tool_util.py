import os
import zipfile
import logging
# 全局目标目录（转为绝对路径，避免相对路径混乱）
TARGETDIR = os.path.join("/usr/lib/sysagent/mcp_center/oe_cli_mcp_server/mcp_tools/")

# 配置日志（写入控制台+文件，方便排查）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    handlers=[logging.StreamHandler()]  # 如需写入文件，可添加 logging.FileHandler("unzip.log")
)
logger = logging.getLogger(__name__)

def unzip_tool_package(zip_file_path, target_dir: str = TARGETDIR) -> bool:
    """
    解压 ZIP 文件中的所有内容
    :param zip_file_path: ZIP 文件的路径（如 "test.zip"）
    :param target_dir: 解压后文件存放目标路径
    :return: 解压成功返回 True，失败返回 False
    """
    # 1. 校验输入文件是否存在
    if not os.path.exists(zip_file_path):
        logger.error(f"ZIP 文件不存在：{zip_file_path}")
        return False

    # 2. 安全获取压缩包名称（避免[:-4]截取异常）
    zip_basename = os.path.basename(zip_file_path)
    if not zip_basename.lower().endswith(".zip"):
        logger.error(f"文件不是合法的 ZIP 格式：{zip_file_path}")
        return False
    pkg_name = zip_basename[:-4]  # 此时截取是安全的

    # 3. 拼接最终解压路径
    extract_to_path = target_dir
    logger.info(f"准备解压文件 {zip_file_path} 到 {extract_to_path}")

    # 4. 创建目标目录（含父目录），处理权限问题
    try:
        os.makedirs(extract_to_path, exist_ok=True)  # exist_ok=True 避免重复创建报错
    except PermissionError:
        logger.error(f"无权限创建目录：{extract_to_path}，请使用 root 权限运行")
        return False
    except Exception as e:
        logger.error(f"创建解压目录失败：{str(e)}")
        return False

    # 5. 执行解压操作
    try:
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            # 校验 ZIP 文件是否损坏
            zip_ref.testzip()  # 检测压缩包完整性
            zip_ref.extractall(extract_to_path)
        logger.info(f"✅ 解压完成！文件已保存到：{extract_to_path}")
        return True
    except zipfile.BadZipFile:
        logger.error(f"❌ 错误：{zip_file_path} 不是有效的 ZIP 文件（可能损坏）")
    except FileNotFoundError as e:
        logger.error(f"❌ 错误：解压过程中找不到文件 - {str(e)}")
    except PermissionError:
        logger.error(f"❌ 错误：无权限写入目录 {extract_to_path}，请使用 sudo 运行")
    except Exception as e:
        logger.error(f"❌ 解压失败：{str(e)}", exc_info=True)  # exc_info=True 打印完整异常栈

    return False

# 示例调用
if __name__ == "__main__":
    # 测试：解压 file_test_tool.zip
    zip_path = "/home/tsn/euler-copilot-framework/mcp_center/file_test_tool.zip"
    result = unzip_all(zip_file_path=zip_path)
    print(f"解压结果：{'成功' if result else '失败'}")