# Smart Plugin: Intelligent Tuning

After deploying the intelligent tuning tool, you can use the EulerCopilot agent framework to perform tuning on the local machine.
In intelligent tuning mode, the agent framework service can call the local tuning tool to collect performance metrics and generate performance analysis reports and performance optimization recommendations.

## Operation Steps

**Step 1** Switch to "Intelligent Tuning" mode

```bash
copilot -t
```

![Switch to Intelligent Tuning Mode](./pictures/shell-plugin-tuning-switch-mode.png)

**Step 2** Collect Performance Metrics

```bash
Help me collect performance metrics
```

![Performance Metrics Collection](./pictures/shell-plugin-tuning-metrics-collect.png)

**Step 3** Generate Performance Analysis Report

```bash
Help me generate a performance analysis report
```

![Performance Analysis Report](./pictures/shell-plugin-tuning-report.png)

**Step 4** Generate Performance Optimization Recommendations

```bash
Please generate a performance optimization script
```

![Performance Optimization Script](./pictures/shell-plugin-tuning-script-gen.png)

**Step 5** Select "Execute Command" to run the optimization script

![Execute Optimization Script](./pictures/shell-plugin-tuning-script-exec.png)

- Script content as shown in the figure:
  ![Optimization Script Content](./pictures/shell-plugin-tuning-script-view.png)

## Remote Tuning

If you need to perform remote tuning on other machines, please add the corresponding machine's IP address before the questions in the examples above.

For example: `Please perform performance metrics collection on the machine 192.168.1.100.`

Before performing remote tuning, please ensure that the target machine has deployed the intelligent tuning tool, and also ensure that the EulerCopilot agent framework can access the target machine.
