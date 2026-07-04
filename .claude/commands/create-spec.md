---
description: Create a spec file for the next Spendly feature
argument-hint: "Step number and feature name e.g. 2 registration"
allowed-tools: Read, Write, Glob
----

Read database/db.py to understand the expeses table schema, the db connection pattern, and the database file name.

You are a senior developer planning a new feature for the Spendly expense tracker.  Always follow the rules in CLAUDE.md.

User input: $ARGUMENTS

## Step 1 - Parse arguments

From $ARGUMENTS extract:

1. 'step_number' - zero-padded to 2 digits: 2 > 02, 11 > 11

2. 'feature_title' - human readable title in Title Case
    - Example: "Registration" or "Login and Logout"

3. 'feature_slug' - file safe slug 
    - Lowercase, kebab-case
    - Only a-z, 0-9 and -
    - Maximum 40 characters
    - Example: registration, login-logout

If you cannot infer these from $ARGUMENTS, ask the user to clarify before proceding.

## Step 2 - Research the codebase
Read these files before writing the spec:
- CLAUDE.md - roadmap, conventions, schema
- app.py - existing routes and structure
- database/db.py - existing schema and functions
- All files in .claude/specs/ - avoid duplicating existing specs

Check CLAUDE.md to confirm the requested step is not already marked completed.  If it is, warn the user and stop.

## Step 3 - Write the spec
Generate a spec doc document with this exact structure:

# Spec: <feature_title>

## Overview
One paragraph describing what this feature and why it exists at this stage of the Spendly readmap.

## Depends on
Which previous steps this feature requires to be complete.

## Routes
Every new route needed:
- METHOD /path - description - access level (public/logged-in)

if no new routes: state "No new routes".

## Database changes
Any new tables, columns, or constraints needed.
Always verify against database/db.py before writing this.
If none: state "No database changes".

## Templates
- Create: list new templates with their path
- Modify: list existing templates and what changes

## Files to change
Every file that will be modified.

## File to create
Every new file that will be created.

## New dependencies
Any new pip packages.  If none: state "No new dependencies".

## Rules for implementation
Specific constraints Claude must follow.
Always include:
- No SQLAlchemy or ORMS
- Parameterised queries only
- Password hashed with werkzeug
- Use CSS variables - never hardcode hex values
- All templates extend base.html

## Definition of done
A specific testable checklist.  Each item must be something that can be verified by running the app.

## Step 4 - Save the spec
Save to: .claude/specs/
<step_number>-<feature_slug>.md

## Step 5 - Report to the user
Print a short summary in this exact format:

Spec file: .claude/specs/
<step_number>-<feature_slug>.md
Title: <feature_title>

The tell the user:
"Review the spec at .claude/specs/<step_number>-<feature_slug>.md then enter Plan Mode with Shift-Tab twice to begin implemtation."


