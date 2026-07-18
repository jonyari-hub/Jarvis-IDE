# skill: validate_config_file

## objective
Inspect a configuration file for syntax issues, structural inconsistencies, suspicious values, missing required fields, duplicate keys when detectable, and obvious contract mismatches.

This skill is meant for configuration-like files such as:
- JSON
- YAML / YML
- TOML
- INI / CFG
- ENV-style key-value files
- lightweight app config modules, if treated as pure configuration

The goal is to validate configuration safely and point to likely problems without inventing schema rules that do not exist.

## when_to_activate
Activate when:
- the user asks to review a config file
- a bug may come from JSON/YAML/TOML/INI/.env settings
- a module depends on external configuration and behavior looks inconsistent
- the agent sees parsing errors or suspicious config values
- a deployment or runtime issue may be caused by misconfigured keys or types

## required_inputs
- target config file path
- optional known config type:
  - json
  - yaml
  - toml
  - ini
  - env
- optional expected schema, required keys, or sample valid config
- optional error message or parser output if available

## allowed_tools
- read_file(path)
- read_multiple_files(paths)
- search_code(query)
- find_config_references(key)

## procedure
1. Identify the config file type.
2. Read the file completely.
3. Perform syntax-level validation appropriate to the file type:
   - malformed JSON structure
   - invalid YAML indentation or malformed blocks
   - TOML section/value problems
   - malformed INI structure
   - broken key-value lines in ENV-like files
4. Identify structural issues:
   - missing expected top-level sections if known
   - suspicious nesting
   - duplicated keys if detectable from raw text or parser behavior
   - empty required-looking values
   - obviously malformed arrays, maps, or scalars
5. If the expected config contract is known, compare against it:
   - missing required keys
   - unexpected key names close to known names
   - wrong value shape/type where inferable
   - inconsistent enum-like values
6. Search code references if needed to understand expected keys or shapes.
7. Separate findings into:
   - syntax errors
   - structural problems
   - suspicious values
   - contract mismatches
8. If no formal schema exists, keep conclusions conservative and clearly label assumptions.

## validations
Before finishing, verify:
- whether the file type was correctly identified
- whether a “missing key” is truly required or just optional in this project
- whether a suspicious value is invalid or merely environment-specific
- whether duplicate keys are real and not part of repeated sections or list items
- whether comments or templating syntax could affect parsing expectations

## expected_output
The output must contain:

### target_file
path and detected config type

### syntax_status
one of:
- valid_syntax
- syntax_errors_detected
- unable_to_confirm_safely

### findings
grouped list of:
- syntax errors
- structural issues
- suspicious values
- likely contract mismatches

### keys_or_sections_to_review
specific keys, blocks, or sections worth checking

### confidence_notes
what is confirmed vs what is inferred

### recommendation
one of:
- config_looks_valid
- review_specific_keys
- likely_config_bug
- schema_or_contract_check_needed

## limits
- Do not rewrite the config in this skill unless the user explicitly asks for correction.
- Do not invent required keys or schema rules without evidence.
- Do not assume a suspicious value is wrong if it may be environment-dependent.
- Do not silently normalize formatting and call it validation.

## escalation
If the user wants the config corrected after validation, recommend:
- apply_local_fix

If config keys appear unused or inconsistent with code expectations, recommend:
- find_symbol_usage
- map_change_impact