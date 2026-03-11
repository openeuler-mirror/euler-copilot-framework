# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Record摘要生成工具的提示词"""
from textwrap import dedent

from apps.models import LanguageType

# 摘要生成提示词：适配ExecutorHistory执行历史，约束生成文档指定的标准化摘要
# 核心修改：新增「核心内容」字段，完整保留代码/文本/命令行内容，同时遵守原有格式/Token约束
ABSTRACT_PROMPT: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
        <instructions>
            根据给定的CLI工具执行历史记录，生成一个标准化的操作摘要，该摘要将用于Agent上下文记忆管理。
            生成的摘要必须严格遵循固定模板，保留核心操作信息（含完整代码/文本/命令行内容），剔除过程性冗余内容，确保Token不超过200个。

            生成摘要的硬性要求如下：
            1. 严格按照【操作记录-{{record_id}}】+核心目标+关键操作链+核心内容+最终结果+异常与重试的固定结构生成，不得修改模板格式；
            2. 核心目标从user角色的第一条指令提取，过滤"帮我、麻烦、请"等修饰词，仅保留「动作+对象」；
            3. 关键操作链仅保留assistant工具调用+对应function执行结果，格式为「工具名(核心参数)→结果」，多工具用→连接并自动去重,严格按照<history>真实内容，切勿偏离事实；
            4. 核心内容完整保留本次操作中「产生/读取/修改」的代码/文本/命令行内容：
               - 代码类：完整保留（含格式/缩进），用「代码：」；
               - 文本/命令行类：完整保留核心内容，用「文本：」/「命令：」；
               - 无核心内容则填"无"；
            5. 最终结果从最后一条function角色记录提取，标注成功/失败，核心信息截断至50字内，失败需补充关键错误信息（30字内）；
            6. 异常与重试统计function执行失败次数，标注关键失败原因，无失败则填"无"，有失败需标注最终执行状态；
            7. 输出时请不要包含XML标签，确保信息准确性，不得编造任何未在执行历史中出现的内容；
            8. 工具名和核心参数需简洁，核心参数截断至20字内，过滤过程性的进度、查询等无意义步骤；
            9. 整体Token严格控制在200以内，核心内容超长时优先保留代码/文本关键逻辑。

            执行历史记录将在<history>标签中给出，每条记录包含角色和内容信息。
        </instructions>

         <history>
         {%- for item in history -%}
         <{{item.role}}>
            {{item.content | trim}}
         </{{item.role}}>
         {%- endfor -%}
         </history>

        现在，请严格按照固定模板开始生成标准化操作摘要：
        【操作记录-{{record_id}}】
        核心目标：
        关键操作链：
        核心内容：
        最终结果：
        异常与重试：
    """
    ).strip(),
    LanguageType.ENGLISH: dedent(
        r"""
        <instructions>
            Generate a standardized operation abstract based on the given CLI tool execution history records, 
            which will be used for Agent context memory management.
            The generated abstract must strictly follow the fixed template, retain core operation information (including complete code/text/command content), 
            eliminate procedural redundant content, and ensure that the token does not exceed 200.

            The hard requirements for generating the abstract are as follows:
            1. Strictly generate according to the fixed structure of 【Operation Record-{{record_id}}】 + Core Goal + 
               Key Operation Chain + Core Content + Final Result + Exception and Retry, without modifying the template format;
            2. Extract the core goal from the first instruction of the user role, filter out modifier words such as 
               "please, help me", and only retain [Action + Object];
            3. The key operation chain only retains assistant tool calls and corresponding function execution results, 
               in the format of [Tool Name(Core Parameters)→Result], multiple tools are connected with → and deduplicated automatically;
            4. Core Content completely retains the code/text/command content "generated/read/modified" in this operation:
               - Code type: Keep complete (including format/indentation), marked with prefix "Code:";
               - Text/Command type: Keep complete core content, marked with prefix "Text:"/"Command:";
               - Fill in "None" if no core content;
            5. Extract the final result from the last function role record, mark success/failure, truncate the core 
               information to within 50 words, and supplement key error information (within 30 words) if it fails;
            6. Exception and Retry count the number of function execution failures, mark the key failure reason, 
               fill in "None" if there is no failure, and mark the final execution status if there is a failure;
            7. Do not include XML tags in the output, ensure the accuracy of the information, and do not fabricate 
               any content that does not appear in the execution history;
            8. Tool names and core parameters should be concise, core parameters are truncated to within 20 words, 
               and meaningless procedural steps such as progress and query are filtered out;
            9. Strictly control the total tokens within 200, prioritize retaining key logic of code/text if core content is too long.

            The execution history records will be given in the <history> tag, and each record contains role and content information.
        </instructions>

         <history>
         {%- for item in history -%}
         <{{item.role}}>
            {{item.content | trim}}
         </{{item.role}}>
         {%- endfor -%}
         </history>

        Now, please generate the standardized operation abstract strictly according to the fixed template:
        【Operation Record-{{record_id}}】
        Core Goal:
        Key Operation Chain:
        Core Content:
        Final Result:
        Exception and Retry:
    """
    ).strip(),
}