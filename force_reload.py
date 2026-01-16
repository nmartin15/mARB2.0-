#!/usr/bin/env python3
"""Force Cursor to recognize the virtual environment."""
import json
from pathlib import Path

# The settings are already correct, but let's make sure
workspace = Path(__file__).parent
settings_file = workspace / ".vscode" / "settings.json"

# Ensure settings exist and are correct
if not settings_file.parent.exists():
    settings_file.parent.mkdir(parents=True)

settings = {
    "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
    "python.terminal.activateEnvironment": True,
    "python.terminal.activateEnvInCurrentTerminal": True,
}

if settings_file.exists():
    with open(settings_file) as f:
        existing = json.load(f)
    settings.update(existing)

with open(settings_file, 'w') as f:
    json.dump(settings, f, indent=4)

print("✓ Settings file updated")
print("\n⚠️  IMPORTANT: You need to reload Cursor for changes to take effect:")
print("   1. Press Cmd+Shift+P")
print("   2. Type: 'Developer: Reload Window'")
print("   3. Press Enter")
print("\n   OR manually select the interpreter:")
print("   1. Press Cmd+Shift+P")
print("   2. Type: 'Python: Select Interpreter'")
print("   3. Select: ./venv/bin/python")
