## What This Is

A gateway proxy that sits between the user and external LLM providers. It automatically detects personally identifiable
information (PII) in user messages, replaces it with realistic synthetic data before sending to the LLM, and restores
the original values in the response.

Built as a master's thesis project. Use case: analysis of Polish civil law contracts.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/006-provider-adapters-router/plan.md
<!-- SPECKIT END -->
