# Patch format saja: tanpa $, Atas/Bawah polos, Neto ▲/▼
from pathlib import Path

p = Path("bot.py")
s = p.read_text(encoding="utf-8")

# 1. HTML escape
s = s.replace(
    'return s.replace("&", "&").replace("<", "<").replace(">", ">")',
    'return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")',
)

# 2. Module _pts + _neto
old = (
    'def _pts(v) -> str:\n'
    '    """Format poin (neto/julat/atas/bawah) tanpa koma."""\n'
    '    if v is None:\n'
    '        return "-"\n'
    '    try:\n'
    '        n = int(round(float(v)))\n'
    '        return str(n)\n'
    '    except Exception:\n'
    '        return str(v)\n'
)
new = (
    'def _pts(v) -> str:\n'
    '    """Atas/Bawah/Julat: angka positif polos tanpa +/-."""\n'
    '    if v is None:\n'
    '        return "-"\n'
    '    try:\n'
    '        return str(abs(int(round(float(v)))))\n'
    '    except Exception:\n'
    '        return str(v)\n'
    '\n'
    '\n'
    'def _neto(v) -> str:\n'
    '    """Neto: 588 ▲ atau 147 ▼."""\n'
    '    if v is None:\n'
    '        return "-"\n'
    '    try:\n'
    '        n = int(round(float(v)))\n'
    '        if n > 0:\n'
    '            return f"{n} ▲"\n'
    '        if n < 0:\n'
    '            return f"{abs(n)} ▼"\n'
    '        return "0"\n'
    '    except Exception:\n'
    '        return str(v)\n'
)
if old in s:
    s = s.replace(old, new)
    print("  + _neto helper")
else:
    print("  ! _pts block not found")

s = s.replace('f"Neto : {_pts(neto)}"', 'f"Neto : {_neto(neto)}"')

old2 = (
    '    def pts(v):\n'
    '        if v is None:\n'
    '            return "-"\n'
    '        try:\n'
    '            n = int(round(float(v)))\n'
    '            return f"{n:+d}" if n != 0 else "0"\n'
    '        except Exception:\n'
    '            return str(v)\n'
)
new2 = (
    '    def pts(v):\n'
    '        if v is None:\n'
    '            return "-"\n'
    '        try:\n'
    '            return str(abs(int(round(float(v)))))\n'
    '        except Exception:\n'
    '            return str(v)\n'
    '\n'
    '    def neto_fmt(v):\n'
    '        if v is None:\n'
    '            return "-"\n'
    '        try:\n'
    '            n = int(round(float(v)))\n'
    '            if n > 0:\n'
    '                return f"{n} ▲"\n'
    '            if n < 0:\n'
    '                return f"{abs(n)} ▼"\n'
    '            return "0"\n'
    '        except Exception:\n'
    '            return str(v)\n'
)
if old2 in s:
    s = s.replace(old2, new2)
    print("  + neto_fmt in GT table")
else:
    print("  ! local pts not found")

old_row = (
    'rows.append(f"Neto    {col_pts(gt3.get(\'neto\'))} '
    '{col_pts(gt2.get(\'neto\'))} {col_pts(gt1.get(\'neto\'))} '
    '{col_pts(live_neto)}")'
)
new_row = (
    'def col_neto(v, width=9):\n'
    '        t = neto_fmt(v)\n'
    '        if len(t) > width:\n'
    '            t = t[:width]\n'
    '        return t.rjust(width)\n'
    '    rows.append(f"Neto    {col_neto(gt3.get(\'neto\'))} '
    '{col_neto(gt2.get(\'neto\'))} {col_neto(gt1.get(\'neto\'))} '
    '{col_neto(live_neto)}")'
)
if old_row in s:
    s = s.replace(old_row, new_row)
    print("  + Neto row ▲/▼")
else:
    print("  ! Neto row not found")

p.write_text(s, encoding="utf-8")
print("  bot.py patched OK")
