# Build and distribute one ActualTextPDF.exe

## Why the previous EXE did not open on the other computer

The previous `build_exe.bat` used PyInstaller `--onedir`. That mode creates an executable plus a companion `_internal` directory. Copying only `ActualTextPDF.exe` leaves out the bundled Python runtime and libraries, so the program cannot start.

## New build: one-file EXE

The updated `build_exe.bat` uses PyInstaller `--onefile --console`. It packages the Python runtime, FastAPI/Uvicorn backend, PyMuPDF dependencies, and built React frontend into one executable.

### Build on Windows

On the developer/build computer:
1. Install Python 3.11+ and Node.js LTS.
2. Extract the project ZIP completely.
3. Open the project folder.
4. Double-click `build_exe.bat`.
5. Wait for `BUILD COMPLETED SUCCESSFULLY!`.
6. Find the single executable at `dist\ActualTextPDF.exe`.

Build the Windows EXE on Windows. PyInstaller is not a cross-compiler. The build computer needs internet access for the first dependency installation.

### Copy to the other Windows PC

Copy only `dist\ActualTextPDF.exe`. The target PC does not need Python or Node.js installed.

The target needs a compatible Windows version and CPU architecture. Use the same architecture (normally x64) used to build the EXE. The app binds only to `127.0.0.1` and opens `http://127.0.0.1:8000`.

The first launch can take longer because PyInstaller extracts the embedded files to a temporary directory. Do not delete or move the EXE while it is running. Keep the console window open while using the application.

### Troubleshooting on target PC

If it still does not open:
- Right-click the EXE > Properties. If Windows shows an **Unblock** checkbox/button, use it only if you trust the file and its source.
- Try launching it from Command Prompt so any error remains visible:
  `ActualTextPDF.exe`
- Check the launcher log at `%LOCALAPPDATA%\ActualTextPDF\launcher.log`.
- If Windows Security quarantines the file, confirm the build provenance and scan it before allowing it. Do not disable antivirus globally.
- If it reports port 8000 is occupied, close the application currently using that port.

## Existing one-folder build

If you prefer the old `--onedir` mode, distribute the entire `dist\ActualTextPDF` folder as a ZIP. Never send only the EXE from that folder.

## Important

This build script is configured for a single-file EXE, but it must be run on a Windows build machine to produce and test the actual Windows binary. A source ZIP is not itself a compiled EXE.
