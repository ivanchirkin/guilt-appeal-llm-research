"""Recalculate all four metrics from verified annotations and human ratings."""
import sys
from collections import Counter
from statistics import mean

from study import (ROOT, GROUPS, CODES, LEVELS, LEVEL_NAMES, read_csv, read_json,
                   write_csv, write_json, annotation_metrics, descriptive,
                   guilt_performance, sha256)
from validate_annotations import validate_all


def summarize(records):
    summary = {'n': len(records)}
    for key in ('FLD', 'FREQ', 'NAT_llm', 'NAT_human', 'word_count', 'FREQ_100'):
        summary[key] = descriptive(r[key] for r in records)
    summary['FREQ_total'] = sum(r['FREQ'] for r in records)
    summary['word_count_total'] = sum(r['word_count'] for r in records)
    summary['FREQ_100_pooled'] = 100 * summary['FREQ_total'] / summary['word_count_total'] if records else None
    summary['guilt_positive_llm'] = sum(r['GUILT_llm'] for r in records)
    summary['guilt_positive_human'] = sum(r['GUILT_human'] for r in records)
    summary['guilt_performance'] = guilt_performance(records)
    summary['nat_distribution'] = {
        who: {str(s): sum(r[f'NAT_{who}'] == s for r in records) for s in range(1, 6)}
        for who in ('llm', 'human')}
    diffs = [r['NAT_human'] - r['NAT_llm'] for r in records]
    summary['nat_agreement'] = {'exact_n': diffs.count(0),
        'exact_share': diffs.count(0) / len(records) if records else None,
        'within_one_n': sum(abs(d) <= 1 for d in diffs),
        'human_higher_n': sum(d > 0 for d in diffs),
        'llm_higher_n': sum(d < 0 for d in diffs),
        'mean_difference_human_minus_llm': mean(diffs) if diffs else None,
        'mean_absolute_difference': mean(abs(d) for d in diffs) if diffs else None}
    return summary


