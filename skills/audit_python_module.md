# skill: audit_python_module

## objective
Audit a Python module to detect likely errors, inconsistencies, or fragile logic, and propose a minimal correction path without editing the file.

## when_to_activate
Activate when:
- the user asks to review a Python file
- a Python module is suspected to be broken
- a traceback points to a Python file
- a recent change may have broken a Python module
- the agent needs to understand a Python module before editing it

## required_inputs
- path to the Python file
- optional traceback or observed error
- optional expected behavior description
- optional previous impact analysis

## allowed_tools
- read_file(path)
- read_multiple_files(paths)
- search_code(query)
- find_references(symbol)
- extract_import_graph(path)
- run_linter(target)
- run_tests(target)

## procedure
1. Read the entire Python file.
2. Identify:
   - imports
   - classes
   - functions
   - constants/config
   - side effects at import time
3. If a traceback exists:
   - locate the relevant line/function
   - inspect surrounding logic
   - do not assume the shown line is the root cause
4. Classify the likely issue:
   - syntax error
   - missing or broken import
   - circular import
   - undefined name
   - missing attribute
   - invalid return shape
   - inconsistent parameter usage
   - broken control flow
   - incorrect state mutation
   - typo in safe text-only area
5. Check internal consistency:
   - names used vs names defined
   - called functions vs imported symbols
   - function signatures vs actual usage
   - expected return values vs downstream use
6. If needed, inspect a minimal set of related files:
   - the file that imports this module
   - the file providing a missing symbol
   - a config file referenced by the module
7. Determine whether the issue is:
   - LOCAL_TO_MODULE
   - CAUSED_BY_RELATED_MODULE
   - POSSIBLY_SYSTEMIC
8. Produce a concise diagnosis and a minimal correction strategy.

## validations
Before finishing, verify:
- whether the apparent error is caused by a missing import or bad caller
- whether a renamed function/class broke compatibility
- whether the issue is caused by config/data shape rather than code syntax
- whether the fix would change a public interface

## expected_output
The output must contain:

### module_summary
what the module appears to do

### detected_problem
technical description of the likely problem

### probable_cause
why it is happening

### scope
LOCAL_TO_MODULE / CAUSED_BY_RELATED_MODULE / POSSIBLY_SYSTEMIC

### minimal_fix_strategy
what should be changed and where

### related_files_to_review
only if needed

## limits
- Do not edit the file.
- Do not refactor the module unless the bug requires it.
- Do not rename public symbols without strong justification.
- Do not mix stylistic suggestions with the core bug diagnosis.

## escalation
If the issue came from a stacktrace or exception flow, recommend:
- analyze_traceback

If the module appears widely reused, recommend:
- map_change_impact