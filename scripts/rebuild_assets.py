import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'scripts' / 'index_original.html'
CSS_TARGET = ROOT / 'python_backend' / 'static' / 'css' / 'dashboard.css'
JS_TARGET = ROOT / 'python_backend' / 'static' / 'js' / 'dashboard.js'

html = SNAPSHOT.read_text(encoding='utf-8', errors='ignore')

style_match = re.search(r'<style>([\s\S]*?)</style>', html)
script_matches = re.findall(r'<script(?![^>]*src)[^>]*>([\s\S]*?)</script>', html)

if not style_match or not script_matches:
    raise SystemExit('Could not locate inline style and script blocks in snapshot')

CSS_TARGET.parent.mkdir(parents=True, exist_ok=True)
JS_TARGET.parent.mkdir(parents=True, exist_ok=True)

CSS_TARGET.write_text(style_match.group(1).strip() + '\n', encoding='utf-8')
JS_TARGET.write_text(script_matches[-1].strip() + '\n', encoding='utf-8')

print('Assets restored from snapshot')
