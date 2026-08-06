# Patch format saja: hapus +/-, Neto pakai ▲/▼
# Jalankan: python patch_neto.py
from pathlib import Path

p = Path("bot.py")
s = p.read_text(encoding="utf-8")
n = 0

# 1) Neto di format_harga
old1 = 'f"Neto : {_pts(neto)}"'
new1 = 'f"Neto : {_neto(neto)}"'
if old1 in s:
    if "def _neto(" not in s:
        helper = '''
def _neto(v) -> str:
    """Neto: 588 ▲ atau 147 ▼."""
    if v is None:
        return "-"
    try:
        n = int(round(float(v)))
        if n > 0:
            return f"{n} ▲"
        if n < 0:
            return f"{abs(n)} ▼"
        return "0"
    except Exception:
        return str(v)

'''
        marker = "def _pts(v) -> str:"
        idx = s.find(marker)
        if idx >= 0:
            end = s.find("\n\n", idx)
            if end > 0:
                s = s[:end] + "\n" + helper + s[end:]
                n += 1
                print("+ helper _neto")
    s = s.replace(old1, new1)
    n += 1
    print("+ format_harga Neto → ▲/▼")
else:
    print("! format_harga Neto sudah diubah atau tidak ditemukan")

# 2) pts lokal di format_mt5_genesis: hapus +/-
old2 = 'return f"{n:+d}" if n != 0 else "0"'
new2 = 'return str(abs(n)) if n != 0 else "0"'
if old2 in s:
    s = s.replace(old2, new2, 1)
    n += 1
    print("+ Atas/Bawah tanpa +/-")
else:
    print("! pts +/- tidak ditemukan (mungkin sudah diubah)")

# 3) Neto row di tabel GT
old3 = 'rows.append(f"Neto    {col_pts(gt3.get(\'neto\'))} {col_pts(gt2.get(\'neto\'))} {col_pts(gt1.get(\'neto\'))} {col_pts(live_neto)}")'
new3 = '''def _nf(v):
        if v is None:
            return "-"
        try:
            x = int(round(float(v)))
            if x > 0:
                return f"{x} ▲"
            if x < 0:
                return f"{abs(x)} ▼"
            return "0"
        except Exception:
            return str(v)
    def col_neto(v, width=9):
        t = _nf(v)
        if len(t) > width:
            t = t[:width]
        return t.rjust(width)
    rows.append(f"Neto    {col_neto(gt3.get('neto'))} {col_neto(gt2.get('neto'))} {col_neto(gt1.get('neto'))} {col_neto(live_neto)}")'''
if old3 in s:
    s = s.replace(old3, new3)
    n += 1
    print("+ tabel GT Neto → ▲/▼")
else:
    print("! baris Neto tabel tidak ditemukan")

p.write_text(s, encoding="utf-8")
print(f"\nSelesai: {n} perubahan. Jalankan ulang bot.")
