Please review the step history context. The current goal is: {{goal}}

You can use the following tools:

{% for tool in tools %}
- {{tool.toolName}}: {{tool.description}}
{% endfor %}

Please provide a concise analysis and your thinking process, including the following points:

- What is the progress towards completing the current goal
- What action should be taken next to achieve the goal
- Which tool should be used and the rationale for choosing that tool

**Important Notes**:

- Please provide your analysis and thinking directly, without repeating or restating the results returned by tools
- The tool outputs are already visible, you only need to reason and make decisions based on this information
- Keep responses concise and focused on the next action plan

Now, please begin thinking step by step: