# mcp_center

## 1. Introduction
mcp_center is used to build the oe intelligent assistant, and its directory structure is as follows:
```
├── client - Test client
├── config - Public and private configuration files
├── mcp_config - Configuration files for mcp registration to the framework
├── README.en.md - English version description
├── README.md - Chinese version description
├── requiremenets.txt - Overall dependencies
├── run.sh - Script to start the mcp service
├── servers - Directory containing mcp server source code
└── service - Directory containing .service files for mcp
```

### Running Instructions
1. Before running the mcp server, execute the following command in the mcp_center directory:
   ```
   export PYTHONPATH=$(pwd)
   ```
2. Start the mcp server through Python for testing
3. You can test each mcp tool through client.py in the client directory. The specific URL, tool name, and input parameters can be adjusted as needed.


## 2. Rules for Adding New mcp
1. **Create Service Source Code Directory**  
   Create a new folder under the `mcp_center/servers` directory. Example (taking top mcp as an example):
   ```
   servers/top/
   ├── README.en.md       English version of mcp service details
   ├── README.md          Chinese version of mcp service details
   ├── requirements.txt   Contains only private installation dependencies (to avoid conflicts with public dependencies)
   └── src                Source code directory (including server main entry)
       └── server.py
   ```

2. **Configuration File Settings**  
   Create a new configuration file under the `mcp_center/config/private` directory. Example (taking top mcp as an example):
   ```
   config/private/top
   ├── config_loader.py   Configuration loader (including public configuration and private custom configuration)
   └── config.toml        Private custom configuration
   ```

3. **Document Updates**  
   For each new mcp added, you need to synchronously add the basic information of the mcp to the existing mcp section in the main directory's README (ensure that ports do not conflict, starting from 12100).<br>
   For each new mcp added, you need to add a .service file in the service directory of the main directory to make the mcp a service.<br>
   For each new mcp added, you need to create a corresponding directory in mcp_config of the main directory and create a config.json under it (for registering the mcp to the framework).<br>
   For each new mcp added, you need to add a command in run.sh of the main directory to start the mcp service.

4. **General Parameter Requirements**  
   Each mcp tool requires a host as an input parameter for communication with the remote server.

5. **Remote Command Execution**  
   Remote command execution can be implemented through `paramiko`.


## 3. Existing MCP Services

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/remote_info         |
| Directory| mcp_center/servers/remote_info |
| Port Used| 12100                       |
| Introduction | Obtain endpoint information |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/shell_generator     |
| Directory| mcp_center/servers/shell_generator |
| Port Used| 12101                       |
| Introduction | Generate & execute shell commands |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/top     |
| Directory| mcp_center/servers/top |
| Port Used| 12110                      |
| Introduction | Get system load info |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/kill     |
| Directory| mcp_center/servers/kill |
| Port Used| 12111                       |
| Introduction | Process control & signal meanings |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/nohup     |
| Directory| mcp_center/servers/nohup |
| Port Used| 12112                       |
| Introduction | Background process execution |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/strace     |
| Directory| mcp_center/servers/strace |
| Port Used| 12113                       |
| Introduction | Process tracing for anomaly analysis |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/nvidia     |
| Directory| mcp_center/servers/nvidia |
| Port Used| 12114                       |
| Introduction | mcp_center/servers/nvidia |

| Category   | Details                     |
|------------|------------------------------|
| Name       | servers/npu                  |
| Directory  | mcp_center/servers/npu       |
| Port Used  | 12115                        |
| Description| Query and control of NPU     |

| Category   | Details                  |
|------------|--------------------------|
| Name       | servers/iftop            |
| Directory  | mcp_center/servers/iftop |
| Port Used  | 12116                    |
| Description| Network traffic monitoring |

| Category | Details                       |
|----------|-------------------------------|
| Name     | servers/nload                 |
| Directory| mcp_center/servers/nload      |
| Port Used| 12117                         |
| Introduction | Nload Bandwidth Monitoring |

