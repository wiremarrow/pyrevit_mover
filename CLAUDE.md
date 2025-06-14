# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

This repository contains PyRevit Python scripts for fixing architectural placement issues in Revit files. The specific issue being addressed:

- A contracted architect delivered a field house .rvt file that was built in the wrong location (random corner of the site plan)
- The building needs to be moved to its correct position within a middle school construction project
- Shared Coordinates are being avoided for this specific building due to the contractor's communication issues
- PyRevit is already working with the open project file for rapid iteration

## Development Workflow

1. **Cross-Platform Development**:
   - Primary development on macOS using Claude Code
   - Scripts are executed on Windows machine with Revit/PyRevit installed
   - Git is used to sync code changes between machines
   - Execution results and errors are committed back for debugging on macOS

2. **PyRevit Extension Structure**:
   - Scripts should be compatible with PyRevit extension format
   - Use IronPython 2.7 syntax (PyRevit default)
   - Access Revit API through pyRevit module imports

## Common Commands

```bash
# Stage all changes and view status
git add . && git status

# Commit changes with descriptive message
git commit -m "Add/Update PyRevit script for [specific task]"

# Push to remote
git push origin main

# Pull latest changes (from Windows machine results)
git pull origin main
```

## PyRevit Script Template

```python
# -*- coding: utf-8 -*-
from pyrevit import revit, DB
from pyrevit import script

doc = revit.doc
uidoc = revit.uidoc

# Script logic here
```

## Key Considerations

- All scripts must handle transaction management for Revit document modifications
- Error handling should be verbose to aid remote debugging
- Include progress output for long-running operations
- Test element selection before applying transformations

## API Documentation Requirements

When implementing Revit API functionality:
- **ALWAYS** search for current Revit API documentation (latest version) before implementing
- Verify that methods and properties are not deprecated in Revit 2026+
- Check for API breaking changes between versions
- Look for official Autodesk documentation and Building Coder blog posts
- Avoid using deprecated properties like ElementId.IntegerValue (use .Value instead)