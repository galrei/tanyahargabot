@echo off
chcp 65001 >nul
title TanyaHargaBot
echo ========================================
echo        TANYAHARGABOT - Menjalankan
echo ========================================
echo.

:: Cek apakah file .env ada
if not exist ".env" (
    echo [ERROR] File .env tidak ditemukan!
    echo.
    echo Buat file .env terlebih dahulu dengan isi:
    echo TELEGRAM_BOT_TOKEN=token_bot_kamu
    echo.
    pause
    exit /b
)

echo Menginstall library yang dibutuhkan...
python -m pip install -r requirements.txt
echo.
echo Menjalankan bot...
echo Jangan tutup jendela ini supaya bot tetap hidup.
echo ========================================
echo.

python bot.py

echo.
echo Bot berhenti.
pause
