@echo off
chcp 65001 >nul
title Restore TanyaHargaBot
echo ========================================
echo  RESTORE kode lengkap + format dashboard
echo ========================================
echo.

echo [1/3] Download bot.py (versi lengkap)...
curl -fsSL -o bot.py "https://raw.githubusercontent.com/kebunsaldo/tanyahargabot/d0d65960990b06e474f6840970227b2a4ae14c3a/bot.py"
if errorlevel 1 (
  echo GAGAL download bot.py - cek koneksi internet
  pause
  exit /b 1
)

echo [2/3] Download mt5_helper.py ...
curl -fsSL -o mt5_helper.py "https://raw.githubusercontent.com/kebunsaldo/tanyahargabot/d0d65960990b06e474f6840970227b2a4ae14c3a/mt5_helper.py"

echo [3/3] Download signal_engine.py ...
if not exist services mkdir services
curl -fsSL -o services\signal_engine.py "https://raw.githubusercontent.com/kebunsaldo/tanyahargabot/d0d65960990b06e474f6840970227b2a4ae14c3a/services/signal_engine.py"

echo.
echo Menerapkan format: tanpa $ / +/- , Neto pakai simbol ▲ ▼ ...
python _patch_format.py
if errorlevel 1 (
  echo Patch gagal - tapi file utama sudah terunduh.
)

echo.
echo ========================================
echo  SELESAI.
echo  Jalankan: jalankan-bot.bat
echo ========================================
pause
