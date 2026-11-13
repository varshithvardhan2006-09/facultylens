@echo off
rem Starts FacultyLens. Works even when PowerShell scripts are blocked by the execution policy.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
