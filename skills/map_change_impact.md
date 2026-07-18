# skill: map_change_impact

## objective
Determine the likely impact of modifying a file, module, class, function, or configuration element before proposing or applying changes.

The goal is to identify inbound and outbound dependencies, likely affected files, public interfaces, and possible collateral effects.

## when_to_activate
Activate this skill when:
- the user asks to modify or fix an existing file or module
- a bug appears to be tied to a specific file or symbol
- the agent suspects the fix may affect more than one file
- the user asks for dependency analysis, impact estimation, or risk assessment
- the target file belongs to a core/shared area of the project

## required_inputs
- target file path, module name, or symbol name
- optional traceback or bug description
- repository tree access
- ability to inspect references/imports/usages

## allowed_tools
- read_file(path)
- list_repo_tree()
- search_code(query)
- find_references(symbol)
- extract_import_graph(path)
- find_symbol_usage(symbol)
- find_config_references(key)

## procedure
1. Identify the target:
   - file
   - module
   - class
   - function
   - config key or constant
2. Read the target file or the file that contains the target symbol.
3. Extract outbound dependencies:
   - imports
   - referenced modules
   - external config keys
4. Extract inbound dependencies:
   - who imports this module
   - who calls this function or class
   - where the symbol is referenced
5. Detect whether the target is part of a public/shared interface.
6. Check for project-wide references to the relevant symbols.
7. Build a compact impact map:
   - directly affected files
   - likely indirectly affected files
   - shared interfaces or contracts touched by the change
8. Classify impact:
   - LOCAL: likely limited to current file or isolated logic
   - COUPLED: likely affects a small set of related files
   - TRANSVERSAL: likely affects multiple subsystems or shared contracts
9. Identify risk factors:
   - widely reused function/class
   - central config or shared constants
   - public API surface
   - initialization/bootstrap code
   - serialization formats or data contracts
10. Recommend one of:
   - safe to fix locally
   - fix locally but inspect related files first
   - do not edit yet; broader audit needed

## validations
Before finishing, verify:
- whether the target is imported or referenced from multiple places
- whether the change affects a public or shared symbol
- whether the change touches config or data contracts
- whether the bug may actually originate from an upstream dependency

## expected_output
The output must contain:

### target
target file/module/symbol

### outbound_dependencies
key modules, files, or configs used by the target

### inbound_dependencies
who depends on or references the target

### impact_classification
LOCAL / COUPLED / TRANSVERSAL

### risk_points
specific risks detected

### recommendation
one of:
- safe_local_fix
- inspect_related_files_first
- broader_audit_required

## limits
- Do not modify files.
- Do not propose large refactors.
- Do not assume a dependency exists unless it can be verified.
- Do not confuse “same folder” with “real dependency”.

## escalation
If the target is a Python file with a likely logic or syntax bug, recommend running:
- audit_python_module

If the issue is driven by an exception or stacktrace, recommend:
- analyze_traceback