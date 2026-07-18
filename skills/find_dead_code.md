# skill: find_dead_code

## objective
Identify code that appears to be unused, unreachable, obsolete, or disconnected from the active project flow.

This includes potentially dead:
- modules
- functions
- classes
- methods
- imports
- constants
- branches
- legacy helper code

The goal is to flag suspicious code safely, not to delete it automatically.

## when_to_activate
Activate when:
- the user asks to find unused or dead code
- the agent needs to clean up a codebase
- the agent suspects old modules are still present but no longer connected
- the agent wants to audit orphan files or unused functions before refactoring
- a large project has accumulated abandoned helpers, experiments, or obsolete paths

## required_inputs
- repository access
- optional target scope:
  - whole repo
  - folder
  - file
  - module
- optional language context
- ability to search symbol usage and imports

## allowed_tools
- list_repo_tree()
- read_file(path)
- read_multiple_files(paths)
- search_code(query)
- find_references(symbol)
- find_symbol_usage(symbol)
- extract_import_graph(path)

## procedure
1. Determine the scope of the dead-code audit:
   - full repository
   - specific folder
   - specific module/file
2. Identify candidate targets:
   - modules not imported anywhere obvious
   - functions/classes with no references
   - imports that are never used
   - constants never referenced
   - branches guarded by always-false conditions or obsolete flags
3. For each candidate, gather evidence:
   - where it is defined
   - whether it is imported or called
   - whether it is part of an interface, registry, plugin, or framework hook
   - whether it is referenced only by tests, scripts, or docs
4. Classify each candidate into one of these categories:
   - ORPHAN_MODULE
   - UNUSED_FUNCTION_OR_CLASS
   - UNUSED_IMPORT
   - UNUSED_CONSTANT
   - POSSIBLY_UNREACHABLE_BRANCH
   - LEGACY_OR_DUPLICATE_HELPER
5. For each candidate, look for exceptions before marking it as dead:
   - dynamic imports
   - string-based dispatch
   - reflection/registry use
   - plugin auto-registration
   - framework conventions
   - CLI entry points
   - test-only or migration-only usage
6. Estimate confidence:
   - HIGH: strong evidence of no usage
   - MEDIUM: likely unused but with some uncertainty
   - LOW: suspicious but dynamic usage cannot be ruled out
7. Produce a dead-code report ordered by confidence and cleanup safety.

## validations
Before finishing, verify:
- whether a supposedly unused module is actually invoked dynamically
- whether a symbol is used only in tests, scripts, migrations, or entrypoints
- whether an import is unused only because a side effect is expected
- whether an apparently dead branch is actually gated by runtime config
- whether “not referenced” is due to incomplete search scope

## expected_output
The output must contain:

### audit_scope
what part of the project was inspected

### candidates
list of suspected dead-code candidates with:
- type
- location
- confidence
- short reason

### exceptions_or_uncertainties
dynamic usage risks, framework caveats, side-effect imports, or other reasons to be careful

### safe_cleanup_candidates
items with strongest evidence and lowest risk

### review_before_removal
items that need manual review before deletion

### recommendation
one of:
- safe_partial_cleanup
- cleanup_with_manual_review
- do_not_remove_without_deeper_analysis

## limits
- Do not delete code in this skill.
- Do not label something as dead only because it has no direct caller in one search pass.
- Do not ignore side-effect imports, framework hooks, or registry-based usage.
- Do not mix “ugly code” with “dead code”; this skill is about usage and reachability, not style.

## escalation
If the user wants to remove confirmed dead code, recommend:
- map_change_impact
- apply_local_fix

If a suspicious item depends on a symbol-usage decision, recommend:
- find_symbol_usage