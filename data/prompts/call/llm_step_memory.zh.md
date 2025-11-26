{% if role == "user" %}
# 任务执行记录 - 第{{ step_index }}步

## 任务目标

{{ step_goal }}

## 调用工具

为了完成这一步骤，我们调用了工具 `{{ step_name }}`。

## 输入参数

提供给工具的参数为：

```json
{{ input_data | tojson }}
```

{% elif role == "assistant" %}
# 任务执行结果 - 第{{ step_index }}步

## 执行状态

第{{ step_index }}步已执行完成。

执行状态：{{ step_status }}

## 输出数据

工具执行后得到的数据为：

```json
{{ output_data | tojson }}
```

这些数据将作为后续步骤的输入或参考信息使用。

{% endif %}
