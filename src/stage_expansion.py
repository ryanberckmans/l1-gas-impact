"""Stage reconciled expansion records and receipt exports for release review."""
from pathlib import Path
from collections import defaultdict
import json,sys,csv,gzip,io,hashlib

ROOT=Path(__file__).resolve().parents[1];R=Path(sys.argv[1]);DATA=ROOT/'data'
def read(p):return json.loads(p.read_text())
def save(p,j):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
def main():
    assert read(R/'supplement-verification-errors.json')==[]
    core=read(R/'expanded-core.json');verified=read(R/'supplement-verification.json')
    metadata=read(R/'classification-manifest.json')
    assert all(v['daily_count_and_gas_match'] for v in metadata['reconciliations'])
    supplement=[]
    for p in sorted((R/'supplement-verified').glob('*.json')):supplement.extend(read(p))
    assert len(supplement)==sum(v['accepted'] for v in verified)
    grouped=defaultdict(lambda:[0,0])
    for r in supplement:
        token=r['recipient'] if r['activity']=='approvals' else ''
        key=(r['date'],r['product'],r['activity'],r['source_id'],token)
        grouped[key][0]+=r['gas_used'];grouped[key][1]+=1
    rows=core+[{'date':d,'product':p,'bucket':b,'source_id':sid,'gas_used':v[0],'tx_count':v[1],**({'token':token} if token else {})} for (d,p,b,sid,token),v in sorted(grouped.items())]
    save(DATA/'inputs/expanded.json',rows)
    config=read(DATA/'inputs.json');config['accepted_for_publication']=False
    if not any(e['path']=='inputs/expanded.json' for e in config['inputs']):config['inputs'].append({'path':'inputs/expanded.json'})
    save(DATA/'inputs.json',config)
    seen=set();exports={}
    for p in ['worldchain','unichain','op','ink']:
        with gzip.open(R/'exports'/f'receipts-{p}.csv.gz','rt') as f:receipts=list(csv.DictReader(f))
        receipts.extend(r for r in supplement if r['product']==p)
        for r in receipts:
            h=r['transaction_hash'];assert h not in seen,'Overlapping expansion populations';seen.add(h)
        receipts.sort(key=lambda r:(int(r['block_number']),r['transaction_hash']))
        f=io.StringIO(newline='');w=csv.DictWriter(f,fieldnames=list(receipts[0]));w.writeheader();w.writerows(receipts)
        payload=f.getvalue().encode();path=ROOT/'dist/data'/f'receipts-{p}.csv.gz';path.write_bytes(gzip.compress(payload,mtime=0))
        assert gzip.decompress(path.read_bytes())==payload
        exports[p]={'url':'/data/'+path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'transactions':len(receipts),'gas_used':sum(int(r['gas_used']) for r in receipts),
            'scope':'All included contract, approval and Across/CCTP transactions in this product’s published lower bound; unresolved populations remain excluded.'}
        assert exports[p]['gas_used']==sum(r['gas_used'] for r in rows if r['product']==p)
    save(DATA/'expanded-receipt-exports.json',exports)
    save(DATA/'expanded-methods.json',{'products':['worldchain','unichain','op','ink'],'contract_reconciliation':metadata,'supplement_reconciliation':verified,
        'receipt_samples':read(R/'receipt-sample-verification.json'),'receipt_exports':exports})
    print(json.dumps({'staged_records':len(rows),'receipts':len(seen),'publication_ready':False,'products':exports}))

if __name__=='__main__':main()
