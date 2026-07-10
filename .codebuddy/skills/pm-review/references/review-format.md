# Review Document Format

## Header

Every review document starts with:

```markdown
# {Module Name} - Code Review

| Field | Value |
|:--|:--|
| Date | YYYY-MM-DD |
| Version | {N} |
| Reviewer | {name} |
| Scope | {what was reviewed} |
```

## Finding Entry Format

```markdown
### [{Severity}] {Title}

- **Location**: `path/to/file.cs:10-25`
- **Problem**: Clear description of what's wrong.
- **Suggestion**: Concrete fix or approach.

{Optional detailed explanation}
```

## Severity Levels

| Severity | Icon | When to Use |
|:--|:--|:--|
| Critical | [!!] | Will cause runtime errors, data loss, or blocks other work |
| Major | [!] | Architectural problem, pattern violation, will cause issues |
| Minor | [~] | Code quality, inconsistency, not urgent |
| Suggestion | [?] | Improvement idea, optional |

## Grouping

Findings grouped by severity section:

```markdown
## Critical

### [Critical] {Title}
...

## Major

### [Major] {Title}
...

## Minor

### [Minor] {Title}
...

## Suggestions

### [Suggestion] {Title}
...
```

## Summary Section

End each review with:

```markdown
## Summary

- **Critical**: {N}
- **Major**: {N}
- **Minor**: {N}
- **Suggestions**: {N}

### Top Priority

1. {most important finding}
2. {second most important}
```

## Version History

The version field in the header tracks review cycles:
- Version 1: first review of the module
- Version 2: re-review after fixes, old content fully replaced
- Each re-review gets a new header row (date + version) and completely fresh content

The date changes on each re-review. The version number increments.

## Example

```markdown
# GlobalDataMgr - Code Review

| Field | Value |
|:--|:--|
| Date | 2026-07-05 |
| Version | 1 |
| Reviewer | PM Review Skill |
| Scope | GlobalDataMgr.cs, ProjectData.cs, SystemData.cs, UserData.cs |

## Critical

### [Critical] Initialization Missing

- **Location**: `Scripts/GlobalManager/GlobalDataMgr.cs:21-27`
- **Problem**: `DelayInit()` only loads `SystemData`. `ProjectData` and `UserData` are defined but never loaded from JSON.
- **Suggestion**: Add `JsonReaderWriter.Read<ProjectData>("ProjectData")` and `JsonReaderWriter.Read<UserData>("UserData")` in `DelayInit()`.

## Major

### [Major] WriteJson is Dead Code

- **Location**: `Scripts/GlobalManager/GlobalDataMgr.cs:62-67`
- **Problem**: `WriteJson()` method exists but is commented out in `DelayInit()`. If needed, it should be callable; if not, it should be removed.
- **Suggestion**: Either expose as public API or delete.

## Minor

(empty)

## Suggestions

### [Suggestion] Static Methods Should Be Extension Methods

- **Location**: `Scripts/GlobalManager/GlobalDataMgr.cs:30-58`
- **Problem**: Static helper methods pollute the manager class namespace.
- **Suggestion**: Consider moving `GetTaskData()` helpers to extension methods on `ProjectData`.

## Summary

- **Critical**: 1
- **Major**: 1
- **Minor**: 0
- **Suggestions**: 1

### Top Priority

1. Complete ProjectData and UserData loading in DelayInit
2. Decide fate of WriteJson (implement or remove)
```
