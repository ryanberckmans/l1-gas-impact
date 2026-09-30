"""Strictly classify acquired Ethereum receipts, then reconcile before staging.

Research dependencies: eth-abi==5.2.0, eth-utils==5.3.1, pycryptodome==3.23.0.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict, Counter
import json, gzip, csv, hashlib, sys, io
from eth_abi import decode, encode
from eth_utils import keccak

R=Path(sys.argv[1]);ROOT=Path(__file__).resolve().parents[1]
CAT=json.loads((R/'catalog.json').read_text())
L2_MESSENGER='0x4200000000000000000000000000000000000007'
L2_BRIDGE='0x4200000000000000000000000000000000000010'
TUPLE='(uint256,address,address,uint256,uint256,bytes)'
RELAY=['uint256','address','address','uint256','uint256','bytes']
FINAL=['address','address','address','address','uint256','bytes']

def save(p,j):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(j,indent=2)+'\n')
def selector(sig):return '0x'+keccak(text=sig)[:4].hex()
def checked(types,raw):
    values=decode(types,raw)
    assert raw.startswith(encode(types,values)),'Noncanonical ABI encoding'
    return values
def day(r):return datetime.fromtimestamp(int(r['timeStamp']),timezone.utc).date().isoformat()
def method(name,types):return (selector(name+'('+','.join(types)+')'),types)
DEPOSITS=dict([
    method('depositERC20',['address','address','uint256','uint32','bytes']),
    method('depositERC20To',['address','address','address','uint256','uint32','bytes']),
    method('bridgeERC20',['address','address','uint256','uint32','bytes']),
    method('bridgeERC20To',['address','address','address','uint256','uint32','bytes']),
    method('bridgeETH',['uint32','bytes']),method('bridgeETHTo',['address','uint32','bytes']),
    method('depositETH',['uint32','bytes']),method('depositETHTo',['address','uint32','bytes'])])
FINAL_SELECTORS={selector('finalizeBridgeERC20('+','.join(FINAL)+')'),selector('finalizeERC20Withdrawal('+','.join(FINAL)+')')}

def withdrawal(p,data,sel):
    types=[TUPLE] if sel=='0x8c3152e9' else [TUPLE,'address']
    w=checked(types,data)[0]
    messenger=next(s['recipient'] for s in CAT if s['product']==p and s['kind']=='messenger')
    assert w[1]==L2_MESSENGER and w[2]==messenger and w[3]==0,'Native ETH or arbitrary outer target'
    assert w[5][:4].hex()=='d764ad0b','Unrecognized message relay'
    relay=checked(RELAY,w[5][4:])
    assert relay[3]==0,'Native ETH relay'
    standard=next(s['recipient'] for s in CAT if s['product']==p and s['name']=='L1StandardBridge')
    targets={standard:L2_BRIDGE}
    alias='optimism' if p=='op' else p
    discovery=json.loads((R/(alias+'-discovered.json')).read_text())
    for e in discovery['entries']:
        if e.get('name') in ['L1ERC20TokenBridge','L1DAITokenBridge','wstETHEscrow'] and e['address'].startswith('eth:'):
            v=e['values'];remote=v.get('l2TokenBridge',v.get('l2DAITokenBridge'))
            if remote:targets[e['address'].split(':')[-1].lower()]=remote.split(':')[-1].lower()
    assert targets.get(relay[2])==relay[1],'Noncanonical token bridge endpoints'
    assert '0x'+relay[5][:4].hex() in FINAL_SELECTORS,'Non-token or unreviewed bridge method'
    checked(FINAL,relay[5][4:])
    return 'withdrawal_claims'

def classify(s,r):
    inp=r['input'];sel=inp[:10];data=bytes.fromhex(inp[10:]) if len(inp)>=10 else b''
    if s['kind']=='batch':
        assert r['from'].lower() in s['senders'],'Unverified batch sender'
        if s['product']=='ink':
            expected='0x500d7ea63cf2e501dadaa5feec1fc19fe2aa72ac' if int(r['blockNumber'])<25631821 else '0x6db6161fc5662450e801398bad62dd9921216b98'
            assert r['from'].lower()==expected,'Outside reviewed batcher interval'
        return 'batch_submission'
    if s['kind']=='settlement':
        assert s['name']=='DisputeGameFactory' and sel=='0x82ecf2f6','Unreviewed settlement method'
        checked(['uint32','bytes32','bytes'],data);return 'settlement'
    if s['kind']=='governance':
        allowed=dict([method('setEIP1559Params',['uint32','uint32']),method('setMinBaseFee',['uint64'])])
        assert sel in allowed,'Unreviewed administration method'
        checked(allowed[sel],data);return 'governance'
    if s['kind'] in ['canonical_bridge','dedicated_token_bridge']:
        if inp=='0x' and s['name']=='L1StandardBridge':return 'canonical_bridge'
        assert sel in DEPOSITS,'Unreviewed bridge method'
        checked(DEPOSITS[sel],data);return s['kind']
    if s['kind']=='messenger':
        assert sel=='0x3dbb202b','Arbitrary inbound message'
        checked(['address','bytes','uint32'],data);return 'canonical_bridge'
    if s['kind']=='portal':
        if sel=='0xe9e05c42':
            checked(['address','uint256','uint64','bool','bytes'],data);return 'deposits'
        if sel=='0x4870496f':
            checked([TUPLE,'uint256','(bytes32,bytes32,bytes32,bytes32)','bytes[]'],data);return 'withdrawal_proofs'
        if sel in ['0x8c3152e9','0x43ca1c50']:return withdrawal(s['product'],data,sel)
        if inp=='0x':return 'deposits'
        raise AssertionError('Unreviewed portal method')
    raise AssertionError('Unreviewed contract class')

def main():
    COR=json.loads((R.parent/'reference/canonical_correction_transactions.json').read_text())
    assert all(json.loads((R/f'{mode}-errors.json').read_text())==[] for mode in ['receipts','aggregates','supplement'])
    accepted=[];excluded=[];sources=[];reconciliations=[];seen=set();repairs=[]
    for p in ['worldchain','op']:
        origin=json.loads((R/(p+'-omitted.json')).read_text())
        for r in origin['transactions']:
            proof=json.loads((R/(p+'-omitted-rpc.json')).read_text()).get('result')
            assert proof and proof['transactionHash']==r['hash'],'Missing independent receipt confirmation'
            assert int(proof['gasUsed'],16)==r['gas_used'] and int(proof['blockNumber'],16)==r['block_id']
            repairs.append({'hash':r['hash'],'product':p,'block':r['block_id'],'gas_used':r['gas_used'],
                'source':'Blockchair raw transaction, matched to Ethereum JSON-RPC receipt via Routescan proxy',
                'raw_sources':origin['sources'],'receipt_file':p+'-omitted-rpc.json'})
    for s in CAT:
        tag=s['product']+'-'+s['recipient']
        m=json.loads((R/'receipt-manifests'/(tag+'.json')).read_text())
        rows=[json.loads(l) for l in gzip.open(R/m['ledger'],'rt')]
        for repair in repairs:
            if repair['product']==s['product']:
                raw=next(r for r in json.loads((R/(s['product']+'-omitted.json')).read_text())['transactions'] if r['hash']==repair['hash'])
                if raw['recipient']==s['recipient']:
                    rows.append({'hash':raw['hash'],'timeStamp':str(int(datetime.fromisoformat(raw['time']).replace(tzinfo=timezone.utc).timestamp())),
                        'blockNumber':str(raw['block_id']),'from':raw['sender'],'to':raw['recipient'],'gasUsed':str(raw['gas_used']),
                        'input':'0x'+raw['input_hex'],'value':raw['value'],'isError':'1' if raw['failed'] else '0','txreceipt_status':'0' if raw['failed'] else '1'})
        assert len({r['hash'] for r in rows})==len(rows)
        observed=defaultdict(lambda:[0,0])
        for r in rows:observed[day(r)][0]+=int(r['gasUsed']);observed[day(r)][1]+=1
        agg=json.loads((R/'aggregate-manifests'/(tag+'.json')).read_text())
        bc={r['date']:[r['sum(gas_used)'],r['count()']] for r in json.loads((R/agg['raw_file']).read_text())['data']}
        corrections=[]
        if 'ETH4' in agg['context']['servers']:
            for r in COR:
                if r['recipient']==s['recipient']:
                    bc[r['date']][0]-=r['gas_used'];bc[r['date']][1]-=1;corrections.append(r['hash'])
        assert dict(observed)==bc,('Daily two-provider reconciliation',s['source_id'])
        reconciliations.append({'source_id':s['source_id'],'days_checked':184,'receipts':len(rows),'gas_used':sum(v[0] for v in observed.values()),'daily_count_and_gas_match':True,'duplicate_hashes_removed_from_aggregate':corrections})
        counts=Counter();gas=Counter();rejects=Counter()
        for r in rows:
            try:bucket=classify(s,r)
            except Exception as exc:
                why=str(exc) or type(exc).__name__;rejects[why]+=1
                excluded.append({'product':s['product'],'hash':r['hash'],'gas_used':int(r['gasUsed']),'selector':r['input'][:10],'reason':why});continue
            assert r['hash'] not in seen,'Cross-source duplicate'
            seen.add(r['hash']);counts[bucket]+=1;gas[bucket]+=int(r['gasUsed'])
            accepted.append({'date':day(r),'product':s['product'],'transaction_hash':r['hash'],'block_number':int(r['blockNumber']),
                'gas_used':int(r['gasUsed']),'sender':r['from'].lower(),'recipient':r['to'].lower(),'activity':bucket,
                'source_id':s['source_id'],'selector':r['input'][:10],'status':'failed' if r['isError']=='1' else 'success'})
        sources.append({**s,'measurement':'Actual Ethereum L1 transaction gasUsed; hash-deduplicated receipts, reviewed ABI methods only',
            'included_transactions':sum(counts.values()),'gas_used':sum(gas.values()),'activity_counts':dict(counts),'activity_gas':dict(gas),
            'excluded_counts':dict(rejects),'receipt_sources':m['pages'],'aggregate_crosscheck':agg['url'],
            'period_complete_for_queried_addresses':True})
    by_day=defaultdict(lambda:[0,0])
    for r in accepted:
        v=by_day[(r['date'],r['product'],r['activity'],r['source_id'])];v[0]+=r['gas_used'];v[1]+=1
    core=[{'date':d,'product':p,'bucket':b,'source_id':sid,'gas_used':v[0],'tx_count':v[1]} for (d,p,b,sid),v in sorted(by_day.items())]
    save(R/'expanded-core.json',core)
    save(R/'classification-manifest.json',{'sources':sources,'reconciliations':reconciliations,'repairs':repairs,'excluded_transactions':excluded,
        'method':'Strict ABI decoding with canonical-prefix re-encoding; trailing integrator tags are non-executable calldata and retained in receipt gas; portal finalizations require zero ETH, the chain-specific messenger and a reviewed canonical ERC20 bridge payout. Native ETH and arbitrary target finalizations excluded.',
        'scope_exclusions':['Shared Superchain governance, shared implementations and verifier deployments','Unindexed dynamic dispute-game calls','Unreviewed multisig operations and external transaction wrappers','Global World ID and WLD activity unrelated to World Chain','Uniswap trading on Unichain is not measured as L1 Uniswap execution'],
        'accepted_transactions':len(accepted),'gas_used':sum(r['gas_used'] for r in accepted)})
    for p in ['worldchain','unichain','op','ink']:
        path=R/'exports'/f'receipts-{p}.csv.gz';path.parent.mkdir(exist_ok=True)
        data=sorted((r for r in accepted if r['product']==p),key=lambda r:(r['block_number'],r['transaction_hash']))
        f=io.StringIO(newline='')
        writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
        payload=f.getvalue().encode();compressed=gzip.compress(payload,mtime=0)
        path.write_bytes(compressed)
        assert gzip.decompress(path.read_bytes())==payload,'Incomplete receipt export'
        print(json.dumps({'product':p,'receipts':len(data),'core_gas_used':sum(r['gas_used'] for r in data),'excluded':sum(r['product']==p for r in excluded)}))

if __name__=='__main__':main()
