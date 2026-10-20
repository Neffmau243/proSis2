"""Read only the served SPA shell and public static assets."""
import json
from pathlib import Path
import re
from urllib.request import urlopen

page = urlopen('http://127.0.0.1:8000/admision?patientId=14', timeout=10).read()
local = Path('frontend/dist/index.html').read_bytes()
assets = re.findall(rb'(?:src|href)="(/assets/[^"]+)"', page)
result = {
    'admission_status': 200,
    'matches_current_build': page.strip() == local.strip(),
    'assets_checked': len(assets),
    'assets_ok': all(urlopen('http://127.0.0.1:8000'+asset.decode(), timeout=10).status == 200 for asset in assets),
}
assert result['matches_current_build'] and assets and result['assets_ok']
Path(__file__).with_name('live-assets.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result))