| Category | Details                       |
|----------|-------------------------------|
| Name     | servers/netstat               |
| Directory| mcp_center/servers/netstat    |
| Port Used| 12118                         |
| Introduction | netstat Network Connection Monitoring |

| Category | Details                       |
|----------|-------------------------------|
| Name     | servers/lsof                  |
| Directory| mcp_center/servers/lsof       |
| Port Used| 12119                         |
| Introduction | Quickly troubleshoot file occupation conflicts, abnormal network connections and process resource occupation issues |

| Category | Details                       |
|----------|-------------------------------|
| Name     | servers/ifconfig              |
| Directory| mcp_center/servers/ifconfig   |
| Port Used| 12120                         |
| Introduction | ifconfig Network Interface Information Monitoring |

| Category | Details                       |
|----------|-------------------------------|
| Name     | servers/ethtool               |
| Directory| mcp_center/servers/ethtool    |
| Port Used| 12121                         |
| Introduction | ethtool Network Card Information Query, Feature Status and Network Card Settings |

| Category | Details                       |
|----------|-------------------------------|
| Name     | servers/tshark                |
| Directory| mcp_center/servers/tshark     |
| Port Used| 12122                         |
| Introduction | Capture, Display and Analyze Network Traffic |

| Category | Details                       |
|----------|-------------------------------|
| Name     | servers/file_content_tool     |
| Directory| mcp_center/servers/file_content_tool |
| Port Used| 12125                         |
| Introduction | File Content Creation, Deletion, Modification and Query |

| Category | Details                       |
|----------|-------------------------------|
| Name     | servers/firewalld             |
| Directory| mcp_center/servers/firewalld  |
| Port Used| 12130                         |
| Introduction | Firewalld Network Firewall Management Tool |

| Category | Details                       |
|----------|-------------------------------|
| Name     | servers/iptable               |
| Directory| mcp_center/servers/iptable    |
| Port Used| 12131                         |
| Introduction | iptables Firewall Management Tool |

| Category | Details                       |
|----------|-------------------------------|
| Name     | servers/docker                |
| Directory| mcp_center/servers/docker     |
| Port Used| 12133                         |
| Introduction | docker Tool |

| Category | Details                       |
|----------|-------------------------------|
| Name     | servers/qemu                  |
| Directory| mcp_center/servers/qemu       |
| Port Used| 12134                         |
| Introduction | Qemu Virtual Machine Management Tool |

| Category | Details                       |
|----------|-------------------------------|
| Name     | servers/nmap                  |
| Directory| mcp_center/servers/nmap       |
| Port Used| 12135                         |
| Introduction | Nmap IP Scanning Tool |

| Category | Details                       |
|----------|-------------------------------|
| Name     | servers/file_transfer                    |
| Directory| mcp_center/servers/file_transfer         |
| Port Used| 12136                         |
| Introduction | File Transfer/Download  |

| Category       | Details                                          |
|----------------|--------------------------------------------------|
| Name           | servers/systrace-mcpserver                       |
| Directory      | mcp_center/servers/systrace/systrace_mcp         |
| Port Occupied  | 12145                                            |
| Description    | Start MCP Server Service                         |

| Category       | Details                                          |
|----------------|--------------------------------------------------|
| Name           | servers/systrace-openapi                         |
| Directory      | mcp_center/servers/systrace/systrace_mcp         |
| Port Occupied  | 12146                                            |
| Description    | Start OpenAPI Server Service                     |

| Category       | Details                                          |
|----------------|--------------------------------------------------|
| Name           | servers/systrace-mcpserver                       |
| Directory      | mcp_center/servers/euler-copilot-tune            |
| Port Occupied  | 12147                                            |
| Description    | Tuning MCP Service                               |

