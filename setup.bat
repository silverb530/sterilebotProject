@echo off
echo ===========================================
echo   SterileBot Environment Setup
echo ===========================================
echo.

REM 1. Find Python 3.11
echo [1/5] Looking for Python 3.11...
set PY311=

REM Try py launcher first
py -3.11 --version >nul 2>&1
if not errorlevel 1 (
    set PY311=py -3.11
    py -3.11 --version
    goto :py_found
)

REM Try common install paths
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PY311="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" --version
    goto :py_found
)
if exist "C:\Python311\python.exe" (
    set PY311=C:\Python311\python.exe
    C:\Python311\python.exe --version
    goto :py_found
)
if exist "C:\Program Files\Python311\python.exe" (
    set PY311="C:\Program Files\Python311\python.exe"
    "C:\Program Files\Python311\python.exe" --version
    goto :py_found
)

REM Fallback: check default python
python --version 2>&1 | findstr /C:"Python 3.11" >nul
if not errorlevel 1 (
    set PY311=python
    python --version
    goto :py_found
)

echo [ERROR] Python 3.11 not found.
echo.
echo This project requires Python 3.11 because dlib whl is cp311-specific.
echo Install Python 3.11 from:
echo   https://www.python.org/downloads/release/python-3119/
echo.
echo You can keep your existing Python ^(3.14 etc^) installed alongside.
echo Just make sure to check "Add Python to PATH" during installation.
pause
exit /b 1

:py_found
echo Found Python 3.11
echo.

REM 2. gesture_learning venv (using Python 3.11)
echo [2/5] Setting up gesture_learning venv with Python 3.11...
cd /d "%~dp0gesture_learning"
if not exist .venv (
    %PY311% -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] gesture_learning library install failed.
    call deactivate
    pause
    exit /b 1
)
call deactivate
echo gesture_learning done.
echo.

REM 3. server venv
echo [3/5] Setting up server venv with Python 3.11...
cd /d "%~dp0server"
if not exist .venv (
    %PY311% -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
echo.

REM 4. dlib install
echo [4/5] Installing dlib from wheels folder...
set DLIB_WHL=
for %%f in ("%~dp0wheels\dlib-*.whl") do set DLIB_WHL=%%f
if "%DLIB_WHL%"=="" (
    echo [ERROR] No dlib whl file in wheels folder.
    call deactivate
    pause
    exit /b 1
)
echo dlib whl: %DLIB_WHL%
pip install "%DLIB_WHL%"
if errorlevel 1 (
    echo [ERROR] dlib install failed.
    call deactivate
    pause
    exit /b 1
)
echo.

REM 5. server libraries
echo [5/5] Installing server libraries...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] server library install failed.
    call deactivate
    pause
    exit /b 1
)
call deactivate
echo server done.
echo.

echo ===========================================
echo   Setup Complete!
echo ===========================================
echo.
echo Next steps:
echo   1. Run face calibration ^(once per user^):
echo      cd gesture_learning
echo      .venv\Scripts\activate
echo      python calib.py --name your_english_name
echo.
echo   2. Edit name_map.json:
echo      Add: { "korean_name": "english_name" }
echo.
echo   3. Run WPF
echo.
pause
