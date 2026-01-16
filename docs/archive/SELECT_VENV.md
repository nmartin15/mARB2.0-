# Select Virtual Environment in Cursor

## Quick Steps

1. **Open Command Palette:**
   - Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)

2. **Select Python Interpreter:**
   - Type: `Python: Select Interpreter`
   - Press Enter

3. **Choose the Virtual Environment:**
   - Look for: `./venv/bin/python` or
   - Look for: `Python 3.9.6 ('venv': venv)`
   - Select it

## Alternative Method

1. **Click the Python version** in the bottom-right status bar
2. Select the interpreter from the list
3. Choose `./venv/bin/python`

## Verify It's Working

After selecting the interpreter:
- The bottom-right should show: `Python 3.9.6 ('venv': venv)`
- Import errors should disappear
- IntelliSense should work for FastAPI, SQLAlchemy, etc.

## If It Still Doesn't Work

1. **Reload the window:**
   - `Cmd+Shift+P` → `Developer: Reload Window`

2. **Check the path:**
   - The interpreter should be: `/Users/nathanmartinez/CursorProjects/mARB 2.0/venv/bin/python`

3. **Manual selection:**
   - `Cmd+Shift+P` → `Python: Select Interpreter`
   - Click "Enter interpreter path..."
   - Paste: `${workspaceFolder}/venv/bin/python`

## Configuration Files Created

- `.vscode/settings.json` - Auto-configures the venv
- `.python-version` - Specifies Python version
- `.cursorrules` - Project rules for Cursor

The workspace is now configured to automatically use the virtual environment!

