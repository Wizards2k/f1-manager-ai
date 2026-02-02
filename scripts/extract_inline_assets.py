import re
from pathlib import Path

root = Path(r"c:/Sviluppo/f1-manager-ai")
index_path = root / "python_backend" / "templates" / "index.html"
css_path = root / "python_backend" / "static" / "css" / "dashboard.css"
js_path = root / "python_backend" / "static" / "js" / "dashboard.js"

content = index_path.read_text(encoding="utf-8")

style_match = re.search(r"<style>([\s\S]*?)</style>", content)
if not style_match:
    raise RuntimeError("Inline <style> block not found")

script_matches = list(re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)</script>", content))
if not script_matches:
    raise RuntimeError("Inline <script> block not found")
script_match = script_matches[-1]

css_path.parent.mkdir(parents=True, exist_ok=True)
js_path.parent.mkdir(parents=True, exist_ok=True)

css_content = style_match.group(1).strip() + "\n"
js_content = script_match.group(1).strip() + "\n"

css_path.write_text(css_content, encoding="utf-8")
js_path.write_text(js_content, encoding="utf-8")

link_tag = "    <link rel=\"stylesheet\" href=\"{{ url_for('static', filename='css/dashboard.css') }}\">\n"
script_tag = "    <script src=\"{{ url_for('static', filename='js/dashboard.js') }}\"></script>\n"

new_content = content[:style_match.start()] + link_tag + content[style_match.end():]
new_content = new_content[:script_match.start()] + script_tag + new_content[script_match.end():]

index_path.write_text(new_content, encoding="utf-8")
print("Assets extracted and index.html updated")
