"""Reviewed method decoding for the expanded receipt cohorts.

No address alone authorizes a shared bridge transaction. Unknown methods and
arbitrary L1 callbacks fail closed. ABI declarations are retained with evidence.
"""
import json,re
from eth_utils import keccak
from eth_abi import decode,encode

def split_types(s):
    result=[];depth=0;start=0
    for i,c in enumerate(s):
        if c=='(':depth+=1
        elif c==')':depth-=1
        elif c==',' and depth==0:result.append(s[start:i].strip());start=i+1
    if s[start:].strip():result.append(s[start:].strip())
    return result

def close(s,start=0):
    depth=0
    for i in range(start,len(s)):
        if s[i]=='(':depth+=1
        elif s[i]==')':
            depth-=1
            if depth==0:return i
    raise ValueError('Unbalanced ABI')

def abi_type(s):
    s=s.strip()
    if s.startswith('tuple'):s=s[5:]
    if s.startswith('('):
        end=close(s);suffix=re.match(r'(\[[0-9]*\])*',s[end+1:])[0]
        return '('+','.join(abi_type(x) for x in split_types(s[1:end]))+')'+suffix
    t=s.split()[0]
    return re.sub(r'^uint(?=\[|$)','uint256',re.sub(r'^int(?=\[|$)','int256',t))

def parse(s):
    s=s.removeprefix('function ').strip();i=s.index('(');end=close(s,i)
    name=s[:i].strip();assert re.fullmatch(r'\w+',name)
    types=[abi_type(x) for x in split_types(s[i+1:end])]
    sig=name+'('+','.join(types)+')'
    return '0x'+keccak(text=sig)[:4].hex(),(name,types,sig)

def checked(types,raw):
    values=decode(types,raw)
    assert raw.startswith(encode(types,values)),'Noncanonical ABI'
    return values

def declarations(root):
    global ZK_IDENTITIES
    identities=json.loads((root/'zk-chain-identities.json').read_text())
    ZK_IDENTITIES={int(k) if k.isdigit() else k:v for k,v in identities.items()}
    result={};sources={}
    for f in sorted((root/'discovery').glob('*-discovered.json')):
        methods={}
        for address,abi in json.loads(f.read_text())['abis'].items():
            for s in abi:
                if not s.startswith('function '):continue
                selector,item=parse(s);methods[selector]=item
        ts=root/'discovery'/(f.stem.replace('-discovered','')+'-'+f.stem.replace('-discovered','')+'.ts')
        if ts.exists():
            for s in re.findall(r'functionSignature:\s*[\'"`]([^\'"`]+)[\'"`]',ts.read_text()):
                selector,item=parse(s);methods[selector]=item
        result[f.name]=methods
        sources.update(methods)
    def json_type(a):
        return '('+','.join(json_type(x) for x in a['components'])+')'+a['type'][5:] if a['type'].startswith('tuple') else a['type']
    for f in sorted((root/'verified-abis').glob('*.json')):
        methods={}
        for source in json.loads(f.read_text()):
            for a in source['abi']:
                if a.get('type')!='function':continue
                selector,item=parse(a['name']+'('+','.join(json_type(x) for x in a['inputs'])+')');methods[selector]=item
        result[f.stem]=methods
    return result,sources

