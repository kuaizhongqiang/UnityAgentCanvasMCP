# Planning Document Structure Guidelines

## Minimal Overview Format

When writing the initial overview for a new feature/module:

```markdown
# {Feature Name}

{One sentence: what it does.}

{One sentence: scope boundary - what's in, what's out.}

{Optional: one sentence on how it connects to existing systems.}
```

Keep it to 3 sentences maximum. Do not expand until user confirms.

## Full Document Structure

After overview is confirmed, expand using this template:

```markdown
# {Title}

## Overview

{2-3 paragraph summary}

## Motivation

{Why this exists, what problem it solves}

## Design

### Architecture

{How it fits in the MCV framework or where it deviates}

### Data Model

{New classes, fields, relationships}

### API / Interface

{How other modules interact with it}

## Implementation Plan

{Ordered steps, dependencies, estimated effort}

## Open Questions

{Unresolved decisions or unknowns}
```

## Placement Rules

| If the document is about... | Place in... | Example |
|:--|:--|:--|
| Framework architecture | `Plan/Architecture/` | MCV pattern, scene pipeline |
| Business logic / user-facing flows | `Plan/Business/` | Roaming, step system |
| Technical modules / systems | `Plan/Modules/` | UI framework, interactive system |
| Data schemas / formats | `Plan/Data/` | JSON schema, enums |
| How-to guides for developers | `Plan/Guides/` | New experiment, new panel |

## Reference Conventions

- Link to existing docs instead of repeating content
- Use relative paths: `[MCV Architecture](../Architecture/MCV.md)`
- Cross-reference Related Work section at document end if applicable
