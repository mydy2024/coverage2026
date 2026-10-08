"""Extract local planning inputs; preserve one-based physical PDF pages."""
from pathlib import Path
import hashlib
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.tools' / 'python'))
import pymupdf

def main():
    out = ROOT / 'reference_notes' / 'extracted'
    out.mkdir(parents=True, exist_ok=True)
    sources = []
    for relative in ['JESD79-5D.PDF', 'papers/ICCAD26_ChatFCM.pdf', 'FCM_CoverageClosure_v2.pptx']:
        path = ROOT.parent / relative
        entry = {'path': '../' + relative, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        if path.suffix.lower() == '.pdf':
            with pymupdf.open(path) as doc:
                entry['physical_pages'] = len(doc)
                chunks = [f'\n\n=== PDF PAGE {i+1} ===\n' + page.get_text(sort=True) for i, page in enumerate(doc)]
        else:
            with zipfile.ZipFile(path) as archive:
                names = sorted([n for n in archive.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)], key=lambda n: int(re.search(r'(\d+)\.xml', n).group(1)))
                entry['slides'] = len(names)
                chunks = []
                for i, name in enumerate(names):
                    xml = ET.fromstring(archive.read(name))
                    chunks.append(f'\n\n=== SLIDE {i+1} ===\n' + '\n'.join(t.text or '' for t in xml.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t')))
        target = out / (path.stem + '.txt')
        target.write_text(''.join(chunks), encoding='utf-8')
        entry['extracted_text'] = str(target.relative_to(ROOT)).replace('\\', '/')
        sources.append(entry)
    (ROOT / 'reference_notes' / 'source_manifest.json').write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(sources, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