CCTP={1:'avalanche',2:'op',3:'arbitrum',4:'noble',5:'solana',6:'base',7:'polygon',8:'sui',9:'aptos',10:'unichain',11:'linea',12:'codex',13:'sonic',14:'worldchain',15:'monad',16:'sei',17:'bsc',18:'xdc',19:'hyperliquid',21:'ink',22:'plume',25:'starknet',26:'arc',27:'stellar',28:'edge',29:'injective',30:'morph',31:'pharos',32:'cronos',33:'plasma',37:'xlayer'}
EVM={10:'op',56:'bsc',100:'gnosis',137:'polygon',250:'fantom',324:'zksync2',1088:'metis',1101:'polygonzkevm',5000:'mantle',8453:'base',42161:'arbitrum',42170:'nova',42220:'celo',43114:'avalanche',59144:'linea',534352:'scroll',81457:'blast',34443:'mode',7777777:'zora',167000:'taiko',111188:'real',7565164:'solana',34268394551451:'solana',999:'hyperliquid',480:'worldchain',130:'unichain',57073:'ink',9745:'plasma',143:'monad',146:'sonic',1868:'soneium',80094:'berachain',2741:'abstract',747474:'katana'}
# Mainnet route IDs from Across's published chains-and-contracts registry.
EVM.update({4663:'robinhood',5042:'arc',4217:'tempo',728126428:'tron',4326:'megaeth'})
ZK_IDENTITIES={}
WORM={1:'solana',4:'bsc',5:'polygon',6:'avalanche',8:'algorand',10:'fantom',13:'kaia',14:'celo',15:'near',16:'moonbeam',18:'terra2',19:'injective',20:'osmosis',21:'sui',22:'aptos',23:'arbitrum',24:'op',25:'gnosis',29:'bitcoin',30:'base',31:'filecoin',32:'sei',33:'rootstock',34:'scroll',35:'mantle',36:'blast',37:'xlayer',38:'linea',39:'berachain',40:'sei',41:'eclipse',42:'bob',43:'snaxchain',44:'unichain',45:'worldchain',46:'ink',47:'hyperliquid',48:'monad',49:'movement',50:'mezo',51:'fogo',52:'sonic',53:'converge',54:'codex',55:'plume',56:'aztec',57:'xrplevm',58:'plasma',59:'creditcoin',60:'stacks',61:'stellar',62:'ton',63:'moca',64:'megaeth',65:'dogecoin',66:'xrpl',67:'zerogravity',68:'tempo',69:'nexus',70:'tron',71:'arc',72:'robinhood',73:'hydration',4009:'noble',65000:'hyperliquid'}
ORDER='(uint64,bytes,uint256,bytes,uint256,uint256,bytes,uint256,bytes,bytes,bytes,bytes,bytes,bytes)'
CREATION='(address,uint256,bytes,uint256,uint256,bytes,address,bytes,bytes,bytes,bytes)'
MARKET='(address,address,address,address,uint256)'
STANDARD=[
'transfer(address,uint256)','transferFrom(address,address,uint256)','permit(address,address,uint256,uint256,uint8,bytes32,bytes32)',
'deposit(uint256,address)','mint(uint256,address)','withdraw(uint256,address,address)','redeem(uint256,address,address)',
'submit(address)','wrap(uint256)','unwrap(uint256)','deposit()','deposit(address)','deposit(uint256,address,uint16)',
'supply(address,uint256,address,uint16)','supplyWithPermit(address,uint256,address,uint16,uint256,uint8,bytes32,bytes32)',
'deposit(address,uint256,address,uint16)','withdraw(address,uint256,address)','borrow(address,uint256,uint256,uint16,address)',
'repay(address,uint256,uint256,address)','repayWithATokens(address,uint256,uint256)','repayWithPermit(address,uint256,uint256,address,uint256,uint8,bytes32,bytes32)',
'setUserEMode(uint8)','setUserUseReserveAsCollateral(address,bool)','swapBorrowRateMode(address,uint256)','rebalanceStableBorrowRate(address,address)',
'liquidationCall(address,address,address,uint256,bool)',
'supply(address,uint256)','supplyTo(address,address,uint256)','supplyFrom(address,address,address,uint256)',
'withdraw(address,uint256)','withdrawTo(address,address,uint256)','withdrawFrom(address,address,address,uint256)',
'absorb(address,address[])','buyCollateral(address,uint256,uint256,address)','allow(address,bool)',
f'supply({MARKET},uint256,uint256,address,bytes)',f'supplyCollateral({MARKET},uint256,address,bytes)',
f'repay({MARKET},uint256,uint256,address,bytes)',f'borrow({MARKET},uint256,uint256,address,address)',
f'withdraw({MARKET},uint256,uint256,address,address)',f'withdrawCollateral({MARKET},uint256,address,address)',
f'liquidate({MARKET},address,uint256,uint256,bytes)',f'createMarket({MARKET})','setAuthorization(address,bool)',
'requestWithdrawals(uint256[],address)','requestWithdrawalsWstETH(uint256[],address)',
'requestWithdrawalsWithPermit(uint256[],address,(uint256,uint256,uint8,bytes32,bytes32))',
'requestWithdrawalsWstETHWithPermit(uint256[],address,(uint256,uint256,uint8,bytes32,bytes32))',
'submitReport(uint256,bytes32,uint256)','submitReportData((uint256,uint256,uint256,uint256[],uint256[],uint256,uint256,uint256,uint256[],uint256,bool,uint256,uint256,bytes32,uint256),uint256)',
'cooldownAssets(uint256)','cooldownShares(uint256)','unstake(address)','daiToUsds(address,uint256)','usdsToDai(address,uint256)',
'mkrToSky(address,uint256)','skyToMkr(address,uint256)','join(address,uint256)','exit(address,uint256)','exitAll(address)',
'drip()','drip(bytes32)','requestWithdraw(address,uint256)','requestWithdrawWithPermit(address,uint256,(uint256,uint256,uint8,bytes32,bytes32))',
'submitCheckpoint(bytes,uint256[3][])','submitCheckpoint(bytes,bytes)','stakeFor(address,uint256,uint256,bool,bytes)',
'restake(uint256,uint256,bool)','unstake(uint256)','unstakeClaim(uint256)','withdrawRewards(uint256)',
'depositFor(address,address,bytes)','syncState(address,bytes)',
'depositForBurn(uint256,uint32,bytes32,address)','depositForBurnWithCaller(uint256,uint32,bytes32,address,bytes32)',
'depositForBurn(uint256,uint32,bytes32,address,bytes32,uint256,uint32)','depositForBurnWithHook(uint256,uint32,bytes32,address,bytes32,uint256,uint32,bytes)','receiveMessage(bytes,bytes)',
'transferTokens(address,uint256,uint16,bytes32,uint256,uint32)','transferTokensWithPayload(address,uint256,uint16,bytes32,uint32,bytes)',
'wrapAndTransferETH(uint16,bytes32,uint256,uint32)','wrapAndTransferETHWithPayload(uint16,bytes32,uint32,bytes)',
*[n+'(bytes)' for n in ['completeTransfer','completeTransferWithPayload','createWrapped','updateWrapped']],
f'createOrder({CREATION},bytes,uint32,bytes)',f'createSaltedOrder({CREATION},uint64,bytes,uint32,bytes,bytes)',
f'fulfillOrder({ORDER},uint256,bytes32,bytes,address)',f'fulfillOrder({ORDER},uint256,bytes32,bytes,address,address)',
f'sendBatchSolanaUnlock({ORDER}[],bytes32,uint256,uint64,uint64)',f'sendSolanaUnlock({ORDER},bytes32,uint256,uint64,uint64)',
f'sendSolanaOrderCancel({ORDER},bytes32,uint256,uint64,uint64)',f'patchOrderTake({ORDER},uint256)',
]
for n in [2,3,4]:
    STANDARD += [f'add_liquidity(uint256[{n}],uint256)',f'add_liquidity(uint256[{n}],uint256,bool)',f'add_liquidity(uint256[{n}],uint256,address)',f'remove_liquidity(uint256,uint256[{n}])',f'remove_liquidity_imbalance(uint256[{n}],uint256)']
