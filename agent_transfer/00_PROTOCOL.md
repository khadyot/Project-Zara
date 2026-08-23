# Inter-Agent Communication Protocol

## Roles
- **Claude:** The "Brain". Responsible for reasoning, architecture, defining data structures, deciding the logical flow of the MVP, performing high-level research, and telling Antigravity what to build.
- **Antigravity (AG):** The "Executioner". Responsible for interacting with the filesystem, running Python scripts, executing terminal commands, organizing files, and building the MVP based on Claude's design.
- **Perplexity / Human Bridge:** We do NOT have native API access to Perplexity. All Perplexity research must be routed through the human.

## How Claude & Antigravity Communicate
To avoid wasting tokens by reading massive, infinitely growing files, we use a chronological file drop system:

1. **Claude to AG:** When Claude needs AG to execute a task, Claude writes a new file: `agent_transfer/C_to_AG_01.md` (incrementing the number each time).
2. **AG to Claude:** When AG finishes the task, hits an error, or needs a decision, AG writes a response file: `agent_transfer/AG_to_C_01.md` (incrementing the number).
3. **Rule:** Do NOT append to old files. Always write a fresh file for a new exchange. Each agent should only need to read the *latest* file from the other agent to know what to do next.

## How to use the Perplexity Human Bridge
Since we cannot query Perplexity natively, we must ask the human to do it for us:
1. When Claude needs external research (e.g. comparing API stacks, evaluating n8n vs Python), Claude writes the prompt as a markdown file in the `perplexity_prompts/` folder (e.g., `perplexity_prompts/01_linkedin_apis.md`).
2. The Human picks up this file, pastes it into Perplexity, and drops the result into `perplexity_responses/`.
3. Claude (or AG) reads the response to inform the next architectural decision.