def main():
    verified, pending, errors = validate_all()
    if errors:
        print('\n'.join(errors)); return 1
    human = {r['dialogue_id']: r for r in read_csv(ROOT / '05_annotations/human_nat.csv')}
    records, code_rows = [], []
    for registry, annotation, turns in verified:
        did, group = registry['dialogue_id'], registry['group']
        record = {'dialogue_id': did, 'group': group, 'review_status': annotation['review_status'],
                  'GUILT_human': annotation['human_assessment'],
                  'GUILT_llm': annotation['guilt']['value'],
                  'GUILT_match': annotation['guilt']['model_correct'],
                  'NAT_llm': annotation['nat']['score'], 'NAT_human': int(human[did]['score']),
                  **annotation_metrics(annotation, turns)}
        records.append(record)
        counts = Counter(o['code'] for o in annotation['occurrences'])
        for code in CODES:
            code_rows.append({'scope': 'dialogue', 'dialogue_id': did, 'group': group,
                'n': 1, 'code': code, 'level': LEVELS[code], 'frequency': counts[code],
                'dialogues_present': int(counts[code] > 0), 'mean_per_dialogue': counts[code]})
    groups = {g: summarize([r for r in records if r['group'] == g]) for g in GROUPS}
    category_rows, level_rows = [], []
    for group in GROUPS:
        n = groups[group]['n']
        for code in CODES:
            rs = [r for r in code_rows if r['group'] == group and r['code'] == code]
            category_rows.append({'scope': 'group', 'dialogue_id': '', 'group': group,
                'n': n, 'code': code, 'level': LEVELS[code],
                'frequency': sum(r['frequency'] for r in rs),
                'dialogues_present': sum(r['dialogues_present'] for r in rs),
                'mean_per_dialogue': mean(r['frequency'] for r in rs)})
        for level in LEVEL_NAMES:
            frequency = sum(r['frequency'] for r in category_rows if r['group'] == group and r['level'] == level)
            total = groups[group]['FREQ_total']
            level_rows.append({'group': group, 'level': level, 'frequency': frequency,
                               'share_of_group_FREQ': frequency / total if total else 0})
    source_paths = [ROOT / 'dialogue_registry.csv', ROOT / '04_protocol/analysis_sample.csv',
                    ROOT / '05_annotations/human_nat.csv', ROOT / '04_protocol/annotation.levels.schema.json']
    for registry, _, _ in verified:
        source_paths.extend([ROOT / registry['corpus_file'], ROOT / f'05_annotations/{registry["dialogue_id"]}.json'])
    source_hashes = {p.relative_to(ROOT).as_posix(): sha256(p) for p in source_paths}
    overall = summarize(records)
    zero_control = [dict(r, FLD=0, FREQ=0, FREQ_100=0.0) if r['GUILT_human'] == 0 else dict(r) for r in records]
    snapshot = {'snapshot_date': read_json(ROOT / '04_protocol/study.json')['snapshot_date'],
        'scope': 'D001–D024; only A1–A6; verified annotations; original model decisions preserved',
        'reference_guilt_origin': 'Author-provided group labels: А/Б/В=1, К=0; not an independent blind text adjudication',
        'fld_freq_origin': 'Counts of saved model-coded occurrences, including disputed control occurrences',
        'normalization': 'FREQ_100 group mean is the mean of dialogue ratios; pooled ratio is reported separately',
        'records': records, 'overall': overall, 'groups': groups,
        'categories': category_rows, 'levels': level_rows,
        'reference_gated_sensitivity': {'status': 'conditional scenario, not human reannotation',
            'rule': 'Set FLD/FREQ to zero when GUILT_human=0; do not change occurrences',
            'overall': summarize(zero_control),
            'groups': {g: summarize([r for r in zero_control if r['group'] == g]) for g in GROUPS}},
        'source_sha256': source_hashes}
    out = ROOT / '06_results'
    write_csv(out / 'dialogue_metrics.csv', list(records[0]), records)
    summary_rows = []
    for group, s in groups.items():
        row = {'group': group, 'verified_n': s['n'],
               'GUILT_llm_positive_n': s['guilt_positive_llm'],
               'GUILT_human_positive_n': s['guilt_positive_human']}
        for key in ('FLD', 'FREQ', 'NAT_llm', 'NAT_human', 'word_count', 'FREQ_100'):
            for stat in ('mean', 'median', 'min', 'max'):
                row[f'{key}_{stat}'] = s[key][stat]
        row.update(FREQ_total=s['FREQ_total'], FREQ_100_pooled=s['FREQ_100_pooled'])
        summary_rows.append(row)
    write_csv(out / 'group_summary.csv', list(summary_rows[0]), summary_rows)
    write_csv(out / 'g_code_distribution.csv', list(code_rows[0]), code_rows + category_rows)
    write_csv(out / 'category_summary.csv', list(category_rows[0]), category_rows)
    write_csv(out / 'level_summary.csv', list(level_rows[0]), level_rows)
    nat_rows = [{'group': group, 'evaluator': who, 'score': score,
                'n': s['nat_distribution'][who][str(score)],
                'share': s['nat_distribution'][who][str(score)] / s['n']}
        for group, s in [('ALL', overall), *groups.items()]
        for who in ('llm', 'human') for score in range(1, 6)]
    write_csv(out / 'nat_distribution.csv', list(nat_rows[0]), nat_rows)
    perf = overall['guilt_performance']
    confusion = [{'GUILT_human': h, 'GUILT_llm': m, 'outcome': label, 'n': perf[label]}
                 for h, m, label in [(0, 0, 'TN'), (0, 1, 'FP'), (1, 0, 'FN'), (1, 1, 'TP')]]
    write_csv(out / 'guilt_confusion.csv', list(confusion[0]), confusion)
    write_json(out / 'summary.json', snapshot)
    print(f'Рассчитано: {len(records)} диалога, FREQ={overall["FREQ_total"]}, '
          f'NAT LLM={overall["NAT_llm"]["mean"]:.3f}, человек={overall["NAT_human"]["mean"]:.3f}.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