for integer in ['int128','uint256']:
    for suffix in ['',',address',',bool',',bool,address']:
        STANDARD += [f'exchange({integer},{integer},uint256,uint256{suffix})',f'remove_liquidity_one_coin(uint256,{integer},uint256{suffix})']

METHODS=dict(parse(s) for s in STANDARD)
OPS={'updateState','updateStateKzgDA','updateStateWithOnchainData','commitBatch','commitBatches','commitBatchesWithBlobProof','finalizeBatchWithProof','finalizeBundleWithProof','finalizeBundlePostEuclidV2','commitAndFinalizeBatch','prove','propose','proposeBatch','proposeBatches','proveBatch','proveBatches','proveBlock','proveBlocks','proposeBlock','proposeBlockV2','proposeBlocksV2','saveForcedInclusion','proposeL2Output','checkpointBlockHash','appendStateBatch','appendStateBatchByChainId','create','addSequencerL2BatchFromOrigin','addSequencerL2BatchFromBlobs','addSequencerL2BatchFromOriginDelayProof','addSequencerL2BatchFromBlobsDelayProof','addSequencerL2Batch','forceInclusion','submitBlobs','submitData','finalizeBlocks','finalizeBlocksWithProof','commitBatchesSharedBridge','proveBatchesSharedBridge','executeBatchesSharedBridge','precommitSharedBridge','revertBatchesSharedBridge'}
OPS.update({'submitEpochRootProof','commitBatchWithProof','commitState','finalizeBatch','challengeState','proveState','revertBatch'})
BRIDGE={'deposit','depositETH','depositETHTo','depositERC20','depositERC20To','bridgeETH','bridgeETHTo','bridgeERC20','bridgeERC20To','bridgeERC721','bridgeERC721To','depositERC721','depositERC721To','depositMNT','depositMNTTo','bridgeToken','depositTransaction','sendMessage','sendMessageToL2','createRetryableTicket','unsafeCreateRetryableTicket','depositEth','outboundTransfer','outboundTransferCustomRefund','requestL2Transaction','sendToken','depositETHToByChainId','depositERC20ToByChainId'}
APP={'aave':{'supply','supplyWithPermit','deposit','withdraw','borrow','repay','repayWithATokens','repayWithPermit','setUserEMode','setUserUseReserveAsCollateral','swapBorrowRateMode','rebalanceStableBorrowRate','liquidationCall'},'compound':{'supply','supplyTo','supplyFrom','withdraw','withdrawTo','withdrawFrom','absorb','buyCollateral','allow'},'morpho':{'supply','supplyCollateral','repay','borrow','withdraw','withdrawCollateral','liquidate','createMarket','setAuthorization'},'lido':{'submit','wrap','unwrap','requestWithdrawals','requestWithdrawalsWstETH','requestWithdrawalsWithPermit','requestWithdrawalsWstETHWithPermit','submitReport','submitReportData'},'etherfi':{'deposit','wrap','unwrap','requestWithdraw','requestWithdrawWithPermit'},'ethena':{'deposit','mint','withdraw','redeem','cooldownAssets','cooldownShares','unstake'},'sky':{'deposit','mint','withdraw','redeem','daiToUsds','usdsToDai','mkrToSky','skyToMkr','join','exit','exitAll','drip'},'curve':{'exchange','add_liquidity','remove_liquidity','remove_liquidity_one_coin','remove_liquidity_imbalance'}}

