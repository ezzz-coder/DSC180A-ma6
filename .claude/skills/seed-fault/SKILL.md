---
name: seed-fault
description: Seed one deliberate fault in src/, record whether the PostToolUse hook and the test suite catch it, restore the code, and append the real output to docs/SEEDED_FAULTS.md. Use when asked to seed, plant, inject or test a fault. Argument is a description of the fault, e.g. "drop the shift(1) from cnt_roll_28".
argument-hint: <fault description>
allowed-tools: Read, Edit, Bash(python -m pytest*), Bash(make*), Bash(git diff*), Bash(git status*), Bash(shasum*)
---

# Seed a fault: $ARGUMENTS

The point is evidence, not a fix: does anything go red, and what exactly does
it say? Paste real output only. Never paraphrase it.

1. **Preconditions.** `git status --short src/ tests/` must be empty and
   `make test` green. If not, stop and say why: a fault seeded on a dirty
   tree cannot be cleanly restored or attributed.

2. **Seed it with one `Edit`** to a file under `src/`, implementing
   "$ARGUMENTS" as literally as possible. Use the Edit tool, never Bash: the
   PostToolUse hook only watches Edit/Write. Never touch `data/raw/` or
   `tests/`. If the description needs either, stop and say so instead.
   If it is ambiguous, pick the most literal reading and state it.

3. **Record the hook.** Copy the hook's stderr verbatim from the system
   message after the edit. If none appeared, record "hook did not fire".

4. **Record the suite.** Run `make features` then `make test`, and keep
   the `E ` assertion lines, the `FAILED` lines and the final count. If
   everything passes, that is the finding: say plainly that nothing caught it.

5. **Restore.** Undo the edit with one `Edit`. Then `git diff src/` must be
   empty, `make features && make test` green, and `shasum -a 256
   data/raw/bike_daily.csv` must start `a6bed1577f6e4de5`. Count the turns
   from seeding to green again.

6. **Append** a section to `docs/SEEDED_FAULTS.md`:

   ````
   ## Fault N: <short name>

   Change:
   ```diff
   <the one-line diff>
   ```
   Hook stderr: <verbatim, or "none: the hook did not fire">
   `make test`: <verbatim E/FAILED/count lines>
   Turns to fix: <n> (the seeding agent knew the fault; this is a lower bound)
   What would catch it, if nothing did: <one concrete test or check>
   ````

7. **Report** in three lines: caught by the hook (y/n), caught by the suite
   (which test, or none), and whether the restore verified clean.

Do not report test-set metrics, and do not run `make train`: a fault drill is
not a reason to look at H2 2012.
