# TanyaHargaBot 🥇

Bot Telegram teman untuk menanyakan **harga Gold (XAUUSD)** seputar MT5:  
**aktual • faktual • tren • sinyal • isu/rumor**

## Fitur

| Perintah | Fungsi |
|----------|--------|
| `/start` | Mulai & menu interaktif |
| `/menu`  | Tampilkan tombol menu |
| `/harga` | Harga aktual + OHLC |
| `/tren`  | Tren singkat (MA-based) |
| `/sinyal`| Sinyal sederhana BUY/SELL/WAIT |
| `/isu`   | Isu & rumor yang perlu diperhatikan |
| `/full`  | Ringkasan lengkap sekaligus |
| `/help`  | Bantuan |

Juga mendukung kata kunci bebas (contoh: "berapa harga", "tren dong", "sinyal").

## Persyaratan

- Python 3.10+
- Koneksi internet (untuk data harga & Telegram)

## Instalasi (di komputer sendiri)

```bash
# 1. Clone / masuk ke folder
cd tanyahargabot

# 2. Buat virtual environment (disarankan)
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

# 3. Install dependency
pip install -r requirements.txt

# 4. Token sudah ada di file .env
#    (atau edit .env jika ingin ganti token)
```

## Menjalankan Bot

```bash
python bot.py
```

Bot akan berjalan di komputermu (polling).  
Biarkan terminal terbuka. Untuk menjalankan di background:

```bash
# Linux/macOS
nohup python bot.py > bot.log 2>&1 &

# atau pakai screen / tmux
```

## Token

Token Telegram sudah dimasukkan di file `.env`:

```
TELEGRAM_BOT_TOKEN=6621853308:AAFCzPD_-tVj3ZtqnS5zlT61hLpDMO1S-Ek
```

**Penting:** Jangan share file `.env` ke publik. Jika token bocor, revoke di @BotFather lalu buat yang baru.

## Sumber Data

- Utama: Yahoo Finance (`GC=F` / `XAUUSD=X`) — mendekati harga yang terlihat di MT5
- Fallback: metals.live

Sinyal bersifat **edukatif** dan sederhana (bukan financial advice).

## Integrasi MT5 Langsung (Opsional)

Jika kamu punya MetaTrader 5 terpasang di komputer yang sama, bisa upgrade bot dengan package resmi:

```bash
pip install MetaTrader5
```

Lalu ganti fungsi `get_gold_data()` dengan koneksi ke terminal MT5 untuk harga bid/ask real dari broker.

## Struktur Folder

```
tanyahargabot/
├── bot.py              # Kode utama bot
├── requirements.txt
├── .env                # Token (jangan di-commit)
├── .env.example
└── README.md
```

## Catatan

- Bot ini dirancang untuk dijalankan di **komputer sendiri** (local).
- Untuk VPS / server 24 jam, cukup jalankan `python bot.py` dengan process manager (systemd, pm2, dll).
- Selalu gunakan risk management saat trading.

---
Dibuat berdasarkan permintaan untuk repo kebunsaldo/tanyahargabot.