METHOD_CACHE={}
def select(r,s,decls,all_decl):
    selector=r['input'][:10];raw=bytes.fromhex(r['input'][10:]);role=s['roles'][0];kind=role['kind'];p=role['product']
    if kind=='batch':
        assert r['from'].lower() in role['senders'],'Not the exclusive batch sender'
        return p,'batch_submission','dedicated inbox and sender'
    if r['input']=='0x':
        assert int(r['value'])>0 and ((kind in ['portal','bridge'] and role['name'] in ['OptimismPortal','OptimismPortal2','L1StandardBridge','L1BlastBridge']) or (p=='lido' and role['name']=='stETH') or (p=='etherfi' and role['name']=='LiquidityPool')),'Unreviewed receive function'
        return p,'staking' if p in ['lido','etherfi'] else 'deposits','dedicated deposit receive function'
    if s['address'] not in METHOD_CACHE:
        methods={**METHODS,**decls.get(role.get('discovery'),{})}
        if kind=='zk-validator':methods.update(all_decl)
        # Full ABI retrieval is bound to the specific protocol address.
        methods.update(decls.get(s['address'],{}));METHOD_CACHE[s['address']]=methods
    methods=METHOD_CACHE[s['address']]
    assert selector in methods,'Unreviewed method'
    name,types,signature=methods[selector]
    # Successful closed settlement methods cannot change their chain attribution
    # through opaque proof bytes. The EVM has already accepted their ABI. Decode
    # only attribution-bearing fields rather than materializing huge proof arrays.
    closed={'updateState','updateStateKzgDA','updateStateWithOnchainData','propose','submitEpochRootProof','commitBatch','commitBatches','commitBatchesWithBlobProof','commitBatchWithProof','commitState','finalizeBatch','finalizeBatchWithProof','finalizeBundleWithProof','finalizeBundlePostEuclidV2','commitAndFinalizeBatch','submitBlobs','submitData','finalizeBlocks','finalizeBlocksWithProof'}
    if r['isError']=='0' and kind in ['operations','linea'] and name in closed:
        return p,'settlement',signature
    if r['isError']=='0' and kind=='zk-validator':
        assert name in OPS and name.endswith('SharedBridge')
        assert types[0] in ['uint256','address']
        identity=checked([types[0]],raw[:32])[0]
        return ZK_IDENTITIES[identity],'settlement',signature
    a=checked(types,raw)
    if kind.startswith('cctp'):
        if s['address']=='0xbd3fa81b58ba92a82136038b25adec7066af3155':
            assert selector in {'0x6fd3504e','0xf856ddb6'},'Method not implemented by this CCTP deployment'
        elif s['address']=='0x28b5a0e9c621a5badaa536219b3a228c8168cf5d':
            assert selector in {'0x8e0250ee','0x779b432d'},'Method not implemented by this CCTP deployment'
        if name=='receiveMessage':
            assert r['isError']=='0';m=a[0];assert len(m)>=116 and int.from_bytes(m[8:12],'big')==0
            version=int.from_bytes(m[:4],'big');assert version in [0,1]
            assert version==(1 if s['address']=='0x81d40f21f12a8f0e3252bccb954d722d4c464b64' else 0)
            off=52 if version==0 else 76
            assert '0x'+m[off+12:off+32].hex()==('0xbd3fa81b58ba92a82136038b25adec7066af3155' if version==0 else '0x28b5a0e9c621a5badaa536219b3a228c8168cf5d'),'Unreviewed incoming message recipient'
            p=CCTP[int.from_bytes(m[4:8],'big')]
        else:
            assert name in ['depositForBurn','depositForBurnWithCaller','depositForBurnWithHook','depositForBurnWithFees','depositForBurnWithHookAndFees'];p=CCTP[a[1]]
        return p,'cctp_bridge',signature
    if kind=='across':
        assert name in ['depositV3','deposit','depositNow','depositV3Now','unsafeDeposit'];p=EVM[a[3] if len(types)==8 else a[6]]
        return p,'across_bridge',signature
    if kind=='wormhole':
        if name.startswith('transferTokens'):chain=a[2]
        elif name.startswith('wrapAndTransferETH'):chain=a[0]
        else:
            assert name in ['completeTransfer','completeTransferWithPayload','createWrapped','updateWrapped'] and r['isError']=='0'
            v=a[0];assert len(v)>6 and v[0]==1;body=v[6+66*v[5]:];assert len(body)>51
            chain=int.from_bytes(body[8:10],'big');payload=body[51:]
            if name in ['createWrapped','updateWrapped']:assert len(payload)==100 and payload[0]==2 and int.from_bytes(payload[33:35],'big')==chain
            else:assert payload[0] in [1,3] and int.from_bytes(payload[99:101],'big')==2
        return WORM[chain],'wormhole_bridge',signature
    if kind=='dln-source':
        assert name in ['createOrder','createSaltedOrder'];return EVM[a[0][4]],'dln_bridge',signature
    if kind=='dln-destination':
        if name=='fulfillOrder':
            order=a[0];assert order[5]==1 and order[13]==b'' and order[6]!=b'\0'*20,'Unverified external or native-ETH callback'
            return EVM[order[2]],'dln_bridge',signature
        assert name in ['sendSolanaUnlock','sendBatchSolanaUnlock','sendSolanaOrderCancel','patchOrderTake']
        orders=a[0] if name=='sendBatchSolanaUnlock' else [a[0]]
        assert orders and all(o[2]==orders[0][2] and o[5]==1 for o in orders),'Mixed chain batch'
        return EVM[orders[0][2]],'dln_bridge',signature
    if kind=='zk-validator':
        assert name in OPS and name.endswith('SharedBridge')
        return ZK_IDENTITIES[a[0]],'settlement',signature
    if kind in APP:
        if name in ['transfer','transferFrom'] and kind in ['lido','etherfi','ethena','sky']:
            assert role['name'] in ['stETH','wstETH','eETH','weETH','USDe','sUSDe','ENA','sENA','MCD_DAI','USDS','SUSDS','SDAI','SKY'],'Not a protocol token'
            return p,'token_activity',signature
        assert name in APP[kind],'Unreviewed or callback-capable protocol method'
        if kind=='morpho' and name in ['supply','supplyCollateral','repay','liquidate']:assert a[-1]==b'','Nonempty Morpho callback'
        if kind=='curve':assert all(v is False for t,v in zip(types,a) if t=='bool'),'Native ETH callbacks excluded'
        # Direct token transfers are above; permit/approve to an unrelated spender is excluded.
        return p,'lending' if p in ['aave','compound','morpho'] else 'defi' if p=='curve' else 'staking',signature
    if kind=='polygon':
        allowed={'RootChainProxy':{'submitCheckpoint'},'StakeManagerProxy':{'stakeFor','restake','unstake','unstakeClaim','withdrawRewards'},'RootChainManagerProxy':{'depositFor'},'StateSender':set(),'ERC20PredicateProxy':set()}
        assert name in allowed.get(role['name'],set()),'Unreviewed Polygon method or arbitrary state message'
        return p,'settlement' if name=='submitCheckpoint' else 'deposits' if name=='depositFor' else 'staking',signature
    if p=='aztecnetwork':
        if name in {'deposit','initiateWithdraw','finalizeWithdraw','flushEntryQueue','claimProverRewards','claimSequencerRewards','checkpointRandao','prune','setupEpoch','updateL1GasFeeOracle','invalidateBadAttestation','invalidateInsufficientAttestations'} and role['name'].startswith('Rollup'):
            return p,'operations',signature
        if name in {'signal','signalWithSig','submitRoundWinner','vote'} and role['name'] in {'GovernanceProposer','SlashingProposer'}:
            return p,'governance',signature
        if name in {'sendL2Message','depositToAztecPublic'} and kind=='bridge':return p,'deposits',signature
    if name in OPS and kind in ['operations','linea']:
        if name.endswith('ByChainId'):assert a[0]==1088,'Other Metis instance'
        return p,'settlement',signature
    if name=='proveWithdrawalTransaction' and kind=='portal':return p,'withdrawal_proofs',signature
    if name in BRIDGE and kind in ['bridge','portal','messenger','operations','linea']:
        if name.endswith('ByChainId'):assert a[0]==1088,'Other Metis instance'
        if name=='sendToken':assert a[0][0]==167000,'Other Taiko bridge destination'
        return p,'deposits',signature
    # Starkgate ERC20 withdrawals return tokens; native ETH receivers may execute arbitrary code.
    if p=='starknet' and kind=='bridge' and name=='withdraw' and role['name'] not in ['ETHBridge','MultiBridge']:
        return p,'withdrawals',signature
    raise AssertionError('Unreviewed method or arbitrary L1 execution')
