# mcp_center

## 一、介绍
mcp_center 用于构建 oe 智能助手，其目录结构如下：
```
├── client 测试用客户端
├── config 公共和私有配置文件
├── mcp_config mcp注册到框架的配置文件
├── README.en.md 英文版本说明
├── README.md 中文版本说明
├── requiremenets.txt 整体的依赖
├── run.sh 唤起mcp服务的脚本
├── servers mcp server源码所在目录
└── service mcp的.serivce文件所在目录
```

### 运行说明
1. 运行 mcp server 前，需在 mcp_center 目录下执行：
   ```
   export PYTHONPATH=$(pwd)
   ```
2. 通过 Python 唤起 mcp server 进行测试
3. 可通过 client 目录下的 client.py 对每个 mcp 工具进行测试，具体的 URL、工具名称和入参可自行调整


## 二、新增 mcp 规则
1. **创建服务源码目录**  
   在 `mcp_center/servers` 目录下新建文件夹，示例（以 top mcp 为例）：
   ```
   servers/top/
   ├── README.en.md       英文版本的 mcp 服务详情描述
   ├── README.md          中文版本的 mcp 服务详情描述
   ├── requirements.txt   仅包含私有安装依赖（避免与公共依赖冲突）
   └── src                源码目录（含 server 主入口）
       └── server.py
   ```

2. **配置文件设置**  
   在 `mcp_center/config/private` 目录下新建配置文件，示例（以 top mcp 为例）：
   ```
   config/private/top
   ├── config_loader.py   配置加载器（含公共配置和私有自定义配置）
   └── config.toml        私有自定义配置
   ```

3. **文档更新**  
   每新增一个 mcp，需在主目录的 README 中现有 mcp 板块同步新增该 mcp 的基本信息（确保端口不冲突，端口从 12100 开始）<br>
   每新增一个 mcp，需要在主目录中的 service 中增加.service文件用于将mcp制作成服务<br>
   每新增一个 mcp，需要在主目录中的 mcp_config 中新建对应名称的目录并在下面创建一个config.json（用于将mcp注册到框架）<br>
   每新增一个 mcp，需要在主目录中的 run.sh 中增加一条命令用于唤起mcp服务
4. **通用参数要求**  
   每个 mcp 的工具都需要一个 host 作为入参，用于与远端服务器通信。

5. **远程命令执行**  
   可通过 `paramiko` 实现远程命令执行。


