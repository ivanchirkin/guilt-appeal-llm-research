import csv, hashlib, random, sys
from common import ROOT, GROUPS, SEED, extract, render, load_corrections, corrected_turns

def main():
    registry = ROOT/'dialogue_registry.csv'; corpus = ROOT/'02_corpus'; ann = ROOT/'05_annotations'
    if registry.exists() or (ROOT/'04_protocol'/'source_sha256.csv').exists() or list(corpus.glob('D*.md')) or list(ann.glob('*.json')):
        raise SystemExit('Остановлено: реестр, файлы корпуса или аннотации уже существуют; перезапись запрещена.')
    records=[]
    for latin,(group,name) in GROUPS.items():
        path=ROOT/'01_original'/name
        for number,turns in extract(path): records.append((group,name,number,turns))
    random.Random(SEED).shuffle(records)
    if len(records)!=40: raise SystemExit('Число диалогов не равно 40; запись отменена')
    corrections=load_corrections()
    if not set(corrections).issubset({f'D{i:03}' for i in range(1,41)}): raise SystemExit('Неизвестные ID в конфигурации исправлений')
    fields=['dialogue_id','group','source_file','original_dialogue_number','corpus_file','has_a0','human_turns','model_turns','extraction_status']
    rows=[]
    for n,(group,name,number,turns) in enumerate(records,1):
        did=f'D{n:03}'
        replacement=corrected_turns(did,group,name,number,corrections)
        if replacement is not None: turns=replacement
        records[n-1]=(group,name,number,turns)
        human=sum(k.startswith('B') for k,_ in turns); model=sum(k.startswith('A') and k!='A0' for k,_ in turns)
        status='corrected_author' if replacement is not None else ('ok' if human==model==6 else 'incomplete_source')
        rows.append(dict(dialogue_id=did,group=group,source_file=name,original_dialogue_number=number,corpus_file=f'02_corpus/{did}.md',has_a0=str(any(k=='A0' for k,_ in turns)).lower(),human_turns=human,model_turns=model,extraction_status=status))
    # Exclusive creation protects all existing work; no annotation is modified.
    for row,record in zip(rows,records):
        with (ROOT/row['corpus_file']).open('x',encoding='utf-8',newline='\n') as f: f.write(render(row['dialogue_id'],record[3]))
    with registry.open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    with (ROOT/'04_protocol'/'source_sha256.csv').open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f); w.writerow(['source_file','sha256'])
        for _,name in GROUPS.values(): w.writerow([name,hashlib.sha256((ROOT/'01_original'/name).read_bytes()).hexdigest()])
    print('Создано диалогов:',len(rows))
    for r in rows:
        if r['extraction_status']=='incomplete_source': print('ПРОБЛЕМА:',r['dialogue_id'],r['source_file'],'диалог',r['original_dialogue_number'],'пар:',r['human_turns'])
if __name__=='__main__': main()
