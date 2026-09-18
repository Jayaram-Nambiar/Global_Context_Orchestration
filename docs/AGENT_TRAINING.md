# AI Agent Behavioral Training & Operational Manual

This manual trains AI coding agents (such as Antigravity, Cursor, OpenCode, and Claude Code) to achieve maximum token efficiency, near-zero hallucination rates, and deterministic execution when operating in repositories equipped with **Agent Context Engine (`ctx`)**.

---

## 1. The Core 4-Stage Agent Loop

Every coding task must be executed through the **Context-Optimal Loop**:

```
 ┌───────────────┐      ┌────────────────┐      ┌───────────────┐      ┌───────────────┐
 │ 1. MAP        │      │ 2. QUERY       │      │ 3. SLICE      │      │ 4. CHECK      │
 │ Run `ctx map` │ ───► │ Run `ctx query`│ ───► │ Run `ctx slice│ ───► │ Run `ctx check│
 │ Inspect JSON  │      │ Locate symbol  │      │ Read only lines│     │ Verify syntax │
 └───────────────┘      └────────────────┘      └───────────────┘      └───────────────┘
```

### Stage 1: MAP (Global Structural Acquisition)
- **Directive**: Never begin a task by opening random files or executing recursive directory walks.
- **Action**: Run `ctx map` via terminal tools.
- **Cognitive Process**: Read the generated `.agent-context.json`. Review file paths, classes, and exported functions. Identify which modules own the domain logic needed for the user's prompt.

### Stage 2: QUERY (Instant Symbol Pinpointing)
- **Directive**: If searching for a known method, class name, or API call, do not use `grep` across the entire filesystem.
- **Action**: Run `ctx query <symbol_name>`.
- **Cognitive Process**: `ctx query` returns the exact relative file path and line number of the definition.

### Stage 3: SLICE (Surgical, Line-Bounded Ingestion)
- **Directive**: **NEVER dump or view full source files exceeding 150 lines.**
- **Action**: Use `ctx slice <file> <start_line> <end_line>` or your editor's line-range read tools.
- **Cognitive Process**: Ingest only the target function or block. For instance, if modifying `processPayment` at line 140 of a 600-line file, read lines 135 through 180.

### Stage 4: CHECK (Pre-Completion Syntax Interception)
- **Directive**: Never return to the user or claim "Task complete!" without verifying syntax.
- **Action**: Execute `ctx check` in the terminal.
- **Cognitive Process**: If `ctx check` returns exit code 0 (`[PASS]`), proceed to complete the turn. If it returns exit code 1 (`[FAIL]`), read the specific line and syntax error message, fix the code immediately, and re-run `ctx check`.

---

## 2. Anti-Patterns vs. Best Practices

| Anti-Pattern (Inefficient / Hallucinatory) | Best Practice (Context-Optimized) |
| :--- | :--- |
| Reading a 700-line file to check a function's arguments. | Reading `.agent-context.json` or running `ctx query <func>`. |
| Running broad recursive text searches (`grep -rn "def "`). | Inspecting the structured `.agent-context.json` symbol map. |
| Asking the user: *"Where is the auth handler located?"* | Finding `auth` in `.agent-context.json` via `ctx query auth`. |
| Proposing code edits and waiting for the user to report syntax errors. | Running `ctx check` locally to intercept syntax errors automatically. |
| Reading unchanged dependency files "just in case". | Relying on extracted class and inheritance signatures. |

---

## 3. Case Study: Comparative Execution Transcripts

### Scenario
The user asks: *"Add a retry parameter to the `sendNotification` function in the notification service."*

### Naive Agent (Traditional Approach)
1. Agent runs `ls -la` across directories (250 tokens).
2. Agent opens `notification_service.py` (850 lines = ~3,200 tokens).
3. Agent opens `config.py` (300 lines = ~1,100 tokens).
4. Agent opens `handlers.py` (500 lines = ~2,000 tokens).
5. Agent edits `notification_service.py`, introducing an indentation error.
6. Agent responds: *"I have updated the function!"* (Total turn tokens: ~7,500).
7. User runs script, hits `IndentationError`, and pastes back error.
8. Agent responds: *"I apologize for that mistake..."* (Total turn tokens: ~14,000).

### Context-Optimized Agent (Using `ctx`)
1. Agent runs `ctx map` -> `.agent-context.json` generated in 0.05s.
2. Agent runs `ctx query sendNotification`:
   ```
   [ctx query] Found 1 match(es) for 'sendNotification':
     src/notification_service.py:112 -> fn sendNotification(userId, message)
   ```
3. Agent reads lines 110 to 140 via `ctx slice src/notification_service.py 110 140` (~150 tokens).
4. Agent surgically applies the parameter edit.
5. Agent runs `ctx check`:
   ```
   [ctx check] Validating syntax for 1 file(s)...
     [PASS] src/notification_service.py (Python)
   [ctx check SUCCESS] All 1 inspected file(s) passed syntax validation.
   ```
6. Agent responds directly with the diff and confirmation.
7. **Result**: Completed in **under 800 tokens**, 0 user friction, 0 hallucination loops.

---

## 4. System Prompt Directives for Agent Configuration

Include the following directive block in any system prompt, custom instruction set, or rules profile:

```markdown
# AGENT TOKEN OPTIMIZATION DIRECTIVE
- Run `ctx map` before inspecting workspace files.
- Consult `.agent-context.json` for symbol hierarchies and cross-boundary network/shell hooks.
- Never read files >150 lines in full; use `ctx slice <file> <start> <end>` for targeted inspection.
- Always run `ctx check` after modifying code to catch and fix syntax errors locally before responding.
```

---

## 5. Durable repo memory

Before changing MCP protocol, editor install, or engine bounds, read:

- `docs/AGENT_MEMORY.md` — hard-won failure modes (stdout isolation, dual-era `server/discover`, VS Code `servers` vs `mcpServers`, Claude Code `~/.claude.json`)
- `AGENTS.md` — loop + constraints for this repository
- Official spec: [MCP 2026-07-28 key changes](https://modelcontextprotocol.io/specification/2026-07-28/changelog)

When you learn a new invariant, **append a dated entry to `docs/AGENT_MEMORY.md`**. Do not rely on chat transcripts.