## 三、现有的 MCP 服务

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/remote_info                      |
| 目录   | mcp_center/servers/remote_info   |
| 占用端口 | 12100                    |
| 简介   | 获取端点信息   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/shell_generator                     |
| 目录   | mcp_center/servers/shell_generator  |
| 占用端口 | 12101                    |
| 简介   | 生成&执行shell命令   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/top                     |
| 目录   | mcp_center/servers/top  |
| 占用端口 | 12110                  |
| 简介   | 获取系统负载信息   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/kill                    |
| 目录   | mcp_center/servers/kill  |
| 占用端口 | 12111                  |
| 简介   | 控制进程&查看进程信号量含义   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/nohup                    |
| 目录   | mcp_center/servers/nohup  |
| 占用端口 | 12112                  |
| 简介   | 后台执行进程   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/strace                    |
| 目录   | mcp_center/servers/strace  |
| 占用端口 | 12113                 |
| 简介   | 跟踪进程信息，可以用于异常情况分析   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/nvidia                    |
| 目录   | mcp_center/servers/nvidia  |
| 占用端口 | 12114                 |
| 简介   | GPU负载信息查询   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/npu                    |
| 目录   | mcp_center/servers/npu  |
| 占用端口 | 12115                 |
| 简介   | npu的查询和控制   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/iftop                    |
| 目录   | mcp_center/servers/iftop  |
| 占用端口 | 12116                 |
| 简介   | 网络流量监控   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/nload                    |
| 目录   | mcp_center/servers/nload    |
| 占用端口 | 12117                 |
| 简介   | Nload带宽监控   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/netstat                    |
| 目录   | mcp_center/servers/netstat    |
| 占用端口 | 12118                 |
| 简介   | netstat网络连接监控   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/lsof                    |
| 目录   | mcp_center/servers/lsof    |
| 占用端口 | 12119                 |
| 简介   | 快速排查文件占用冲突、网络连接异常及进程资源占用问题   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/ifconfig                    |
| 目录   | mcp_center/servers/ifconfig    |
| 占用端口 | 12120                 |
| 简介   | ifconfig 网络接口信息监控   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/ethtool                    |
| 目录   | mcp_center/servers/ethtool    |
| 占用端口 | 12121                 |
| 简介   | ethtool网卡信息查询，特性情况，网卡设置   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/tshark                    |
| 目录   | mcp_center/servers/tshark    |
| 占用端口 | 12122                 |
| 简介   | 捕获、显示和分析网络流量   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/file_content_tool                    |
| 目录   | mcp_center/servers/file_content_tool  |
| 占用端口 | 12125                 |
| 简介   | 文件内容增删改查   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/firewalld                    |
| 目录   | mcp_center/servers/firewalld  |
| 占用端口 | 12130                 |
| 简介   | Firewalld网络防火墙管理工具   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/iptable                    |
| 目录   | mcp_center/servers/iptable  |
| 占用端口 | 12131                 |
| 简介   | iptables防火墙管理工具   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/docker                    |
| 目录   | mcp_center/servers/docker  |
| 占用端口 | 12133                 |
| 简介   | docker工具   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/qemu                    |
| 目录   | mcp_center/servers/qemu  |
| 占用端口 | 12134                 |
| 简介   | Qemu虚拟机管理工具   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/nmap                    |
| 目录   | mcp_center/servers/nmap  |
| 占用端口 | 12135                 |
| 简介   | Nmap扫描IP   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/file_transfer                    |
| 目录   | mcp_center/servers/file_transfer  |
| 占用端口 | 12136                 |
| 简介   | 文件传输/下载   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/systrace-mcpserver                   |
| 目录   | mcp_center/servers/systrace/systrace_mcp  |
| 占用端口 | 12145               |
| 简介   | 开启MCP Server服务   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/ssystrace-openapi                    |
| 目录   | mcp_center/servers/systrace/systrace_mcp  |
| 占用端口 | 12146                 |
| 简介   | 开启OpenAPI Server服务   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/systrace-mcpserver                     |
| 目录   | mcp_center/servers/euler-copilot-tune  |
| 占用端口 | 12147                 |
| 简介   |  调优MCP服务   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/lscpu                     |
| 目录   | mcp_center/servers/lscpu  |
| 占用端口 | 12202                    |
| 简介   | cpu架构等静态信息收集   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/numa_topo                     |
| 目录   | mcp_center/servers/numa_topo  |
| 占用端口 | 12203                    |
| 简介   | 查询 NUMA 硬件拓扑与系统配置   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/numa_bind_proc                     |
| 目录   | mcp_center/servers/numa_bind_proc  |
| 占用端口 | 12204                    |
| 简介   | 启动时绑定进程到指定 NUMA 节点   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/numa_rebind_proc                     |
| 目录   | mcp_center/servers/numa_rebind_proc  |
| 占用端口 | 12205                    |
| 简介   | 修改已启动进程的 NUMA 绑定   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/numa_bind_docker                     |
| 目录   | mcp_center/servers/numa_bind_docker  |
| 占用端口 | 12206                    |
| 简介   | 为 Docker 容器配置 NUMA 绑定   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/numa_perf_compare                     |
| 目录   | mcp_center/servers/numa_perf_compare  |
| 占用端口 | 12208                    |
| 简介   | 用 NUMA 绑定控制测试变量   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/numa_diagnose                     |
| 目录   | mcp_center/servers/numa_diagnose  |
| 占用端口 | 12209                     |
| 简介   | 用 NUMA 绑定定位硬件问题   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/numastat                     |
| 目录   | mcp_center/servers/numastat  |
| 占用端口 | 12210                    |
| 简介   | 查看系统整体 NUMA 内存访问状态   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/numa_cross_node                     |
| 目录   | mcp_center/servers/numa_cross_node  |
| 占用端口 | 12211                    |
| 简介   | 定位跨节点内存访问过高的进程   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/numa_container                     |
| 目录   | mcp_center/servers/numa_container  |
| 占用端口 | 12214                    |
| 简介   | 监控 Docker 容器的 NUMA 内存访问   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/hotspot_trace                     |
| 目录   | mcp_center/servers/hotspot_trace  |
| 占用端口 | 12216                    |
| 简介   | 快速定位系统 / 进程的 CPU 性能瓶颈   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/cache_miss_audit                     |
| 目录   | mcp_center/servers/cache_miss_audit  |
| 占用端口 | 12217                    |
| 简介   | 定位 CPU 缓存失效导致的性能损耗   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/func_timing_trace                     |
| 目录   | mcp_center/servers/func_timing_trace  |
| 占用端口 | 12218                    |
| 简介   | 精准测量函数执行时间（含调用栈）   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/strace_syscall                     |
| 目录   | mcp_center/servers/strace_syscall  |
| 占用端口 | 12219                    |
| 简介   | 排查不合理的系统调用（高频 / 耗时）  |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/perf_interrupt                     |
| 目录   | mcp_center/servers/perf_interrupt  |
| 占用端口 | 12220                    |
| 简介   | 定位高频中断导致的 CPU 占用   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/flame_graph                     |
| 目录   | mcp_center/servers/flame_graph  |
| 占用端口 | 12222                    |
| 简介   | 火焰图生成：可视化展示性能瓶颈   |


| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/free                      |
| 目录   | mcp_center/servers/free   |
| 占用端口 | 13100                    |
| 简介   | 获取系统内存整体状态   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/vmstat                     |
| 目录   | mcp_center/servers/vmstat   |
| 占用端口 | 13101                    |
| 简介   | 系统资源交互瓶颈信息采集   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/sar                      |
| 目录   | mcp_center/servers/sar   |
| 占用端口 | 13102                    |
| 简介   | ​​系统资源监控与故障诊断   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/sync                     |
| 目录   | mcp_center/servers/sync   |
| 占用端口 | 13103                    |
| 简介   | 内存缓冲区数据写入磁盘   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/swapon                      |
| 目录   | mcp_center/servers/swapon   |
| 占用端口 | 13104                    |
| 简介   | 查看swap设备状态   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/swapoff                     |
| 目录   | mcp_center/servers/swapoff   |
| 占用端口 | 13105                    |
| 简介   | swap设备停用   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/fallocate                      |
| 目录   | mcp_center/servers/fallocate   |
| 占用端口 | 13106                    |
| 简介   | 临时创建并启用swap文件   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/find                     |
| 目录   | mcp_center/servers/find   |
| 占用端口 | 13107                    |
| 简介   | 文件查找   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/touch                      |
| 目录   | mcp_center/servers/touch   |
| 占用端口 | 13108                    |
| 简介   | 文件创建与时间校准   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/mkdir                     |
| 目录   | mcp_center/servers/mkdir   |
| 占用端口 | 13109                    |
| 简介   | 文件夹创建   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/rm                      |
| 目录   | mcp_center/servers/rm   |
| 占用端口 | 13110                    |
| 简介   | 文件删除   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/mv                     |
| 目录   | mcp_center/servers/mv   |
| 占用端口 | 13111                    |
| 简介   | 文件移动或重命名   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | servers/ls                      |
| 目录   | mcp_center/servers/ls   |
| 占用端口 | 13112                    |
| 简介   | 查看目录内容   |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | head                     |
| 目录   | mcp_center/servers/head  |
| 占用端口 | 13113                    |
| 简介   | 文件开头内容查看工具     |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | tail                     |
| 目录   | mcp_center/servers/tail  |
| 占用端口 | 13114                    |
| 简介   | 文件末尾内容查看工具             |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | cat                      |
| 目录   | mcp_center/servers/cat   |
| 占用端口 | 13115                    |
| 简介   | 文件内容查看工具         |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | chown                    |
| 目录   | mcp_center/servers/chown |
| 占用端口 | 13116                    |
| 简介   | 文件所有者修改工具       |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | chmod                    |
| 目录   | mcp_center/servers/chmod |
| 占用端口 | 13117                    |
| 简介   | 文件权限修改工具         |

| 类别   | 详情                   |
|--------|------------------------|
| 名称   | tar                    |
| 目录   | mcp_center/servers/tar |
| 占用端口 | 13118                  |
| 简介   | 文件压缩解压工具       |

| 类别   | 详情                   |
|--------|------------------------|
| 名称   | zip                    |
| 目录   | mcp_center/servers/zip |
| 占用端口 | 13119                  |
| 简介   | 文件压缩解压工具       |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | grep                     |
| 目录   | mcp_center/servers/grep  |
| 占用端口 | 13120                    |
| 简介   | 文件内容搜索工具         |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | sed                      |
| 目录   | mcp_center/servers/sed   |
| 占用端口 | 13121                    |
| 简介   | 文本处理工具             |

| 类别   | 详情                     |
|--------|--------------------------|
| 名称   | echo                     |
| 目录   | mcp_center/servers/echo  |
| 占用端口 | 13125                    |
| 简介   | 文本写入工具             |