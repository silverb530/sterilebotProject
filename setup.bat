@echo off
chcp 65001 >nul 2>&1
echo ===========================================
echo   SterileBot 환경 자동 셋업
echo ===========================================
echo.

REM 1. Python 설치 확인
echo [1/5] Python 설치 확인...
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python이 설치되어 있지 않거나 PATH에 없습니다.
    echo https://www.python.org/downloads/ 에서 Python 3.11 설치 후 다시 실행하세요.
    echo 설치할 때 "Add Python to PATH" 체크 필수!
    pause
    exit /b 1
)
python --version
echo.

REM Python 3.11 인지 단순 문자열 검색
python --version 2>&1 | findstr /C:"Python 3.11" >nul
if errorlevel 1 (
    echo [WARNING] Python 3.11 이 아닙니다.
    echo dlib whl 파일이 cp311 전용이라 호환 안 될 수 있습니다.
    echo 계속하려면 아무 키나 누르세요. 중단하려면 창 닫기.
    pause
)
echo.

REM 2. gesture_learning venv
echo [2/5] gesture_learning 가상환경 생성 + 라이브러리 설치...
cd /d "%~dp0gesture_learning"
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] gesture_learning 라이브러리 설치 실패.
    call deactivate
    pause
    exit /b 1
)
call deactivate
echo gesture_learning 완료.
echo.

REM 3. server venv 만들기
echo [3/5] server 가상환경 생성...
cd /d "%~dp0server"
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
echo.

REM 4. dlib 별도 설치
echo [4/5] dlib 설치 (wheels 폴더에서)...
set DLIB_WHL=
for %%f in ("%~dp0wheels\dlib-*.whl") do set DLIB_WHL=%%f
if "%DLIB_WHL%"=="" (
    echo [ERROR] wheels 폴더에 dlib whl 파일이 없습니다.
    call deactivate
    pause
    exit /b 1
)
echo dlib whl: %DLIB_WHL%
pip install "%DLIB_WHL%"
if errorlevel 1 (
    echo [ERROR] dlib 설치 실패. Python 3.11 인지 확인하세요.
    call deactivate
    pause
    exit /b 1
)
echo.

REM 5. server 나머지 라이브러리
echo [5/5] server 나머지 라이브러리 설치...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] server 라이브러리 설치 실패.
    call deactivate
    pause
    exit /b 1
)
call deactivate
echo server 완료.
echo.

echo ===========================================
echo   셋업 완료!
echo ===========================================
echo.
echo 다음 단계:
echo   1. camera_finder.py 실행 (gesture_learning 폴더에서)
echo   2. calib.py --name 영문이름 실행
echo   3. name_map.json 에 한글이름 → 영문이름 매핑 추가
echo   4. WPF 빌드 + 실행
echo.
pause