| Category | Details |
|----------|--------------------------|
| Name | servers/ |
| Directory | mcp_center/servers/lscpu |
| Port Occupied | 12202 |
| Description | Collects static information such as CPU architecture |

| Category | Details |
|----------|--------------------------|
| Name | servers/numa_topo |
| Directory | mcp_center/servers/numa_topo |
| Port Occupied | 12203 |
| Description | Queries NUMA hardware topology and system configuration |

| Category | Details |
|----------|--------------------------|
| Name | servers/numa_bind_proc |
| Directory | mcp_center/servers/numa_bind_proc |
| Port Occupied | 12204 |
| Description | Binds processes to specified NUMA nodes at startup |

| Category | Details |
|----------|--------------------------|
| Name | servers/numa_rebind_proc |
| Directory | mcp_center/servers/numa_rebind_proc |
| Port Occupied | 12205 |
| Description | Modifies NUMA bindings of already started processes |

| Category | Details |
|----------|--------------------------|
| Name | servers/numa_bind_docker |
| Directory | mcp_center/servers/numa_bind_docker |
| Port Occupied | 12206 |
| Description | Configure NUMA binding for Docker containers |

| Category | Details |
|----------|--------------------------|
| Name | servers/numa_perf_compare |
| Directory | mcp_center/servers/numa_perf_compare |
| Port Occupied | 12208 |
| Description | Control test variables with NUMA binding |

| Category | Details |
|----------|--------------------------|
| Name | servers/numa_diagnose |
| Directory | mcp_center/servers/numa_diagnose |
| Port Occupied | 12209 |
| Description | Locate hardware issues with NUMA binding |

| Category | Details |
|----------|--------------------------|
| Name | servers/numastat |
| Directory | mcp_center/servers/numastat |
| Port Occupied | 12210 |
| Description | View the overall NUMA memory access status of the system |

| Category | Details |
|----------|--------------------------|
| Name | servers/numa_cross_node |
| Directory | mcp_center/servers/numa_cross_node |
| Port Occupied | 12211 |
| Description | Identify processes with excessive cross-node memory access |

| Category | Details |
|----------|--------------------------|
| Name | servers/numa_container |
| Directory | mcp_center/servers/numa_container |
| Port Occupied | 12214 |
| Description | Monitor NUMA memory access in Docker containers |

| Category | Details |
|----------|--------------------------|
| Name | servers/hotspot_trace |
| Directory | mcp_center/servers/hotspot_trace |
| Port Occupied | 12216 |
| Description | Quickly locate CPU performance bottlenecks in systems/processes |

| Category | Details |
|----------|--------------------------|
| Name | servers/cache_miss_audit |
| Directory | mcp_center/servers/cache_miss_audit |
| Port Occupied | 12217 |
| Description | Identify performance losses due to CPU cache misses |

| Category | Details |
|----------|--------------------------|
| Name | servers/func_timing_trace |
| Directory | mcp_center/servers/func_timing_trace |
| Port Occupied | 12218 |
| Description | Accurately measure function execution time (including call stack) |

| Category | Details |
|----------|--------------------------|
| Name | servers/strace_syscall |
| Directory | mcp_center/servers/strace_syscall |
| Port Occupied | 12219 |
| Description | Investigate unreasonable system calls (high frequency / time-consuming) |

| Category | Details |
|----------|--------------------------|
| Name | servers/perf_interrupt |
| Directory | mcp_center/servers/perf_interrupt |
| Port Occupied | 12220 |
| Description | Locate CPU usage caused by high-frequency interrupts |

