@echo off
cd C:\tracking_without_mouse\Zone_calibration
call .venv\Scripts\activate.bat

start "Zone Tracker" python zone_tracker.py
timeout /t 2
start "Face Tracking" python Learning_TWM.py --name minjun