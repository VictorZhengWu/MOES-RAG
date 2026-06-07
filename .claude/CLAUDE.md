# Marine & Offshore Expert System — Project CLAUDE.md

> Claude Code loads this file automatically at the start of EVERY session.
> It establishes project rules and mandatory session-start procedures.

---

## 0. Project Identity

**Name**: Marine & Offshore Expert System
**Purpose**: Professional RAG intelligent Q&A system for ship and offshore engineering.
**Global CLAUDE.md**: `~/.claude/CLAUDE.md` — contains the full development process specification. This file supplements it with project-specific rules.

---

## 1. Mandatory New-Session Startup Checklist

**CRITICAL: Every new session MUST execute these steps in order BEFORE any coding or decision-making.**

If you are starting a new session for this project, read the following files in this exact order:

### Step 1: Architecture Overview
```
Read .dev/specs/rag-system-design-2026-05-12.md
Focus on: Sections 1-3 (Project Summary, Key Decisions, Architecture)
```
This gives you the complete system architecture, all 8 modules, their responsibilities, interfaces, and the 5-layer dependency model.

### Step 2: Project-Level Decisions
```
Read .dev/decisions.md
```
This recovers all cross-module decisions made outside the design spec, plus any pending or reversed decisions.

### Step 3: Module Status Overview
```
Read .dev/module-memory/index.md
```
This shows which modules are in what state, which are being actively developed, and how many sessions each has had.

### Step 4: Current Module Context
```
Read .dev/module-memory/m<X>-<name>.md  (for the module you're working on)
```
This recovers that module's full development history, key internal decisions, known pitfalls, and open issues.

### Step 5: Task Status
```
Read .dev/tasks.md
```
This shows all tasks, their current status (🔲/🔄/✅/❌), dependencies, and which task to work on next.

### Step 6: Task Test History (if resuming a task)
```
Read .dev/test_records/<NNNNN>.md  (if the current task has previous attempts)
```
This prevents repeating known-failed approaches.

**Violating this checklist = violating project rules. Do not skip steps.**

---

## 2. Project-Specific Rules

### 2.1 System Name
The system is "Marine & Offshore Expert System". Use this name in all user-facing text, documentation, and API branding.

### 2.2 Code Comments (Non-Negotiable)
All source code (Python and TypeScript) MUST include detailed English comments with:
- **WHAT**: What the code does — purpose, inputs, outputs, side effects.
- **WHY**: Why this code exists and why this specific approach was chosen.

See design spec Section 7 for examples and enforcement rules.

### 2.3 Internationalization (i18n)
The Web UI (M6 + M7) supports 5 languages: English (default), Chinese, Korean, Japanese, Norwegian.
- ZERO hardcoded UI strings. Everything goes through i18n resource files.
- Language switching must be instant (no page reload).
- i18n key format: `section.component.element`

See design spec Section 8 for full details.

### 2.4 Module Independence
- Modules communicate ONLY through `contracts/` (Python Protocols + Pydantic schemas).
- Never import directly from another module's src/ directory.
- Each module can be developed, tested, and deployed independently.

### 2.5 Storage Backend Selection
- Storage backends are selected at deploy time via deploy.yaml, never hardcoded.
- Personal mode defaults: ChromaDB + SQLite + Local FS
- Module code depends on Protocols, never on concrete backend classes.

### 2.6 LLM Backend Selection
- LLM backends are user-configurable via admin UI, never hardcoded.
- Support both cloud APIs (DeepSeek, Claude, OpenAI) and local (Ollama, vLLM, LM Studio).

---

## 3. Development Workflow

### 3.1 Before Each Task
1. Complete the startup checklist (Section 1 above).
2. Invoke `superpowers:brainstorming` skill for design analysis.
3. Invoke `superpowers:test-driven-development` skill before writing implementation code.

### 3.2 After Each Task
1. Invoke `superpowers:verification-before-completion` skill.
2. Write test results to `.dev/test_records/<Task编号>.md`.
3. Update `.dev/tasks.md` task status.
4. If any module-internal decisions were made, append to `.dev/module-memory/m<X>-<name>.md`.
5. If any cross-module decisions were made, append to `.dev/decisions.md`.
6. Git commit with format: `[Task编号] <type>: <简短描述>`

### 3.3 When Encountering Bugs or Test Failures
Invoke `superpowers:systematic-debugging` skill before proposing fixes.

### 3.4 Pre-Commit Verification (Hard Gate)

**Before ANY `git commit`, run these checks. If any fail, fix before committing.**

```
# 1. Syntax check (Python)
git diff --name-only HEAD | grep '\.py$' | while read f; do
  python -c "import ast; ast.parse(open('$f', encoding='utf-8').read())" || exit 1
done

# 2. Tests (if the change is in a module with tests)
python -m pytest <module>/tests/ -q

# 3. Spec completeness
test $(ls .dev/specs/m*-design-*.md 2>/dev/null | wc -l) -ge 8
```

**DO NOT commit if:**

- Python syntax check fails (missing parentheses, duplicate decorators, etc.)
- Tests fail or have new errors
- Writing code via `python -c` to modify files blindly — use `Write`/`Edit` tools instead so you can see the result

### 3.5 Session-End Protocol
Before ending a session (context full, task complete, or user requests):
1. Ensure all decisions and progress are written to the appropriate memory files.
2. Run the Pre-Commit Verification checks above.
3. Git commit all changes.
4. The next session will recover all context from files.

---

## 4. Key File Reference

| File | Purpose | When To Read |
|------|---------|-------------|
| `.dev/specs/rag-system-design-2026-05-12.md` | Architecture spec | Every new session |
| `.dev/decisions.md` | Cross-module decisions | Every new session |
| `.dev/module-memory/index.md` | Module status overview | Every new session |
| `.dev/module-memory/m<X>-<name>.md` | Per-module memory | When working on that module |
| `.dev/tasks.md` | Task list & status | Every new session |
| `.dev/test_records/<NNNNN>.md` | Per-task test history | When resuming a task |
| `.dev/planning.md` | Development plan summary | For development phase context |
| `contracts/` | Interface definitions | When crossing module boundaries |

---

## 5. Quick Context Recovery (For You, The Human)

When starting a new Claude Code session for this project, tell Claude:
> "Continue development on Marine & Offshore Expert System. Read the startup checklist in .claude/CLAUDE.md."

Claude will automatically load this file and execute the checklist.
