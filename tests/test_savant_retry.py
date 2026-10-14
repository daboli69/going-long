import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from extract_savant import public_get, failure_reason


class SavantRetryTests(unittest.TestCase):
    def response(self, status):
        response = Mock(status_code=status, headers={'Retry-After': '3'})
        if status >= 400:
            response.raise_for_status.side_effect = requests.HTTPError(response=response)
        return response

    def test_transient_http_failure_recovers(self):
        healthy = self.response(200)
        with patch('extract_savant.requests.get', side_effect=[self.response(503), healthy]) as get, patch('extract_savant.time.sleep') as sleep:
            self.assertIs(public_get('https://nflsavant.com/api/league', timeout=30), healthy)
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(3)

    def test_permanent_failure_is_not_retried(self):
        with patch('extract_savant.requests.get', return_value=self.response(404)) as get, patch('extract_savant.time.sleep') as sleep:
            with self.assertRaises(requests.HTTPError) as error:
                public_get('https://nflsavant.com/api/league')
        self.assertEqual(get.call_count, 1)
        sleep.assert_not_called()
        self.assertEqual(failure_reason(error.exception), 'HTTPError HTTP 404')

    def test_transport_retry_is_bounded_and_failure_is_not_hidden(self):
        with patch('extract_savant.requests.get', side_effect=requests.Timeout) as get, patch('extract_savant.time.sleep'):
            with self.assertRaises(requests.Timeout):
                public_get('https://nflsavant.com/api/league')
        self.assertEqual(get.call_count, 2)


if __name__ == '__main__':
    unittest.main()
