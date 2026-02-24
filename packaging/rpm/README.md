# RPM 打包

本目录包含 `euler-copilot-framework` 的 RPM 构建规范和测试脚本。

## 包结构

源码包 `euler-copilot-framework` 产出两个二进制 RPM：

| 二进制包 | 类型 | 说明 |
| -------- | ---- | ---- |
| `witty-framework-lite` | 主包 | LLM 智能引擎（纯 Python），原 `euler-copilot-framework` |
| `witty-mcp-manager` | 子包 | 通用 MCP 宿主/加载器，Nuitka 编译单文件 |

## 文件

- `euler-copilot-framework.spec` — RPM 规范文件
- `dist.sh` — 发布归档脚本：将当前分支源码打包为 RPM Source0 tarball，连同 spec 一起输出到 `./dist`
- `test_build.sh` — 本地/VM 测试构建脚本

## 快速使用

### 生成发布归档

```bash
# 归档当前分支最新提交（输出到 ./dist）
./packaging/rpm/dist.sh

# 包含工作区未提交的本地修改
./packaging/rpm/dist.sh --with-dirty

# 自定义输出目录
./packaging/rpm/dist.sh --output /tmp/release

# 归档并创建 git 版本标签 v<version>-<release>
./packaging/rpm/dist.sh --tag
```

归档完成后 `./dist` 目录包含：

| 文件 | 说明 |
| ---- | ---- |
| `euler-copilot-framework-<version>.tar.gz` | RPM `Source0` 源码包 |
| `euler-copilot-framework.spec` | RPM 规范文件 |
| `dist-info.txt` | 版本元数据（分支、commit、构建时间等） |

### 基于归档执行 RPM 构建

```bash
rpmbuild -ba \
  --define '_topdir ~/rpmbuild' \
  --define '_sourcedir ./dist' \
  ./dist/euler-copilot-framework.spec
```

### 本地测试构建（需 openEuler 环境）

```bash
# 完整构建（需要安装所有 BuildRequires）
./packaging/rpm/test_build.sh

# 仅打 SRPM（不需要编译依赖）
./packaging/rpm/test_build.sh --source-only

# 跳过依赖检查
./packaging/rpm/test_build.sh --no-deps

# 详细输出
./packaging/rpm/test_build.sh --verbose
```

## BuildRequires

### witty-framework-lite

无额外编译依赖（纯 Python 源码复制）。

### witty-mcp-manager

需要 Nuitka 编译环境：

- `gcc`, `gcc-c++`, `patchelf`, `ccache`
- `python3-dev`, `uv`
