"""Adversarial attribution checks: shared routes must fail closed."""
import json,sys,gzip,hashlib
from tempfile import TemporaryDirectory
from pathlib import Path
from eth_abi import encode
import coverage_decode as C
R=Path(sys.argv[1]);decls,all_decl=C.declarations(R)
ROOT=Path(__file__).resolve().parents[1]
for s in json.loads((ROOT/'data/cohort-sources.json').read_text())['across']['series']:
 sel,item=C.parse(s['signature']);C.METHODS[sel]=item
checks=[]
def call(signature,args,product,kind,address='0x'+'1'*40,name='test',status='0',extra=None):
 sel,(method,types,_) = C.parse(signature)
 s={'address':address,'roles':[{'product':product,'kind':kind,'name':name,**(extra or {})}]}
 r={'input':sel+encode(types,args).hex(),'value':'0','from':'0x'+'2'*40,'isError':status}
 return C.select(r,s,decls,all_decl)
def reject(fn):
 try:fn()
 except (AssertionError,KeyError,ValueError,IndexError):return
 raise AssertionError('Unsafe route was accepted')
# Chain domains and Ethereum token-messenger recipient are independently required.
recipient=bytes.fromhex('28b5a0e9c621a5badaa536219b3a228c8168cf5d')
message=bytearray(148+228);message[:4]=(1).to_bytes(4,'big');message[4:8]=(5).to_bytes(4,'big');message[88:108]=recipient
args=[bytes(message),b'attestation'];addr='0x81d40f21f12a8f0e3252bccb954d722d4c464b64'
assert call('receiveMessage(bytes,bytes)',args,'shared','cctp-receive',addr)[0]=='solana'
reject(lambda:call('receiveMessage(bytes,bytes)',args,'shared','cctp-receive',addr,status='1'))
bad=bytearray(message);bad[8:12]=(5).to_bytes(4,'big');reject(lambda:call('receiveMessage(bytes,bytes)',[bytes(bad),b''],'shared','cctp-receive',addr))
bad=bytearray(message);bad[88:108]=b'\x01'*20;reject(lambda:call('receiveMessage(bytes,bytes)',[bytes(bad),b''],'shared','cctp-receive',addr))
bad=bytearray(message);bad[4:8]=(9999).to_bytes(4,'big');reject(lambda:call('receiveMessage(bytes,bytes)',[bytes(bad),b''],'shared','cctp-receive',addr))
checks.append('CCTP rejects failed, wrong-destination, unknown-source and arbitrary-recipient messages')
reject(lambda:call('depositForBurn(uint256,uint32,bytes32,address)',[1,5,b'\0'*32,'0x'+'2'*40],'shared','cctp-burn','0x28b5a0e9c621a5badaa536219b3a228c8168cf5d',status='1'))
checks.append('A v1 method sent to the v2 CCTP deployment is not attributed from a coincidental domain word')
# Explicit callback data cannot enter Morpho's whole-parent lower bound.
market=('0x'+'3'*40,'0x'+'4'*40,'0x'+'5'*40,'0x'+'6'*40,10**18)
sig=f'supply({C.MARKET},uint256,uint256,address,bytes)';args=[market,1,0,'0x'+'7'*40,b'']
assert call(sig,args,'morpho','morpho')[0]=='morpho'
reject(lambda:call(sig,[*args[:-1],b'callback'],'morpho','morpho'))
checks.append('Morpho empty-callback supply accepted; callback-bearing supply excluded')
# Third-party token approvals are outside protocol-token transfer populations.
assert call('transfer(address,uint256)',['0x'+'2'*40,1],'ethena','ethena',address='0x'+'8'*40,name='USDe')[1]=='token_activity'
reject(lambda:call('permit(address,address,uint256,uint256,uint8,bytes32,bytes32)',['0x'+'2'*40,'0x'+'3'*40,1,1,27,b'\0'*32,b'\0'*32],'ethena','ethena',address='0x'+'8'*40,name='USDe'))
checks.append('Protocol token transfers included without importing unrelated spender authorizations')
# DLN Ethereum fills require ERC20 and no external-call payload.
order=[1,b'a',7565164,b'token',1,1,b'\x01'*20,1,b'\x02'*20,b'',b'',b'',b'',b'']
sig=f'fulfillOrder({C.ORDER},uint256,bytes32,bytes,address)'
assert call(sig,[order,1,b'\0'*32,b'','0x'+'2'*40],'shared','dln-destination',address='0x'+'9'*40)[0]=='solana'
for change in [{6:b'\0'*20},{13:b'arbitrary call'},{5:56}]:
 bad=list(order)
 for i,v in change.items():bad[i]=v
 reject(lambda:call(sig,[bad,1,b'\0'*32,b'','0x'+'2'*40],'shared','dln-destination',address='0x'+'9'*40))
checks.append('DLN excludes native-ETH callbacks, external payloads and non-Ethereum destinations')
# Never spread a shared ZK Gateway transaction across member chains.
ident=C.ZK_IDENTITIES
assert ident['0xe3e310cd8ee0c808794810ab50fe4bccc5c7d89e']=='grvt'
assert ident[325]=='grvt' and all(v in {'zksync2','abstract','adi','grvt','lens','sophon','zkcandy'} for v in ident.values())
checks.append('ZK identities bind reviewed mainnet addresses and IDs; no Gateway allocation')
# Inbox activity requires both destination cohort and its verified sender.
s={'address':'0x'+'a'*40,'roles':[{'product':'base','kind':'batch','name':'BatchInbox','senders':['0x'+'2'*40]}]}
r={'input':'0x','value':'0','from':'0x'+'2'*40,'isError':'0'}
assert C.select(r,s,decls,all_decl)[0]=='base'
reject(lambda:C.select({**r,'from':'0x'+'3'*40},s,decls,all_decl))
checks.append('Dedicated inbox sender constraint excludes unrelated transfers')
if len(sys.argv)<3:sys.argv.append(str(R))
import classify_coverage as classifier
with TemporaryDirectory() as directory:
 previous=classifier.R;classifier.R=Path(directory)
 rows=[{'hash':'first','input':'0x12345678abcdef'},{'hash':'second','input':'0xabcdef010203'}]
 pages=[]
 for n,items in enumerate([rows,[rows[1]]]):
  raw=json.dumps({'result':items}).encode();path=Path(directory)/f'{n}.json.gz';path.write_bytes(gzip.compress(raw))
  pages.append({'file':path.name,'rows':len(items),'sha256_uncompressed':hashlib.sha256(raw).hexdigest()})
 manifest={'calldata_in_pages':True,'pages':pages,'transactions':2}
 assert list(classifier.source_rows(manifest,Path(directory)/'unused'))==rows
 path.write_bytes(gzip.compress(b'changed'))
 reject(lambda:list(classifier.source_rows(manifest,Path(directory)/'unused')))
 classifier.R=previous
checks.append('Referenced raw calldata is complete, hash-checked and deduplicated before classification')
print(json.dumps({'passed':True,'scenarios':checks}))
