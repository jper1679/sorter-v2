@echo off
title RP2040 Distribution Board - Flet Test GUI
cd /d "%~dp0"
python software/scripts/pico_tester_gui.py
pause
