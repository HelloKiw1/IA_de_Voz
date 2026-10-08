"""Import audited treated WAVs; preserve complete copies and trim only edge silence."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tts.reference_audio import VOICE_PROFILES, validate_reference_audio


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    audit_path = ROOT/'docs/voices/eduardo/source_analysis.json'
    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    manifest = []
    for profile, relative in VOICE_PROFILES.items():
        item = next(r for r in audit['files'] if f'({profile})' in r['name'] and r.get('format') == 'wav')
        source = args.source/item['name']
        if hashlib.sha256(source.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Fonte mudou desde a análise: '+source.name)
        target = ROOT/relative
        archive = target.parent/'originais'/f'{profile}.wav'
        archive.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or archive.exists():
            raise FileExistsError(f'Importação já existe: {target}')
        shutil.copy2(source, archive)
        samples, rate = sf.read(source, always_2d=True)
        lead = max(0, int((item['initial_silence_seconds']-.2)*rate))
        tail = max(0, int((item['final_silence_seconds']-.2)*rate))
        sf.write(target, samples[lead:len(samples)-tail if tail else None], rate, subtype=sf.info(source).subtype)
        report = validate_reference_audio(relative, profile)
        manifest.append(dict(profile=profile, source_name=source.name, source_sha256=item['sha256'],
                             full_copy=archive.relative_to(ROOT).as_posix(), reference=relative,
                             removed_start_seconds=lead/rate, removed_end_seconds=tail/rate, validation=report))
    script = next(r for r in audit['files'] if r['name'].endswith('.txt'))
    shutil.copy2(args.source/script['name'], ROOT/'docs/voices/eduardo/roteiro_referencia.txt')
    (ROOT/'docs/voices/eduardo/import_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
