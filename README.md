# lens_replace
I'm just tired of looking at logs and doing other simple things in the huge lens ide. Essentially, it's a small application with a UI for viewing logs under, with some additional functionality.

# Build for Windows
```
pyinstaller --onefile --windowed --icon=gui/assets/app_icon.ico --add-data "gui/assets;gui/assets" main.py
```