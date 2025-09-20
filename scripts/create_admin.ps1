# PowerShell wrapper script for create_admin.py to fix module import issues

# Set PYTHONPATH to include the project root
$env:PYTHONPATH = "$(Get-Location);$env:PYTHONPATH"

# Set encoding to UTF-8 to avoid Unicode issues
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:LANG = "C.UTF-8"
$env:LC_ALL = "C.UTF-8"

# Run the script
python scripts/create_admin.py $args
