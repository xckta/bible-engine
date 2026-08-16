@echo off
cd /d "%~dp0"
title Bible Engine // Oracle
powershell.exe -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0scripts\start_windows.ps1"
