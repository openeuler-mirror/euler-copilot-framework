# Smart Plugin: Intelligent Diagnosis

After deploying the intelligent diagnosis tool, you can use the EulerCopilot intelligent agent framework to perform diagnostics on your local machine.
In intelligent diagnosis mode, the intelligent agent framework service can call local diagnostic tools to diagnose abnormal conditions, analyze them, and generate reports.

## Operation Steps

**Step 1** Switch to "Smart Plugin" mode

```bash
copilot -p
```

![Switch to Smart Plugin Mode](./pictures/shell-plugin-diagnose-switch-mode.png)

**Step 2** Abnormal Event Detection

```bash
Help me perform abnormal event detection
```

Press `Ctrl + O` to ask a question, then select "Intelligent Diagnosis" from the plugin list.

![Abnormal Event Detection](./pictures/shell-plugin-diagnose-detect.png)

**Step 3** View Abnormal Event Details

```bash
View abnormal event details for XXX container
```

![View Abnormal Event Details](./pictures/shell-plugin-diagnose-detail.png)

**Step 4** Execute Abnormal Event Analysis

```bash
Please perform profiling analysis on XXX metrics for XXX container
```

![Abnormal Event Analysis](./pictures/shell-plugin-diagnose-profiling.png)

**Step 5** View Abnormal Event Analysis Report

Wait 5 to 10 minutes, then view the analysis report.

```bash
View the profiling report corresponding to <profiling-id>
```

![Execute Optimization Script](./pictures/shell-plugin-diagnose-report.png)
