"""
Run this ONCE on Python 3.14 if you get:
  cannot import name 'find_loader' from 'pkgutil'
"""
import os, shutil
try:
    import pytesseract
    path = os.path.join(os.path.dirname(pytesseract.__file__), "pytesseract.py")
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    if "from pkgutil import find_loader" in src:
        src = src.replace(
            "from pkgutil import find_loader",
            "from importlib.util import find_spec as find_loader"
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)
        print("✅ Patched pytesseract for Python 3.14")
    else:
        print("✅ No patch needed")
    shutil.rmtree(os.path.join(os.path.dirname(pytesseract.__file__), "__pycache__"), ignore_errors=True)
    print("✅ Cleared pycache")
except Exception as e:
    print(f"❌ Error: {e}")
