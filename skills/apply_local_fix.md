# skill: apply_local_fix

## objective
Apply a minimal, localized fix to a previously diagnosed problem without broad refactoring, unnecessary renaming, or unrelated cleanup.

## when_to_activate
Activate only when:
- a plausible diagnosis already exists
- the user has explicitly approved editing
- the change is expected to be local or narrowly scoped
- the agent knows which file(s) should be touched

## required_inputs
- target file(s)
- prior diagnosis
- minimal fix strategy
- optional impact analysis result
- explicit user approval to edit

## allowed_tools
- read_file(path)
- write_file(path, content)
- diff_against_original(path, content)
- run_linter(target)
- run_tests(target)

## procedure
1. Re-read the target file before editing.
2. Locate the exact code region tied to the diagnosed issue.
3. Apply only the minimal change needed to resolve the problem.
4. Preserve whenever possible:
   - public names
   - module structure
   - comments that remain valid
   - compatibility with existing callers
5. Do not use the edit as an excuse to:
   - reorder unrelated code
   - rename symbols for style
   - “clean up” dead code
   - rewrite neighboring logic
6. If the fix unexpectedly requires touching additional files:
   - check whether that was already predicted
   - if not, stop and report the scope expansion
7. Validate the edited result with available lightweight checks.
8. Return the full corrected file(s), not isolated fragments.

## validations
Before finishing, verify:
- the change addresses the diagnosed issue and not a guessed one
- no unnecessary identifiers were changed
- no new dependency was introduced without need
- no unrelated behavior was altered
- no public interface was silently broken

## expected_output
The output must contain:

### change_summary
what was fixed and why

### modified_files
exact files changed

### residual_risks
anything that still deserves review

### corrected_code
full corrected file content

## limits
- Never edit without explicit approval.
- Do not expand the scope on your own.
- Do not refactor unless the bug truly requires it.
- Do not delete suspicious code unless a separate audit explicitly concluded it is safe.

## escalation
If the fix stops being local during editing, stop and recommend:
- map_change_impact
- audit_python_module