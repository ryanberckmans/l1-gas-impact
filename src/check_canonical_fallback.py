"""An indexed receipt exception must preserve independent gas and identity checks."""
from pathlib import Path
from tempfile import TemporaryDirectory
import copy
import hashlib
import json
import sys

with TemporaryDirectory() as directory:
    sys.argv = ['check', directory, directory]
    import verify_refresh as verifier
    root = Path(directory)
    h, block = '0x' + 'a' * 64, '0x' + 'b' * 64
    sender, recipient = '0x' + '1' * 40, '0x' + '2' * 40
    base = {
        'routescan': {'id': h, 'chainId': '1', 'blockNumber': 100, 'blockHash': block,
                      'from': sender, 'to': recipient, 'status': True, 'gasUsed': '21000', 'value': '0'},
        'blockchair': {'data': [{'hash': h, 'block_id': 100, 'sender': sender, 'recipient': recipient,
                                 'failed': False, 'gas_used': 21000, 'value': '0', 'input_hex': ''}]},
        'rpc_failure': {'status': '0', 'message': 'An error occurred'}}
    def fixture(values):
        manifest = {'hash': h, 'method': 'independent-indexed-receipts'}
        for name, value in values.items():
            payload = json.dumps(value).encode(); (root / (name + '.json')).write_bytes(payload)
            manifest[name] = {'file': name + '.json', 'sha256': hashlib.sha256(payload).hexdigest()}
        return manifest
    result = verifier.indexed_receipt(h, fixture(base))
    assert result['gasUsed'] == '0x5208' and result['blockHash'] == block
    for key, value in [('hash', '0x' + 'c' * 64), ('block_id', 101), ('sender', recipient),
                       ('failed', True), ('gas_used', 22000), ('value', '1'), ('input_hex', '00')]:
        changed = copy.deepcopy(base); changed['blockchair']['data'][0][key] = value
        try:
            verifier.indexed_receipt(h, fixture(changed))
        except AssertionError:
            pass
        else:
            raise AssertionError('Accepted conflicting ' + key)
    manifest = fixture(base); (root / 'routescan.json').write_text('{}')
    try:
        verifier.indexed_receipt(h, manifest)
    except AssertionError:
        pass
    else:
        raise AssertionError('Accepted changed evidence bytes')
from resolve_coverage_disputes import explicit_absence
assert explicit_absence({'jsonrpc': '2.0', 'id': 1, 'result': None})
for response in [{}, {'jsonrpc': '2.0', 'id': 1},
                 {'jsonrpc': '2.0', 'id': 1, 'result': {'hash': h}},
                 {'status': '0', 'message': 'An error occurred', 'result': None},
                 {'jsonrpc': '2.0', 'id': 1, 'result': None,
                  'error': {'code': -32000, 'message': 'Backend unavailable'}}]:
    assert not explicit_absence(response), 'An error or incomplete response cannot prove absence'
print('Passed indexed receipt agreement, eight conflicting/tampered evidence cases, and explicit-absence boundaries')
