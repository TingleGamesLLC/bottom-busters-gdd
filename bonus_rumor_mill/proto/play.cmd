@echo off
rem Opens Rumor Mill in a maximized Windows Terminal window.
rem   play       play the game
rem   play dm    instructor mode: F2 opens the DM view
set ARGS=
if /I "%1"=="dm" set ARGS=--dm
wt -w new --maximized new-tab -d "%~dp0." --title "Rumor Mill" cmd /c "python rumormill.py %ARGS% || pause"
