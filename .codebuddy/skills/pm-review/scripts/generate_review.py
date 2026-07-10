# PM Review Document Generator

import argparse
import os
import sys
from datetime import date

REVIEW_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'Assets', 'Documents', 'Plan', 'Reviews'
)

def slugify(name):
    return name.lower().replace(' ', '-').replace('_', '-')

def generate_header(module_name, scope):
    today = date.today().isoformat()

    return f"""# {module_name} - Code Review

| Field | Value |
|:--|:--|
| Date | {today} |
| Version | 1 |
| Reviewer | PM Review |
| Scope | {scope} |

## Critical



## Major



## Minor



## Suggestions



## Summary

- **Critical**: 0
- **Major**: 0
- **Minor**: 0
- **Suggestions**: 0

### Top Priority

(No findings yet)
"""

def main():
    parser = argparse.ArgumentParser(description='Generate a code review document.')
    parser.add_argument('module', help='Module name (e.g. "GlobalDataMgr")')
    parser.add_argument('--scope', '-s', default='Full module', help='Review scope description')
    args = parser.parse_args()

    module_name = args.module
    slug = slugify(module_name)
    filename = f"{slug}.md"
    filepath = os.path.join(REVIEW_DIR, filename)

    # Check if file exists
    if os.path.exists(filepath):
        old_content = open(filepath, 'r', encoding='utf-8').read()
        # Extract old version number
        old_version = 0
        for line in old_content.split('\n'):
            if 'Version' in line and '|' in line:
                try:
                    old_version = int(line.split('|')[1].strip())
                except ValueError:
                    pass
                break

        # Re-read with proper version increment
        header = generate_header(module_name, args.scope)
        # Replace version with incremented version
        new_version = old_version + 1
        header = header.replace('| Version | 1 |', f'| Version | {new_version} |')

        print(f"Version: {old_version} -> {new_version}")
        print(f"Overwriting: {filepath}")
    else:
        new_version = 1
        header = generate_header(module_name, args.scope)
        print(f"Creating: {filepath}")

    # Create directory if needed
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(header)

    print(f"Review document generated: {filepath}")
    print(f"Date: {date.today().isoformat()}")
    print(f"Version: {new_version}")

if __name__ == '__main__':
    main()
