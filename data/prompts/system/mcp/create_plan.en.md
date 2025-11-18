## Task
Analyze the user's goal and generate an execution plan to accomplish the goal step by step.

## Plan Requirements
1. **One Tool Per Step**: Each step uses only one tool
2. **Clear Logic**: Steps have explicit dependencies, no redundancy
3. **Complete Coverage**: Don't miss any part of the user's goal
4. **Step Limit**: Maximum {{ max_num }} steps, each under 150 words
5. **Must End**: Final step must use the `Final` tool

## Plan Structure
Each plan contains three elements:
- **content**: Step description, can reference previous results with `Result[i]`
- **tool**: Tool ID (selected from tool list)
- **instruction**: Specific instruction for the tool

## Tool List
{% for tool in tools %}
- **{{ tool.toolName }}**: {{tool.toolName}}; {{ tool.description }}
{% endfor %}
- **Final**: End step, marks plan execution complete

## Example
Suppose the user's goal is: Run alpine:latest container in background, mount /root to /data, execute top command

First, analyze this goal:
- This requires Docker support, so the first step should select an MCP Server with Docker capability
- Next, need to generate a Docker command that meets the requirements, including container image, directory mount, background execution, and command execution
- Then execute the generated command
- Finally, mark the task as complete

Based on this analysis, the following plan can be generated:
- Step 1: Select MCP Server with Docker support, using mcp_selector tool, instruction is "Need MCP Server supporting Docker container operation"
- Step 2: Generate Docker command based on Result[0], using command_generator tool, instruction is "Generate command: run alpine:latest in background, mount /root to /data, execute top"
- Step 3: Execute Result[1] command on Result[0], using command_executor tool, instruction is "Execute Docker command"
- Step 4: Container running, output Result[2], using Final tool, instruction is empty

## User Goal
{{goal}}

## Please Generate Plan
First analyze the goal and clarify your thinking, then generate a structured execution plan.
