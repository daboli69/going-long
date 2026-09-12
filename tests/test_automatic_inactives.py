import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import requests
from topdown.inactives import parse_official_report,update_inactives,fetch
from topdown.model import stamp,inactive_gate,player_key
from topdown.journal import Journal

URL='https://www.nfl.com/news/test-inactives'
EVENT=dict(event='test',home='Los Angeles Rams',away='San Francisco 49ers',kickoff='2026-09-13T17:00:00Z')
NOW=stamp('2026-09-13T15:40:00Z')


def page(published='2026-09-13T15:35:00Z',second=True):
    article={'@type':'NewsArticle','headline':'Official game inactives','datePublished':published}
    return '<script type="application/ld+json">'+json.dumps(article)+'</script><div class="story-part-rich-text-editor-wrapper"><h3></h3></div><div class="story-part-rich-text-editor-wrapper"><p>WHEN: 1 p.m. ET</p><h3>NINERS</h3><ul><li>WR Test Player Jr.</li></ul>'+('<h3>RAMS</h3><ul><li>QB Other Player (emergency third QB)</li></ul>' if second else '')+'</div>'


class AutomaticInactivesTests(unittest.TestCase):
    def test_two_complete_lists_clear_only_final_window(self):
        report=parse_official_report(page(),URL,EVENT,NOW)
        self.assertTrue(inactive_gate(report,EVENT,NOW))
        self.assertEqual(report['teams'][1]['inactive_players'],['Other Player'])
        self.assertFalse(inactive_gate(report,EVENT,stamp('2026-09-13T15:00:00Z')))
        self.assertFalse(inactive_gate(report,EVENT,stamp(EVENT['kickoff'])))
        self.assertEqual(player_key('Test Player Jr.'),player_key('Test Player'))
    def test_incomplete_stale_wrong_game_and_injury_articles_fail(self):
        for html,url,event in [(page(second=False),URL,EVENT),(page('2026-09-12T15:35:00Z'),URL,EVENT),(page(),URL,dict(EVENT,away='Atlanta Falcons')),(page().replace('Official game inactives','Injury report'),URL,EVENT),(page(), 'https://example.com/news/inactives',EVENT)]:
            self.assertIsNone(parse_official_report(html,url,event,NOW))
    def test_early_article_can_contain_late_game_lists(self):
        report=parse_official_report(page('2026-09-13T12:00:00Z'),URL,EVENT,NOW)
        self.assertTrue(inactive_gate(report,EVENT,NOW))
        report['teams'][0]['verified_at']='2026-09-13T15:00:00Z'
        self.assertFalse(inactive_gate(report,EVENT,NOW))
    def test_warning_at_75_deduped_and_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal=Journal(Path(tmp)/'db');send=Mock(return_value='discord');empty=lambda e,n:({},['timeout'])
            update_inactives(journal,[EVENT],{},NOW,send,empty);send.assert_not_called()
            late=stamp('2026-09-13T15:45:00Z')
            update_inactives(journal,[EVENT],{},late,send,empty)
            update_inactives(journal,[EVENT],{},late+30,send,empty)
            self.assertEqual(send.call_count,1);self.assertEqual(send.call_args.args[0],'[WARNING] Automated Inactive Feed Failed for San Francisco 49ers at Los Angeles Rams. Manual override required.')
            report=parse_official_report(page(),URL,EVENT,late+60)
            reports,status=update_inactives(journal,[EVENT],{},late+60,send,lambda e,n:({'test':report},[]))
            self.assertEqual(status['state'],'verified');self.assertTrue(inactive_gate(reports['test'],EVENT,late+60));journal.db.close()
    def test_outside_window_no_network_and_timeout_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            j=Journal(Path(tmp)/'db');retrieve=Mock(side_effect=requests.Timeout())
            update_inactives(j,[EVENT],{},NOW-1800,None,retrieve);retrieve.assert_not_called()
            _,status=update_inactives(j,[EVENT],{},NOW,None,retrieve)
            self.assertEqual(status['state'],'awaiting_official_reports');j.db.close()
    def test_http_timeout_retries_and_rate_limit_stops(self):
        response=Mock(status_code=200,url=URL,text='ok');response.raise_for_status.return_value=None
        with patch('topdown.inactives.requests.get',side_effect=[requests.Timeout(),response]) as get,patch('topdown.inactives.time.sleep'):
            self.assertEqual(fetch(URL),'ok');self.assertEqual(get.call_count,2)
        response=Mock(status_code=429);response.raise_for_status.side_effect=requests.HTTPError(response=response)
        with patch('topdown.inactives.requests.get',return_value=response) as get:
            with self.assertRaises(requests.HTTPError):fetch(URL)
            self.assertEqual(get.call_count,1)


if __name__=='__main__':unittest.main()
