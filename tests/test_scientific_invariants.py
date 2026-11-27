"""Regression checks for consequential counting and annotation distinctions."""
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '07_scripts'))
from study import ROOT, annotation_metrics, guilt_performance, read_json
from calculate_metrics import summarize
from validate_annotations import validate_annotation


def base_annotation(occurrences):
    return {'dialogue_id': 'D001', 'human_assessment': 1,
        'guilt': {'value': 1, 'model_correct': True,
                  'evidence': [{'turn': 'A1', 'quote': 'текст один', 'reason': 'Тестовая цитата.'}]},
        'nat': {'score': 3, 'reason': 'Тестовое обоснование.', 'issues': []},
        'occurrences': occurrences, 'review_status': 'verified'}


class ScientificInvariants(unittest.TestCase):
    def test_multiturn_sequence_is_one_occurrence(self):
        turns = {f'A{i}': 'текст один' for i in range(1, 7)}
        annotation = base_annotation([{'code': 'G15', 'turns': ['A1', 'A2'],
                                      'quotes': ['текст один', 'текст один']}])
        metrics = annotation_metrics(annotation, turns)
        self.assertEqual((metrics['FLD'], metrics['FREQ']), (1, 1))

    def test_nested_levels_count_as_three_categories(self):
        annotation = base_annotation([{'code': code} for code in ('G01', 'G11', 'G14')])
        turns = {f'A{i}': 'общий фрагмент' for i in range(1, 7)}
        metrics = annotation_metrics(annotation, turns)
        self.assertEqual((metrics['FLD'], metrics['FREQ']), (3, 3))

    def test_mean_normalization_is_not_pooled_ratio(self):
        records = []
        for freq, words in [(10, 100), (20, 400)]:
            records.append({'dialogue_id': str(freq), 'FLD': 1, 'FREQ': freq,
                'word_count': words, 'FREQ_100': 100 * freq / words,
                'NAT_llm': 3, 'NAT_human': 3, 'GUILT_llm': 1,
                'GUILT_human': 1, 'GUILT_match': True})
        summary = summarize(records)
        self.assertEqual(summary['FREQ_100']['mean'], 7.5)
        self.assertEqual(summary['FREQ_100_pooled'], 6)

    def test_verified_does_not_turn_false_positive_into_correct_label(self):
        row = {'dialogue_id': 'D015', 'GUILT_human': 0, 'GUILT_llm': 1,
               'GUILT_match': False, 'review_status': 'verified'}
        result = guilt_performance([row])
        self.assertEqual(result['FP'], 1)
        self.assertEqual(result['accuracy'], 0)
        self.assertIsNone(result['sensitivity'])

    def test_sequence_quote_must_match_its_specific_turn(self):
        turns = {'A1': 'текст один', 'A2': 'текст два'}
        annotation = base_annotation([{'occurrence_id': 'E001', 'code': 'G15',
            'level': 'текстово-дискурсивный', 'turns': ['A1', 'A2'],
            'quotes': ['текст один', 'один'], 'function': 'Тестовый механизм.'}])
        validator = Draft202012Validator(read_json(ROOT / '04_protocol/annotation.levels.schema.json'))
        errors = validate_annotation(annotation, 'D001', turns, validator)
        self.assertTrue(errors)

    def test_code_cannot_move_to_another_level(self):
        annotation = base_annotation([{'occurrence_id': 'E001', 'code': 'G14',
            'level': 'лексический', 'turns': ['A1'], 'quotes': ['текст один'],
            'function': 'Тестовый механизм.'}])
        validator = Draft202012Validator(read_json(ROOT / '04_protocol/annotation.levels.schema.json'))
        self.assertTrue(list(validator.iter_errors(annotation)))


if __name__ == '__main__':
    unittest.main()
