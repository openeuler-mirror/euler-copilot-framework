# 智能插件：智能调优

部署智能调优工具后，可以通过 EulerCopilot 智能体框架实现对本机进行调优。
在智能调优模式提问，智能体框架服务可以调用本机的调优工具采集性能指标，并生成性能分析报告和性能优化建议。

## 操作步骤

**步骤1** 切换到“智能调优”模式

```bash
copilot -t
```

![切换到智能调优模式](./pictures/shell-plugin-tuning-switch-mode.png)

**步骤2** 采集性能指标

```bash
帮我进行性能指标采集
```

![性能指标采集](./pictures/shell-plugin-tuning-metrics-collect.png)

**步骤3** 生成性能分析报告

```bash
帮我生成性能分析报告
```

![性能分析报告](./pictures/shell-plugin-tuning-report.png)

**步骤4** 生成性能优化建议

```bash
请生成性能优化脚本
```

![性能优化脚本](./pictures/shell-plugin-tuning-script-gen.png)

**步骤5** 选择“执行命令”，运行优化脚本

![执行优化脚本](./pictures/shell-plugin-tuning-script-exec.png)

- 脚本内容如图：
  ![优化脚本内容](./pictures/shell-plugin-tuning-script-view.png)

## 远程调优

如果需要对其他机器进行远程调优，请在上文示例的问题前面加上对应机器的 IP 地址。

例如：`请对 192.168.1.100 这台机器进行性能指标采集。`

进行远程调优前请确保目标机器已部署智能调优工具，同时请确保 EulerCopilot 智能体框架能够访问目标机器。