| Category | Details |
|----------|--------------------------|
| Name | servers/flame_graph |
| Directory | mcp_center/servers/flame_graph |
| Port Occupied | 12222 |
| Description | Flame graph generation: Visualize performance bottlenecks |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/free                |
| Directory| mcp_center/servers/free     |
| Port Used| 13100                       |
| Introduction | Obtain the overall status of system memory |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/vmstat              |
| Directory| mcp_center/servers/vmstat   |
| Port Used| 13101                       |
| Introduction | Collect information on system resource interaction bottlenecks |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/sar                 |
| Directory| mcp_center/servers/sar      |
| Port Used| 13102                       |
| Introduction | System resource monitoring and fault diagnosis |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/sync                |
| Directory| mcp_center/servers/sync     |
| Port Used| 13103                       |
| Introduction | Write memory buffer data to disk |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/swapon              |
| Directory| mcp_center/servers/swapon   |
| Port Used| 13104                       |
| Introduction | Check the status of swap devices |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/swapoff             |
| Directory| mcp_center/servers/swapoff  |
| Port Used| 13105                       |
| Introduction | Disable swap devices    |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/fallocate           |
| Directory| mcp_center/servers/fallocate|
| Port Used| 13106                       |
| Introduction | Temporarily create and enable swap files |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/find                |
| Directory| mcp_center/servers/find     |
| Port Used| 13107                       |
| Introduction | File Search             |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/touch               |
| Directory| mcp_center/servers/touch    |
| Port Used| 13108                       |
| Introduction | File Creation and Time Calibration |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/mkdir               |
| Directory| mcp_center/servers/mkdir    |
| Port Used| 13109                       |
| Introduction | Directory Creation      |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/rm                  |
| Directory| mcp_center/servers/rm       |
| Port Used| 13110                       |
| Introduction | File Deletion           |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/mv                  |
| Directory| mcp_center/servers/mv       |
| Port Used| 13111                       |
| Introduction | File move or rename     |

| Category | Details                     |
|----------|-----------------------------|
| Name     | servers/ls                  |
| Directory| mcp_center/servers/ls       |
| Port Used| 13112                       |
| Introduction | View directory contents |

| Category | Details                              |
|----------|--------------------------------------|
| Name     | head                                 |
| Directory| mcp_center/servers/head              |
| Port Used     | 13113                                |
| Introduction | File beginning content viewing tool  |

| Category | Details                              |
|----------|--------------------------------------|
| Name     | tail                                 |
| Directory| mcp_center/servers/tail              |
| Port Used     | 13114                                |
| Introduction | File ending content viewing tool      |

| Category | Details                              |
|----------|--------------------------------------|
| Name     | cat                                  |
| Directory| mcp_center/servers/cat               |
| Port Used     | 13115                                |
| Introduction | File content viewing tool            |

| Category | Details                              |
|----------|--------------------------------------|
| Name     | chown                                |
| Directory| mcp_center/servers/chown             |
| Port Used     | 13116                                |
| Introduction | File owner modification tool         |

| Category | Details                              |
|----------|--------------------------------------|
| Name     | chmod                                |
| Directory| mcp_center/servers/chmod             |
| Port Used     | 13117                                |
| Introduction | File permission modification tool    |

| Category | Details                              |
|----------|--------------------------------------|
| Name     | tar                                  |
| Directory| mcp_center/servers/tar               |
| Port Used     | 13118                                |
| Introduction | File compression and decompression tool |

| Category | Details                              |
|----------|--------------------------------------|
| Name     | zip                                  |
| Directory| mcp_center/servers/zip               |
| Port Used     | 13119                                |
| Introduction | File compression and decompression tool |

| Category | Details                              |
|----------|--------------------------------------|
| Name     | grep                                 |
| Directory| mcp_center/servers/grep              |
| Port Used     | 13120                                |
| Introduction | File content search tool             |

| Category | Details                              |
|----------|--------------------------------------|
| Name     | sed                                  |
| Directory| mcp_center/servers/sed               |
| Port Used     | 13121                                |
| Introduction | Text processing tool                 |

| Category | Details                              |
|----------|--------------------------------------|
| Name     | echo                                 |
| Directory| mcp_center/servers/echo              |
| Port Used     | 13125                                |
| Introduction | Text writing tool                    |
