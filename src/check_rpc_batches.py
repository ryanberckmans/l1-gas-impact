"""Reject ambiguous or failed RPC batches before publishing canonical caches."""
from prefetch_canonical_rpc import checked_batch

requests = [{'id': 1, 'method': 'eth_getTransactionReceipt'},
            {'id': 2, 'method': 'eth_getTransactionByHash'}]
valid = [{'jsonrpc': '2.0', 'id': 2, 'result': {}},
         {'jsonrpc': '2.0', 'id': 1, 'result': '0x1'}]
assert checked_batch(requests, valid)[1]['result'] == '0x1'
invalid = [valid[:1], [valid[0], valid[0]],
           [{**valid[0], 'id': 3}, valid[1]],
           [{**valid[0], 'error': {}}, valid[1]],
           [{**valid[0], 'result': None}, valid[1]], {'result': valid}]
for responses in invalid:
    try:
        checked_batch(requests, responses, allow_missing_receipts=True)
    except AssertionError:
        pass
    else:
        raise AssertionError('Invalid batch accepted')
missing = [valid[0], {**valid[1], 'result': None}]
assert checked_batch(requests, missing, allow_missing_receipts=True)[1]['result'] is None
try:
    checked_batch(requests, missing)
except AssertionError:
    pass
else:
    raise AssertionError('Missing receipt accepted in strict mode')
print('Passed 8 RPC batch validation scenarios')
