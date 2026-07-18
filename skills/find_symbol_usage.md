# skill: find_symbol_usage

## objective
Locate where a symbol is used across the project and determine how it is being referenced.

The symbol may be a function, class, method, constant, config key, module-level object, or a named export.  
The goal is to help the agent understand whether a symbol is isolated, widely reused, part of a public interface, or likely safe to modify.

## when_to_activate
Activate when:
- the user asks where a function, class, variable, or module is used
- the agent needs to estimate the impact of renaming or modifying a symbol
- the agent needs to confirm whether a piece of code is actually in use
- the agent suspects a symbol is part of a shared interface
- a dead-code or impact-analysis task depends on accurate usage mapping

## required_inputs
- symbol name
- optional symbol type:
  - function
  - class
  - method
  - variable
  - constant
  - module
  - config key
- optional file path or module where the symbol is defined
- repository search access

## allowed_tools
- search_code(query)
- read_file(path)
- read_multiple_files(paths)
- find_references(symbol)
- list_repo_tree()

## procedure
1. Identify the target symbol and, if possible, the defining file/module.
2. Determine whether the search should be:
   - exact symbol match
   - scoped to a module/file
   - case-sensitive or language-aware
3. Search the repository for references to the symbol.
4. Separate likely usage categories:
   - import statements
   - direct function/class calls
   - method calls
   - inheritance / subclassing
   - object construction
   - config lookup or constant access
   - comments/docs only
5. Exclude obvious false positives where possible:
   - plain text mentions in docs/comments
   - unrelated variables with the same short name in other scopes
   - string mentions that are not actual references, unless the symbol is dynamically resolved
6. Group matches by file and usage type.
7. Identify whether the symbol appears to be:
   - local/private
   - module-internal
   - reused by a small set of files
   - widely shared across the project
   - exposed through a public interface
8. If the symbol appears unused, verify whether it may still be referenced dynamically:
   - getattr / reflection-like patterns
   - registry lookups
   - config-based dispatch
   - framework auto-discovery
9. Produce a usage map with confidence notes where needed.

## validations
Before finishing, verify:
- whether all found references are real code references or just text matches
- whether the symbol is imported under an alias
- whether dynamic usage is plausible in this project
- whether the symbol is part of a base class or shared utility layer
- whether “unused” actually means unused, or only “not statically referenced”

## expected_output
The output must contain:

### target_symbol
name, type if known, and defining module/file if known

### usage_summary
brief summary of how broadly the symbol is used

### usage_by_file
list of files and the type of usage found in each one

### usage_classification
one of:
- UNUSED_OR_NEAR_UNUSED
- LOCAL_ONLY
- SHARED_IN_SMALL_SCOPE
- WIDELY_REUSED
- POSSIBLY_DYNAMIC_USAGE

### risk_notes
important caveats, false-positive risks, or dynamic-usage concerns

### recommendation
one of:
- safe_to_modify_locally
- inspect_callers_before_modifying
- treat_as_shared_interface
- verify_dynamic_usage_before_removal

## limits
- Do not assume every text match is a real usage.
- Do not conclude “dead code” from a single grep result.
- Do not ignore dynamic or framework-driven references if the project style suggests they exist.
- Do not rename or modify the symbol in this skill.

## escalation
If the user wants to remove or refactor the symbol after usage analysis, recommend:
- map_change_impact

If the symbol appears unused and the user wants cleanup, recommend:
- find_dead_code