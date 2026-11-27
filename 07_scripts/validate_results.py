"""Cross-check saved result tables and figure provenance against source data."""
import math
import sys
from statistics import mean

from study import ROOT, GROUPS, read_csv, read_json, sha256, write_json
from validate_annotations import validate_all


def main():
    verified, _, errors = validate_all()
    data = read_json(ROOT / '06_results/summary.json')
    metrics = read_csv(ROOT / '06_results/dialogue_metrics.csv')
    records = data['records']
    if len(metrics) != len(verified) or [r['dialogue_id'] for r in metrics] != [r['dialogue_id'] for r in records]:
        errors.append('Dialogue metric IDs/counts do not match verified annotations')
    annotations = {r['dialogue_id']: a for r, a, _ in verified}
    for row, record in zip(metrics, records):
        did = row['dialogue_id']; annotation = annotations[did]
        codes = [o['code'] for o in annotation['occurrences']]
        if int(row['FREQ']) != len(codes) or int(row['FLD']) != len(set(codes)):
            errors.append(f'{did}: FLD/FREQ mismatch')
        for key in ('FREQ', 'FLD', 'word_count', 'FREQ_100', 'NAT_llm', 'NAT_human', 'GUILT_llm', 'GUILT_human'):
            if not math.isclose(float(row[key]), record[key], abs_tol=1e-10):
                errors.append(f'{did}: CSV/JSON disagreement in {key}')
    for group in GROUPS:
        rs = [r for r in records if r['group'] == group]
        expected = mean(100 * r['FREQ'] / r['word_count'] for r in rs)
        if not math.isclose(expected, data['groups'][group]['FREQ_100']['mean'], abs_tol=1e-10):
            errors.append(f'{group}: mean of individual ratios is incorrect')
    code_rows = read_csv(ROOT / '06_results/g_code_distribution.csv')
    if sum(int(r['frequency']) for r in code_rows if r['scope'] == 'dialogue') != sum(r['FREQ'] for r in records):
        errors.append('Category counts do not sum to total FREQ')
    for relative, expected in data['source_sha256'].items():
        if sha256(ROOT / relative) != expected:
            errors.append(f'Stale metric input: {relative}')
    manifest_path = ROOT / '06_results/figures/manifest.json'
    figure_n = 0
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        if manifest['source_sha256'] != sha256(ROOT / manifest['source']):
            errors.append('Figure data snapshot is stale')
        for fig in manifest['figures']:
            figure_n += 1
            for ext in ('png', 'svg'):
                if sha256(ROOT / fig[ext]) != fig['sha256'][ext]:
                    errors.append(f'Figure checksum mismatch: {fig[ext]}')
    else:
        errors.append('No figure manifest')
    report = {'snapshot_date': data['snapshot_date'], 'status': 'passed' if not errors else 'failed',
        'selected_annotations': len(verified), 'verified_annotations': len(verified),
        'figures': figure_n, 'errors': errors,
        'scope': 'Technical checks of structure, quotes, counts and provenance; does not replace linguistic adjudication'}
    write_json(ROOT / '06_results/validation_report.json', report)
    for error in errors:
        print('-', error)
    print(f'Итоговая проверка: {report["status"]}; аннотаций: {len(verified)}; диаграмм: {figure_n}.')
    return bool(errors)


if __name__ == '__main__':
    sys.exit(main())
