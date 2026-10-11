@echo off
chcp 65001 >nul
title Call2Code - Voice Agent (Bluetooth Headset + Computer Audio)
color 0A
echo ================================================================
echo   CALL2CODE - VOICE AGENT (BLUETOOTH HEADSET + COMPUTER AUDIO)
echo   - Mic: Headset Mic (Airdopes 280 ANC)
echo   - Sound: PC Speakers (Realtek Audio)
echo   - Language: English
echo   - AI Engine: Moonshot Kimi K3 (via NVIDIA API)
echo   - Auto-Deploy: PC Vercel Account
echo ================================================================
echo.

py voice_bridge.py

pause
