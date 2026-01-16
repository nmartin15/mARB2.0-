#!/usr/bin/env python3
"""Script to verify and set Python interpreter."""
import json
import os
from pathlib import Path

workspace = Path(__file__).parent
venv_python = workspace / "venv" / "bin" / "python"
settings_file = workspace / ".vscode" / "settings.json"

print(f"Workspace: {workspace}")
print(f"Venv Python: {venv_python}")
print(f"Venv exists: {venv_python.exists()}")

if settings_file.exists():
    with open(settings_file) as f:
        settings = json.load(f)
    current = settings.get("python.defaultInterpreterPath", "NOT SET")
    print(f"Current setting: {current}")
    
    # Update if needed
    if current != str(venv_python.relative_to(workspace)) and current != "${workspaceFolder}/venv/bin/python":
        settings["python.defaultInterpreterPath"] = "${workspaceFolder}/venv/bin/python"
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=4)
        print("✓ Updated settings.json")
    else:
        print("✓ Settings already correct")
else:
    print("⚠ Settings file not found")
    
print(f"\nTo use this interpreter in Cursor:")
print(f"1. Press Cmd+Shift+P")
print(f"2. Type: Python: Select Interpreter")
print(f"3. Select: {venv_python}")
