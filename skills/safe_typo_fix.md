# skill: safe_typo_fix

## objective
Correct spelling, grammar, punctuation, and small wording issues only in text areas that are safe to edit without changing program behavior.

This skill is designed for low-risk textual cleanup in:
- comments
- docstrings
- user-facing messages
- README-like inline text
- help strings
- log or UI text, if explicitly allowed by the user

It must avoid touching identifiers, config keys, paths, and any text that may be semantically significant for execution.

## when_to_activate
Activate when:
- the user asks to fix typos or wording without changing logic
- the agent detects obvious spelling issues in comments, docstrings, or user-facing text
- a file needs cleanup of explanatory text but not behavioral changes
- documentation text embedded in code needs correction

## required_inputs
- target file(s)
- optional allowed text zones:
  - comments only
  - comments + docstrings
  - comments + docstrings + user-facing strings
- optional language preference for corrections
- explicit instruction whether log strings or UI messages may be edited

## allowed_tools
- read_file(path)
- read_multiple_files(paths)
- diff_against_original(path, content)

## procedure
1. Read the target file(s).
2. Identify text regions that are potentially safe to edit:
   - comments
   - docstrings
   - explanatory block comments
   - user-facing messages if allowed
3. Exclude text regions that may affect behavior or contracts:
   - variable names
   - function names
   - class names
   - import names
   - config keys
   - JSON/YAML keys embedded in strings
   - file paths, URLs, selectors, IDs, regexes, SQL fragments, shell commands
   - machine-parsed prompts or templates unless explicitly approved
4. For each editable text region:
   - fix obvious spelling mistakes
   - improve punctuation where clearly broken
   - fix grammar only when the intended meaning is clear
   - preserve the original meaning and technical intent
5. Keep edits conservative:
   - do not rewrite whole paragraphs unless the user explicitly asked for rewriting
   - do not “improve style” beyond typo-level cleanup
6. If a string may be shown to users and editing it could affect tests, snapshots, matching logic, or expected outputs, flag it instead of changing it unless explicitly allowed.
7. Produce a corrected version of the file with only safe text edits.

## validations
Before finishing, verify:
- whether each modified segment is truly non-executable text
- whether a string is used for matching, parsing, tests, or protocol communication
- whether a log/UI message is part of assertions or snapshots
- whether the correction preserves the original technical meaning
- whether any edited text could break localization or templating placeholders

## expected_output
The output must contain:

### target_files
files reviewed and edited

### edited_text_zones
what kinds of text were modified:
- comments
- docstrings
- user-facing strings
- other safe text areas

### skipped_risky_zones
strings or areas intentionally left unchanged due to execution risk

### change_summary
brief summary of typo/wording fixes applied

### corrected_code
full corrected file content

## limits
- Never change identifiers or executable logic.
- Do not rewrite large text blocks unless explicitly requested.
- Do not touch config keys, placeholders, selectors, commands, or parser-sensitive strings.
- Do not edit UI/log strings that may be asserted in tests unless the user explicitly allows it.

## escalation
If the user wants broader text rewriting rather than typo-level cleanup, recommend a dedicated documentation or text-rewrite workflow instead of this skill.

If risky strings or config-like text need review, recommend:
- validate_config_file