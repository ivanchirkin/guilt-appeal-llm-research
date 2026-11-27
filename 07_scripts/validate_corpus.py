import csv, hashlib, sys
from collections import Counter
from common import ROOT, GROUPS, extract, render, read_turns, load_corrections, corrected_turns

def main():
    errors=[]; notes=[]
    def error(msg): errors.append(msg)
    with (ROOT/'dialogue_registry.csv').open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    expected={f'D{i:03}' for i in range(1,41)}; ids=[r['dialogue_id'] for r in rows]
    if len(rows)!=40 or set(ids)!=expected or len(set(ids))!=len(ids): error('Реестр: необходимо 40 уникальных ID D001–D040')
    keys=[(r['source_file'], r['original_dialogue_number']) for r in rows]
    if len(set(keys)) != len(keys): error('Реестр: повторяется пара исходный файл / номер диалога')
    corrections=load_corrections()
    if not set(corrections).issubset(set(ids)): error('Исправления ссылаются на отсутствующие ID')
    counts=Counter(r['group'] for r in rows)
    if counts!={g:10 for g,_ in GROUPS.values()}: error(f'Распределение групп: {counts}')
    files={p.stem for p in (ROOT/'02_corpus').glob('D*.md')}
    if files!=expected: error(f'Файлы корпуса: отсутствуют {sorted(expected-files)}, лишние {sorted(files-expected)}')
    sources={}
    for group,name in GROUPS.values():
        try: sources[name]={n:turns for n,turns in extract(ROOT/'01_original'/name)}
        except Exception as e: error(f'{name}: ошибка извлечения: {e}')
    with (ROOT/'04_protocol'/'source_sha256.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            p=ROOT/'01_original'/r['source_file']
            if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']: error(f'{p.name}: изменился контрольный SHA-256')
    seen={}; pairs=Counter(); a0=0
    for r in rows:
        did=r['dialogue_id']; name=r['source_file']; n=r['original_dialogue_number']; prefix=f'{did} ({name}, диалог {n})'
        if (r['group'],name) not in GROUPS.values(): error(f'{prefix}: группа и исходный документ не соответствуют конфигурации')
        if r['corpus_file']!=f'02_corpus/{did}.md': error(f'{prefix}: некорректный путь в реестре'); continue
        p=ROOT/r['corpus_file']
        if not p.exists() or p.stat().st_size==0: error(f'{prefix}: файл отсутствует или пуст'); continue
        try:
            text,turns=read_turns(p)
            labels=list(turns); expected_labels=(['A0'] if 'A0' in turns else [])+[x+str(i) for i in range(1,7) for x in ('B','A')]
            if labels!=expected_labels: error(f'{prefix}: неполная или неверная последовательность {labels}')
            if any(not v.strip() for v in turns.values()): error(f'{prefix}: пустая реплика')
            human=sum(k.startswith('B') for k in turns); model=sum(k.startswith('A') and k!='A0' for k in turns); pairs['human']+=human; pairs['model']+=model; a0+=('A0' in turns)
            if str(human)!=r['human_turns'] or str(model)!=r['model_turns'] or str('A0' in turns).lower()!=r['has_a0']: error(f'{prefix}: число реплик не совпадает с реестром')
            replacement=corrected_turns(did,r['group'],name,n,corrections)
            status='corrected_author' if replacement is not None else ('ok' if human==model==6 else 'incomplete_source')
            if r['extraction_status']!=status: error(f'{prefix}: неверный статус извлечения')
            src=replacement if replacement is not None else sources[name][int(n)]
            if text!=render(did,src): error(f'{prefix}: текст или структура отличаются от проверенного источника')
            fingerprint=hashlib.sha256(repr(list(turns.items())).encode('utf-8')).hexdigest()
            if fingerprint in seen: error(f'{prefix}: текст дублирует {seen[fingerprint]}')
            else: seen[fingerprint]=did
        except Exception as e: error(f'{prefix}: {e}')
    if pairs['human']!=240 or pairs['model']!=240: error(f'Ожидалось 240+240 реплик; фактически {pairs["human"]}+{pairs["model"]}')
    print(f'Реестр: {len(rows)}; группы: {dict(counts)}; файлов: {len(files)}; A0: {a0}; реплик B/A: {pairs["human"]}/{pairs["model"]}')
    if errors:
        print('ОБНАРУЖЕНЫ ПРОБЛЕМЫ:')
        for e in errors: print('-',e)
        return 1
    print(f'Проверка корпуса пройдена. Авторских замен: {len(corrections)}.'); return 0
if __name__=='__main__': sys.exit(main())
