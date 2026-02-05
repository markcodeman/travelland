#!/usr/bin/env python3
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from city_guides.src.persistence import get_synthesis_enhancer

SE = get_synthesis_enhancer()

def neutralize_in_obj(obj, city=None, neighborhood=None):
    changed = 0
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == 'quick_guide' and isinstance(v, str):
                try:
                    # call sync neutralize (engine is sync)
                    cleaned = SE.neutralize_tone(v, neighborhood=neighborhood or obj.get('neighborhood') or '', city=city or obj.get('city') or '')
                    if cleaned and cleaned != v:
                        obj[k] = cleaned
                        changed += 1
                except Exception:
                    pass
            else:
                # Propagate potential city/neighborhood context
                sub_city = city
                sub_nh = neighborhood
                if k.lower() in ('city', 'town', 'name') and isinstance(v, str) and not sub_city:
                    sub_city = v
                if k.lower() in ('neighborhood', 'nb') and isinstance(v, str) and not sub_nh:
                    sub_nh = v
                c = neutralize_in_obj(v, city=sub_city, neighborhood=sub_nh)
                changed += c
    elif isinstance(obj, list):
        for item in obj:
            changed += neutralize_in_obj(item, city=city, neighborhood=neighborhood)
    return changed


def main():
    base = Path('results')
    if not base.exists():
        print('No results/ directory found')
        return

    files = list(base.glob('**/*.json'))
    total_files = 0
    total_changed = 0
    modified_files = []

    for f in files:
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        changed = neutralize_in_obj(data)
        if changed > 0:
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            modified_files.append((str(f), changed))
            total_changed += changed
        total_files += 1

    print(f'Processed {total_files} JSON files under results/; modified {len(modified_files)} files; total quick_guides updated: {total_changed}')
    for p, c in modified_files:
        print(f'- {p}: {c} updates')

if __name__ == '__main__':
    main()
