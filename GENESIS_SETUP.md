# Cara Hubungkan EA Genesis ke TanyaHargaBot

Bot bisa menampilkan data faktual dari **MT5 broker** dan **EA Genesis** kamu.

## Prioritas data
1. File `genesis_data.json` yang ditulis EA Genesis
2. Harga live dari terminal MT5 (yang sedang login)
3. Yahoo Finance (fallback)

---

## Opsi A — MT5 langsung (tanpa ubah EA)

1. Install library:
```bash
pip install MetaTrader5
```

2. Pastikan **MetaTrader 5 terbuka** dan sudah **login** ke akun broker.

3. Jalankan bot di komputer yang sama.

4. Tekan tombol **🏦 MT5 / Genesis** di bot.

---

## Opsi B — EA Genesis menulis file (paling lengkap)

Agar semua angka Genesis (tinggi, bawah, awal, neto, inti, jangkauan, dll) muncul, EA perlu menulis file.

### 1. Di EA Genesis, tambahkan kode sederhana (contoh):

```mql5
// Di OnTick() atau timer
string path = "genesis_data.json";
int h = FileOpen(path, FILE_WRITE|FILE_TXT|FILE_COMMON);
if(h != INVALID_HANDLE)
{
   string json = StringFormat(
      "{\"symbol\":\"%s\",\"time\":\"%s\",\"bid\":%.2f,\"ask\":%.2f,\"price\":%.2f,"
      "\"open\":%.2f,\"high\":%.2f,\"low\":%.2f,\"close\":%.2f,"
      "\"awal\":%.2f,\"tinggi\":%.2f,\"bawah\":%.2f,\"neto\":%.2f,"
      "\"inti\":%.2f,\"jangkauan\":%.2f}",
      _Symbol,
      TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS),
      SymbolInfoDouble(_Symbol, SYMBOL_BID),
      SymbolInfoDouble(_Symbol, SYMBOL_ASK),
      (SymbolInfoDouble(_Symbol, SYMBOL_BID)+SymbolInfoDouble(_Symbol, SYMBOL_ASK))/2.0,
      iOpen(_Symbol, PERIOD_H1, 0),
      iHigh(_Symbol, PERIOD_H1, 0),
      iLow(_Symbol, PERIOD_H1, 0),
      iClose(_Symbol, PERIOD_H1, 0),
      // sesuaikan dengan variabel Genesis kamu:
      awal, tinggi, bawah, neto, inti, jangkauan
   );
   FileWriteString(h, json);
   FileClose(h);
}
```

Sesuaikan nama variabel (`awal`, `tinggi`, `bawah`, `neto`, `inti`, `jangkauan`) dengan yang ada di EA Genesis.

### 2. Lokasi file

Bot mencari file di:
- Folder bot: `genesis_data.json`
- Atau: `MQL5/Files/genesis_data.json` (pakai `FILE_COMMON` atau path terminal)

Bisa juga set di `.env`:
```
GENESIS_DATA_PATH=C:\path\ke\genesis_data.json
```

### 3. Contoh file

Lihat `genesis_data.example.json` di repo.

---

## Setelah setup

1. Restart bot (`jalankan-bot.bat`)
2. Di Telegram tekan **🏦 MT5 / Genesis**
3. Semua angka faktual akan tampil

Kalau kamu kirim file EA Genesis (`.mq5` / `.ex5`), saya bisa bantu sesuaikan kode penulis file-nya.
