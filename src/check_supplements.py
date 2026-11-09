"""Legacy approval metadata must decode, while malformed or wrong routes fail."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import sys

with TemporaryDirectory() as temporary:
    sys.argv = ['check', temporary, temporary]
    import verify_refresh as verifier
    token, spender, other = ('0x' + char * 40 for char in ['1', '2', '3'])
    rows = []
    for index, data in enumerate([
            '095ea7b3' + '0' * 24 + spender[2:] + format(123, '064x'),
            '095ea7b3' + '0' * 24 + other[2:] + format(123, '064x'),
            '095ea7b3' + '0' * 24 + spender[2:]]):
        rows.append({'hash': '0x' + format(index, '064x'), 'block_id': 1,
                     'date': '2026-11-08', 'time': '2026-11-08 00:00:00',
                     'failed': False, 'sender': other, 'recipient': token,
                     'gas_used': 45000, 'input_hex': data, 'value': 0})
    source = {'source_id': 'legacy-approval', 'group': 'approvals',
              'product': 'test', 'spender': spender, 'tokens': [token],
              'url': 'https://api.blockchair.com/ethereum/transactions?q=test',
              'tx_count': 3, 'file': 'aggregate.json'}
    Path(temporary, 'aggregate.json').write_text(json.dumps({'data': [
        {'date': '2026-11-08', 'count()': 3, 'sum(gas_used)': 135000}]}))
    response = {'data': rows, 'context': {'total_rows': 3}}
    with patch.object(verifier, 'fetch', return_value=(response, {})) as transport:
        report = verifier.supplement(source)
        assert transport.call_count == 1 and report['daily_count_and_gas_match']
        assert report['accepted'] == 1 and len(report['excluded']) == 2
    for invalid in [{**source, 'tokens': []}, {**source, 'pattern': 'wrong'}]:
        with patch.object(verifier, 'fetch') as transport:
            try:
                verifier.supplement(invalid)
            except AssertionError:
                pass
            else:
                raise AssertionError('Invalid approval configuration accepted')
            assert transport.call_count == 0
print('Passed legacy approval decoding, wrong-route and malformed-calldata rejection, and configuration-stop checks')
