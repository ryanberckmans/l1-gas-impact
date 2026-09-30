"""Stage source datasets for review; release acceptance is a separate explicit gate."""
from pathlib import Path
import argparse,json,shutil
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'research'
DATA=ROOT/'data';INPUT=DATA/'inputs'
def load(p):return json.loads(p.read_text())
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def main():
 INPUT.mkdir(parents=True,exist_ok=True)
 eth=load(R/'eth_transfers/eth_transfers_daily.json');save(INPUT/'eth.json',eth)
 uni=load(R/'benchmarks/uniswap_normalized.json');save(INPUT/'uniswap.json',uni)
 lighter=load(R/'lighter/lighter-normalized.json')
 mapping={'settlement_data':'batch_submission','settlement_proofs':'verify_batch','settlement_state':'execute_batch','user_deposits':'deposits','withdrawal_requests':'withdrawal_requests','withdrawal_claims':'withdrawal_claims','user_controls':'account_controls','emergency_exits':'emergency','other_direct':'other','governance_admin':'governance','deployments':'deployments','treasury_withdrawals':'withdrawal_claims','exclusive_wrappers':'exclusive_wrappers'}
 lr=[]
 for r in lighter['daily']:
  lr.append({'date':r['date'],'product':'lighter','bucket':mapping[r['bucket']],'gas_used':r['gasUsed'],'tx_count':r['transactionCount'],'source_id':'lighter-receipts-'+r['bucket']})
 save(INPUT/'lighter.json',lr)
 rollups=load(R/'rollups/rollups-strict-daily.json')
 included=load(R/'rollups/rollups-included-sources.json');sid_map={s['source_id']:s for s in included if 'source_id' in s}
 for r in rollups:
  src=sid_map.get(r['source_id'],{});b=src.get('bucket')
  if b in ['batch_submission','settlement','dedicated_token_bridge','canonical_bridge']:r['detail_bucket']=b
  elif 'withdrawal' in r['source_id']:r['detail_bucket']='withdrawal_claims'
  elif 'deployment' in r['source_id']:r['detail_bucket']='deployments'
 save(INPUT/'rollups.json',rollups)
 more=load(R/'additional/additional_daily.json');save(INPUT/'additional.json',more)
 save(DATA/'inputs.json',{'accepted_for_publication':False,'inputs':[{'path':'inputs/eth.json','source_id':'blockchair-plain-eth-transfer-benchmark'},{'path':'inputs/uniswap.json'},{'path':'inputs/lighter.json'},{'path':'inputs/rollups.json'},{'path':'inputs/additional.json'}]})
 save(DATA/'cohort-sources.json',{'eth':load(R/'eth_transfers/summary.json'),'uniswap':load(R/'benchmarks/uniswap_manifest.json'),'lighter':{k:v for k,v in lighter.items() if k!='daily'},'rollups_included':included,'rollups_excluded':load(R/'rollups/rollups-excluded-sources.json'),'approvals':load(R/'additional/approvals_manifest_corrected.json'),'cctp':load(R/'additional/cctp_manifest_corrected.json'),'across':load(R/'additional/across_manifest_corrected.json')})
 print('Staged current complete cohorts for unpublished review; publication remains blocked.')
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--research-dir',type=Path,default=R,help='Directory containing the historical source cohorts')
 R=parser.parse_args().research_dir.expanduser().resolve()
 main()
