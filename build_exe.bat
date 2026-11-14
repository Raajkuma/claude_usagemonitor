@echo off
python -m pip install -r requirements.txt
python -m pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name ClaudeUsageFloat app.py
echo Build complete: dist\ClaudeUsageFloat.exe
pause
