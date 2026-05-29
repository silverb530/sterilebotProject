@echo off
cd C:\tracking_without_mouse\Zone_calibration
call .venv\Scripts\activate.bat

start "Gesture" python gesture_control_v6.py
timeout /t 2
start "Zone Tracker" python Zone_tracker.py
timeout /t 2
start "Face Tracking" python Learning_TWM.py --name minjun