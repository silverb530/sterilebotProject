@echo off
  echo ===========================================
  echo   SterileBot Environment Setup
  echo ===========================================
  echo.

  REM 1. Find Python 3.11
  echo [1/6] Looking for Python 3.11...
  set PY311=

  py -3.11 --version >nul 2>&1
  if not errorlevel 1 (
      set PY311=py -3.11
      py -3.11 --version
      goto :py_found
  )

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
  pause
  exit /b 1

  :py_found
  echo Found Python 3.11
  echo.

  REM 2. gesture_learning venv
  echo [2/6] Setting up gesture_learning venv...
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
  echo [3/6] Setting up server venv...
  cd /d "%~dp0server"
  if not exist .venv (
      %PY311% -m venv .venv
  )
  call .venv\Scripts\activate.bat
  python -m pip install --upgrade pip
  echo.

  REM 4. server libraries
  echo [4/6] Installing server libraries...
  pip install -r requirements.txt
  if errorlevel 1 (
      echo [ERROR] server library install failed.
      call deactivate
      pause
      exit /b 1
  )
  echo.

  REM 5. dlib and face-recognition
  echo [5/6] Installing dlib from local wheel...
  echo Script dir: %~dp0
  echo Looking in: %~dp0wheels
  dir "%~dp0wheels"

  set "DLIB_WHL="
  for %%f in ("%~dp0wheels\dlib-*.whl") do set "DLIB_WHL=%%f"

  echo DLIB_WHL=%DLIB_WHL%

  if "%DLIB_WHL%"=="" (
      echo [ERROR] No dlib whl file in wheels folder.
      echo [HINT] Expected something like: %~dp0wheels\dlib-19.24.6-cp311-cp311-win_amd64.whl
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

  echo Installing face-recognition without dependencies...
  pip install face-recognition==1.3.0 --no-deps
  if errorlevel 1 (
      echo [ERROR] face-recognition install failed.
      call deactivate
      pause
      exit /b 1
  )
  echo.

  REM 6. verify server dependencies
  echo [6/6] Verifying server dependencies...
  python -c "import dlib; print('dlib:', dlib.__version__)"
  if errorlevel 1 (
      echo [ERROR] dlib verification failed.
      call deactivate
      pause
      exit /b 1
  )

  python -c "import face_recognition; print('face_recognition: ok')"
  if errorlevel 1 (
      echo [ERROR] face_recognition verification failed.
      call deactivate
      pause
      exit /b 1
  )

  python -c "import cv2; print('opencv:', cv2.__version__)"
  if errorlevel 1 (
      echo [ERROR] opencv verification failed.
      call deactivate
      pause
      exit /b 1
  )

  python -c "import numpy; print('numpy:', numpy.__version__)"
  if errorlevel 1 (
      echo [ERROR] numpy verification failed.
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
  pause
