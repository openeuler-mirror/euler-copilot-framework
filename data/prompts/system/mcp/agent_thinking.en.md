Now let's review the step history context. My goal is: {{goal}}

Available tools:

{% for tool in tools %}
- {{tool.toolName}}: {{tool.description}}
{% endfor %}

Please think step by step:

- How far along is my goal now
- What should be done next to achieve the goal
- Which tool should be used and why

Think and analyze first, then provide a specific plan for the next step.