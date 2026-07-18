# skill: analyze_traceback

## objective
Analyze an exception, traceback, or error log to identify the most likely root cause, separate primary failure from secondary failures, and determine which file or module should be inspected first.

## when_to_activate
Activate when:
- the user provides a traceback, stacktrace, or runtime exception
- the agent sees an execution error from tests, scripts, or runtime logs
- the failure origin is unclear and needs triage

## required_inputs
- traceback, stacktrace, or error log
- optional repository access
- optional target file if already known

## allowed_tools
- read_file(path)
- search_code(query)
- find_references(symbol)
- read_multiple_files(paths)

## procedure
1. Parse the traceback or error log.
2. Extract:
   - exception type
   - message
   - file paths
   - line numbers
   - call order if available
3. Separate:
   - primary failure candidate
   - cascading/secondary failures
4. Identify the earliest meaningful frame that belongs to project code rather than external libraries, unless the external call is itself the source of the issue.
5. Inspect the file and function around the likely failing frame.
6. Determine whether the failure is likely caused by:
   - bad input/data shape
   - missing symbol or import
   - invalid state
   - unexpected None/null value
   - config issue
   - caller/contract mismatch
   - bug in the shown file
   - bug in an upstream file
7. If needed, inspect one or two directly related files only.
8. Produce a root-cause-oriented diagnosis, not just “the line that crashed”.

## validations
Before finishing, verify:
- whether the shown line is the real origin or just the crash point
- whether the failure is triggered by bad upstream data
- whether the exception comes from a missing dependency or config
- whether multiple errors are actually symptoms of the same root issue

## expected_output
The output must contain:

### exception_summary
type, message, and failing context

### likely_root_cause
best technical explanation of the underlying issue

### primary_target_to_inspect
file/module/function that should be inspected first

### secondary_context
other files or factors worth checking if needed

### recommended_next_step
one of:
- audit_target_module
- inspect_upstream_caller
- inspect_config_or_data_source
- broader_dependency_check

## limits
- Do not assume the last frame is always the root cause.
- Do not produce a fix yet unless the user explicitly asked for one.
- Do not inspect unrelated files just because they appear in the same stack.

## escalation
If the failing target is a Python module, recommend:
- audit_python_module

If the likely fix touches shared logic, recommend:
- map_change_impact