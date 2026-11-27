"""Shared study definitions and portable data IO; no network calls."""
import csv
import hashlib
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ('К', 'А', 'Б', 'В')
CODES = tuple(f'G{i:02}' for i in range(1, 16))
LEVEL_NAMES = ('лексический', 'словообразовательный', 'морфологический',
               'лексико-грамматический', 'синтаксический',
               'семантико-прагматический', 'текстово-дискурсивный')
LEVELS = dict(zip(CODES, [LEVEL_NAMES[0]] * 4 + [LEVEL_NAMES[1], LEVEL_NAMES[2]]
                  + [LEVEL_NAMES[3]] * 3 + [LEVEL_NAMES[4]] * 4
                  + [LEVEL_NAMES[5], LEVEL_NAMES[6]]))
WORD = re.compile(r"[^\W_]+(?:[-‑’'][^\W_]+)*", re.UNICODE)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    temp.replace(path)


def write_csv(path, fields, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def selected_ids():
    return [r['dialogue_id'] for r in read_csv(ROOT / '04_protocol/analysis_sample.csv')
            if r['included'] == 'true']


def word_count(turns):
    return sum(len(WORD.findall(turns[f'A{i}'])) for i in range(1, 7))


def annotation_metrics(data, turns):
    codes = [occ['code'] for occ in data['occurrences']]
    words = word_count(turns)
    if not words:
        raise ValueError('A1–A6 contain no words')
    return {'FLD': len(set(codes)), 'FREQ': len(codes), 'word_count': words,
            'FREQ_100': 100 * len(codes) / words}


def descriptive(values):
    values = list(values)
    if not values:
        return {'n': 0, 'mean': None, 'median': None, 'min': None, 'max': None}
    return {'n': len(values), 'mean': statistics.mean(values),
            'median': statistics.median(values), 'min': min(values), 'max': max(values)}


def guilt_performance(records):
    tp = sum(r['GUILT_human'] == 1 and r['GUILT_llm'] == 1 for r in records)
    fn = sum(r['GUILT_human'] == 1 and r['GUILT_llm'] == 0 for r in records)
    fp = sum(r['GUILT_human'] == 0 and r['GUILT_llm'] == 1 for r in records)
    tn = sum(r['GUILT_human'] == 0 and r['GUILT_llm'] == 0 for r in records)
    ratio = lambda a, b: a / b if b else None
    sensitivity, specificity = ratio(tp, tp + fn), ratio(tn, tn + fp)
    return {'TP': tp, 'FN': fn, 'FP': fp, 'TN': tn,
            'accuracy': ratio(tp + tn, len(records)),
            'sensitivity': sensitivity, 'specificity': specificity,
            'precision_positive': ratio(tp, tp + fp),
            'false_positive_rate': ratio(fp, fp + tn),
            'balanced_accuracy': (sensitivity + specificity) / 2
                if sensitivity is not None and specificity is not None else None,
            'disagreements': [r['dialogue_id'] for r in records if not r['GUILT_match']]}
