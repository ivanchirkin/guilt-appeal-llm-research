"""Validate the current multi-level schema, literal quotes and study membership."""
import sys
from collections import Counter
from functools import lru_cache

from jsonschema import Draft202012Validator

from common import read_turns, extract, render, corrected_turns
from study import ROOT, LEVELS, read_csv, read_json, selected_ids


def occurrence_key(occ, turns):
    first = occ['turns'][0]
    positions = [turns[first].find(q) for q in occ['quotes'] if q in turns[first]]
    return (int(occ['code'][1:]), int(first[1:]), min(positions, default=0))


def validate_annotation(data, did, turns, validator):
    errors = [f'{did}: {"/".join(map(str, e.absolute_path))}: {e.message}'
              for e in validator.iter_errors(data)]
    if errors:
        return errors
    if data['dialogue_id'] != did:
        errors.append(f'{did}: dialogue_id does not match file name')
    for obj in data['guilt']['evidence'] + data['nat']['issues']:
        if obj['turn'] not in turns or obj['quote'] not in turns[obj['turn']]:
            errors.append(f'{did}: non-literal quote in {obj["turn"]}')
    seen = set()
    for index, occ in enumerate(data['occurrences'], 1):
        prefix = f'{did}/{occ["occurrence_id"]}'
        if occ['occurrence_id'] != f'E{index:03}':
            errors.append(f'{prefix}: non-sequential occurrence_id')
        if occ['level'] != LEVELS[occ['code']]:
            errors.append(f'{prefix}: code/level mismatch')
        if occ['turns'] != sorted(set(occ['turns']), key=lambda t: int(t[1:])):
            errors.append(f'{prefix}: turns must be unique and chronological')
        if occ['code'] == 'G15':
            if len(occ['turns']) != len(occ['quotes']):
                errors.append(f'{prefix}: G15 requires one quote per turn')
            else:
                for turn, quote in zip(occ['turns'], occ['quotes']):
                    if quote not in turns.get(turn, ''):
                        errors.append(f'{prefix}: quote not found in {turn}')
        else:
            for quote in occ['quotes']:
                if quote not in turns.get(occ['turns'][0], ''):
                    errors.append(f'{prefix}: quote not found in {occ["turns"][0]}')
        key = (occ['code'], tuple(occ['turns']), frozenset(occ['quotes']))
        if key in seen:
            errors.append(f'{prefix}: exact duplicate within the same code')
        seen.add(key)
        if not occ['function'].strip():
            errors.append(f'{prefix}: empty functional explanation')
    if data['occurrences'] != sorted(data['occurrences'], key=lambda o: occurrence_key(o, turns)):
        errors.append(f'{did}: occurrences are not sorted by code, turn and position')
    human = data.get('human_assessment')
    expected = (human == data['guilt']['value']) if human is not None and data['guilt']['value'] is not None else None
    if data['guilt'].get('model_correct') is not expected:
        errors.append(f'{did}: model_correct does not match the two GUILT assessments')
    if data['review_status'] == 'verified':
        if human not in (0, 1) or type(human) is not int:
            errors.append(f'{did}: verified requires a human reference label')
        if not data['nat']['reason'].strip():
            errors.append(f'{did}: verified requires a NAT explanation')
    return errors


@lru_cache(maxsize=None)
def source_dialogues(source_file):
    return dict(extract(ROOT / '01_original' / source_file))


def validate_all():
    registry = {r['dialogue_id']: r for r in read_csv(ROOT / 'dialogue_registry.csv')}
    validator = Draft202012Validator(read_json(ROOT / '04_protocol/annotation.levels.schema.json'))
    errors, verified, pending = [], [], 0
    selected = set(selected_ids())
    paths = sorted((ROOT / '05_annotations').glob('D*.json'))
    for did in selected - {p.stem for p in paths}:
        errors.append(f'{did}: selected dialogue has no annotation')
    for path in paths:
        try:
            data, did = read_json(path), path.stem
            if did not in registry:
                errors.append(f'{did}: unknown ID'); continue
            row = registry[did]
            markdown, turns = read_turns(ROOT / row['corpus_file'])
            errors.extend(validate_annotation(data, did, turns, validator))
            if data.get('review_status') == 'verified':
                expected = (['A0'] if 'A0' in turns else []) + [p + str(i) for i in range(1, 7) for p in ('B', 'A')]
                if list(turns) != expected or any(not value.strip() for value in turns.values()):
                    errors.append(f'{did}: incomplete dialogue')
                replacement = corrected_turns(did, row['group'], row['source_file'], row['original_dialogue_number'])
                if (replacement is not None) != (row['extraction_status'] == 'corrected_author'):
                    errors.append(f'{did}: correction metadata mismatch')
                source = replacement if replacement is not None else source_dialogues(row['source_file'])[int(row['original_dialogue_number'])]
                if markdown != render(did, source):
                    errors.append(f'{did}: corpus differs from source')
                if did in selected:
                    verified.append((row, data, turns))
            else:
                pending += 1
        except Exception as exc:
            errors.append(f'{path.name}: {exc}')
    human_rows = read_csv(ROOT / '05_annotations/human_nat.csv')
    human_ids = [r['dialogue_id'] for r in human_rows]
    if len(set(human_ids)) != len(human_ids) or set(human_ids) != selected:
        errors.append('human_nat.csv: IDs must match the analysis sample, without duplicates')
    for row in human_rows:
        if row['score'] not in ('1', '2', '3', '4', '5') or row['review_status'] != 'verified':
            errors.append(f'human_nat.csv/{row["dialogue_id"]}: invalid score or review_status')
    expected_groups = Counter({g: 6 for g in ('К', 'А', 'Б', 'В')})
    actual_groups = Counter(registry[did]['group'] for did in selected if did in registry)
    if actual_groups != expected_groups:
        errors.append(f'Analysis sample must have six dialogues in each group: {actual_groups}')
    if len(verified) != len(selected):
        errors.append('Every dialogue in the analysis sample must be verified before calculation')
    return verified, pending, errors


def main():
    verified, pending, errors = validate_all()
    print(f'Проверенных аннотаций в выборке: {len(verified)}; pending: {pending}; ошибок: {len(errors)}')
    for error in errors:
        print('-', error)
    return bool(errors)


if __name__ == '__main__':
    sys.exit(main())
