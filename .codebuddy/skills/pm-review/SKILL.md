---
name: pm-review
description: PM-style planning and code review workflows. Covers two modes: (1) Document Planning - create minimal overviews first, discuss, then refine into full specs; (2) Code Review - analyze existing code and write findings into per-module review documents that are rewritten (not appended) each cycle, with date/version headers. Use when planning new features, writing design docs, reviewing code, or auditing modules.
---

# PM Review

## Overview

Two distinct workflows:

| Mode | Trigger | Rule |
|:--|:--|:--|
| **Document Planning** | New feature, spec, or design doc needed | Minimal overview first, discuss, then expand |
| **Code Review** | Audit existing code in a module | One review doc per module, always rewrite |

## Document Planning Workflow

When asked to plan new content, write a spec, or design a feature:

### Step 1: Write Minimal Overview

Write **2-3 sentences** maximum covering:
- What it does (one line)
- Key scope/boundary (what's in, what's out)

Present only the overview. Do NOT expand yet.

### Step 2: Discuss

After user reviews the overview, ask clarifying questions:
- What's unclear or missing?
- Any constraints not mentioned?
- Priority relative to other work?

### Step 3: Expand

Only after user confirms the overview, expand into full document. Follow the project wiki structure in `Assets/Documents/Plan/` for placement:
- Architecture docs -> `Plan/Architecture/`
- Business module docs -> `Plan/Business/`
- Feature module docs -> `Plan/Modules/`
- Guides -> `Plan/Guides/`

When creating the full document, reference `references/planning-format.md` for structure guidelines.

## Code Review Workflow

When asked to review a module's code:

### Step 1: Analyze

Read all source files in the target scope. Identify:
- Structural issues (coupling, responsibility, naming)
- Pattern violations (does it follow MCV? Singleton conventions?)
- Missing or incomplete implementations
- Data flow problems

### Step 2: Generate Review Document

Use the script to scaffold the document:

```powershell
python .codebuddy/skills/pm-review/scripts/generate_review.py {module-name}
```

This creates `Assets/Documents/Plan/Reviews/{module-name}.md` with proper header.

If the file already exists: **overwrite it entirely**. Never append to an existing review.

### Step 3: Write Review Content

Fill the generated document with findings. Each finding must include:

```
### [Finding Title]

- **Severity**: Critical / Major / Minor / Suggestion
- **Location**: File path + line range
- **Problem**: What's wrong
- **Suggestion**: How to fix
```

Group findings by severity (Critical first).

### Step 4: Present Summary

After writing the document, present a brief summary:
- Total findings count by severity
- Top 2-3 most important issues
- Link to the full review document

## Review Document Rules

1. **One file per module** ！ `Reviews/{module-name}.md`
2. **Always rewrite** ！ erase old content, write fresh. Version header tracks history.
3. **Header contains**: date (YYYY-MM-DD), version (incrementing integer), reviewer, scope description
4. **Version increments** each review cycle: 1, 2, 3...
5. **Findings are permanent within that version** ！ the document IS the current state

For detailed header and finding format, load `references/review-format.md`.

## Planning Document Rules

1. **Minimal first** ！ never write a full spec before user agrees on the overview
2. **Place correctly** ！ use the wiki directory structure: Architecture/Business/Modules/Guides
3. **Avoid duplication** ！ if a topic is covered in another doc, link to it instead of repeating

For document structure guidelines, load `references/planning-format.md`.
