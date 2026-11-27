from pathlib import Path
import re
import hashlib
import json
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

ROOT = Path(__file__).resolve().parent.parent
GROUPS = {'A': ('А', 'ДИАЛОГИ А.docx'), 'B': ('Б', 'ДИАЛОГИ Б.docx'), 'V': ('В', 'ДИАЛОГИ В.docx'), 'K': ('К', 'Диалоги К.docx')}
SEED = 20261109
HEADING = re.compile(r'^\s*диалог\s+(\d+)\s*$', re.I)
MARKER = re.compile(r'^\s*(вопрос|ответ)\s*$', re.I)
HEAD = re.compile(r'^## (A0|[AB][1-6])\. (?:Начальная реплика модели|Реплика человека|Ответ модели)$', re.M)

def paragraphs(container):
    for block in container.iter_inner_content():
        if isinstance(block, Paragraph):
            yield block.text
        elif isinstance(block, Table):
            # Merged cells are unsafe to linearize: the same text can occur twice.
            for row in block.rows:
                seen = set()
                for cell in row.cells:
                    if id(cell._tc) in seen:
                        raise ValueError('Объединённые ячейки таблицы требуют ручной проверки')
                    seen.add(id(cell._tc))
                    yield from paragraphs(cell)

def clean_edges(parts):
    parts = list(parts)
    while parts and not parts[0].strip(): parts.pop(0)
    while parts and not parts[-1].strip(): parts.pop()
    return '\n\n'.join(parts)

def extract(path):
    doc = Document(path)
    xml = doc.element.xml
    for tag in ('drawing', 'pict', 'txbxContent', 'ins', 'del', 'footnoteReference', 'endnoteReference'):
        if re.search(r'<w:' + tag + r'(?:\s|>|/)', xml):
            raise ValueError(f'{path.name}: неподдерживаемый объект {tag}')
    chunks = []
    for p in paragraphs(doc):
        m = HEADING.fullmatch(p)
        if m:
            chunks.append((int(m.group(1)), []))
        elif not chunks:
            if p.strip(): raise ValueError(f'{path.name}: текст перед первым диалогом: {p[:80]}')
        else: chunks[-1][1].append(p)
    numbers = [n for n, _ in chunks]
    if numbers != list(range(1,11)): raise ValueError(f'{path.name}: неожиданные номера диалогов {numbers}')
    out = []
    for number, content in chunks:
        blocks = [('A0', [])]
        count = {'вопрос': 0, 'ответ': 0}
        for p in content:
            m = MARKER.fullmatch(p)
            if m:
                kind = m.group(1).lower(); count[kind] += 1
                label = ('B' if kind == 'вопрос' else 'A') + str(count[kind])
                blocks.append((label, []))
            else: blocks[-1][1].append(p)
        turns = [(label, clean_edges(parts)) for label, parts in blocks]
        if not turns[0][1]: turns = turns[1:]
        expected = ([('B' if i%2==0 else 'A')+str(i//2+1) for i in range(count['вопрос']+count['ответ'])])
        actual = [k for k, _ in turns if k != 'A0']
        if count['вопрос'] != count['ответ'] or actual != expected or any(not text.strip() for _,text in turns):
            raise ValueError(f'{path.name}, диалог {number}: неоднозначные, пустые или несогласованные реплики {actual}')
        if count['вопрос'] > 6: raise ValueError(f'{path.name}, диалог {number}: больше шести пар')
        out.append((number, turns))
    return out

def render(dialogue_id, turns):
    titles = {'A0': 'Начальная реплика модели'}
    chunks = [f'# Диалог {dialogue_id}']
    for label, content in turns:
        title = titles.get(label, 'Реплика человека' if label.startswith('B') else 'Ответ модели')
        chunks.append(f'## {label}. {title}\n\n{content}')
    return '\n\n'.join(chunks) + '\n'

def read_turns(path):
    s = path.read_text(encoding='utf-8')
    found = list(HEAD.finditer(s))
    turns = {}
    for i,m in enumerate(found):
        end = found[i+1].start() if i+1<len(found) else len(s)
        t = s[m.end():end]
        if not t.startswith('\n\n'): raise ValueError('Неверное оформление заголовка')
        t = t[2:]
        t = t[:-2] if i+1<len(found) and t.endswith('\n\n') else t[:-1] if i+1==len(found) and t.endswith('\n') else t
        if m.group(1) in turns: raise ValueError('Повторная метка реплики')
        turns[m.group(1)] = t
    return s, turns


def load_corrections():
    path = ROOT/'04_protocol'/'corrections.json'
    if not path.exists(): return {}
    corrections = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(corrections, dict): raise ValueError('Некорректная конфигурация исправлений')
    return corrections

def corrected_turns(dialogue_id, group, source_file, original_number, corrections=None):
    corrections = load_corrections() if corrections is None else corrections
    if dialogue_id not in corrections: return None
    meta = corrections[dialogue_id]
    if (meta['group'], meta['source_file'], int(meta['original_dialogue_number'])) != (group, source_file, int(original_number)):
        raise ValueError(f'{dialogue_id}: исправление не соответствует исходному диалогу и группе')
    path = (ROOT / meta['replacement_file']).resolve()
    correction_dir = (ROOT/'04_protocol'/'corrections').resolve()
    if not path.is_relative_to(correction_dir) or not path.is_file():
        raise ValueError(f'{dialogue_id}: путь к тексту исправления некорректен')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != meta['sha256']:
        raise ValueError(f'{dialogue_id}: контрольная сумма текста исправления не совпадает')
    blocks = [('A0', [])]; counts = {'вопрос': 0, 'ответ': 0}
    for line in raw.decode('utf-8-sig').splitlines():
        marker = MARKER.fullmatch(line)
        if marker:
            kind = marker.group(1).lower(); counts[kind] += 1
            blocks.append((('B' if kind == 'вопрос' else 'A') + str(counts[kind]), []))
        else: blocks[-1][1].append(line)
    turns = []
    for label, lines in blocks:
        while lines and not lines[0].strip(): lines.pop(0)
        while lines and not lines[-1].strip(): lines.pop()
        turns.append((label, '\n'.join(lines)))
    expected = ['A0'] + [prefix+str(i) for i in range(1,7) for prefix in ('B','A')]
    if [label for label,_ in turns] != expected or any(not value.strip() for _,value in turns):
        raise ValueError(f'{dialogue_id}: исправленный текст должен содержать A0 и шесть последовательных пар')
    return turns
