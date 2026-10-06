import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from tracker_store import load_tracker

PROV = {'inputs': {'history': {'generated_at': '2026-10-05T10:00:00Z', 'sha256': 'a' * 64}}, 'model_source_sha256': 'c' * 64}
NODE = shutil.which('node')

WRITER = """
const {writeTrackerStore}=await import(process.argv[1]);
const rows=Array.from({length:30},(_,i)=>({id:'p'+i,kind:'prediction',observed_at:'2026-10-0'+(1+Math.floor(i/10))+'T10:00:00.000Z',payload:{id:'p'+i,sport:'nfl',probability:.5+i/1000,provenance:JSON.parse(process.argv[3])}}));
rows.push({id:'s1',kind:'settlement',observed_at:'2026-10-09T10:00:00.000Z',payload:{prediction_id:'p1',status:'win'}});
const snapshot={schema_version:1,generated_at:'2026-10-09T12:00:00Z',records:rows,groups:{a:1}};
await writeTrackerStore({dataDir:process.argv[2],snapshot,maxRaw:2500});
process.stdout.write(JSON.stringify(snapshot));
"""


@unittest.skipUnless(NODE, 'node is required to write a fixture store')
class TrackerStoreTests(unittest.TestCase):
    def build(self):
        directory = Path(tempfile.mkdtemp())
        url = (ROOT / 'scripts' / 'tracker_store.mjs').as_uri()
        out = subprocess.run([NODE, '--input-type=module', '-e', WRITER, url, str(directory), json.dumps(PROV)],
                             capture_output=True, text=True, check=True, cwd=str(ROOT))
        return directory, json.loads(out.stdout)

    def test_python_reads_what_node_wrote_identically(self):
        directory, original = self.build()
        loaded = load_tracker(directory)
        self.assertEqual(loaded, original)
        self.assertEqual(list(loaded.keys()), list(original.keys()))
        self.assertEqual(json.dumps(loaded['records'], separators=(',', ':')), json.dumps(original['records'], separators=(',', ':')))
        manifest = json.loads((directory / 'public_tracker' / 'manifest.json').read_text(encoding='utf-8'))
        self.assertGreater(len(manifest['segments']), 1)

    def test_expanded_records_do_not_share_mutable_subtrees(self):
        directory, _ = self.build()
        loaded = load_tracker(directory)
        loaded['records'][0]['payload']['provenance']['model_source_sha256'] = 'changed'
        self.assertEqual(loaded['records'][1]['payload']['provenance']['model_source_sha256'], 'c' * 64)

    def test_tampered_or_missing_segment_raises(self):
        directory, _ = self.build()
        segment = directory / 'public_tracker' / 'segments' / 'seg-000001.json'
        original = segment.read_text(encoding='utf-8')
        segment.write_text(original.replace('"sport":"nfl"', '"sport":"ncaa"'), encoding='utf-8')
        with self.assertRaises(ValueError):
            load_tracker(directory)
        segment.unlink()
        with self.assertRaises(FileNotFoundError):
            load_tracker(directory)

    def test_legacy_file_tombstone_and_corruption(self):
        legacy = Path(tempfile.mkdtemp())
        (legacy / 'public_tracker.json').write_text(json.dumps({'schema_version': 1, 'records': [{'id': 'x'}]}), encoding='utf-8')
        self.assertEqual(load_tracker(legacy)['records'], [{'id': 'x'}])
        (legacy / 'public_tracker.json').write_text(json.dumps({'schema_version': 2, 'moved_to': 'public_tracker/manifest.json'}), encoding='utf-8')
        with self.assertRaises(ValueError):
            load_tracker(legacy)
        (legacy / 'public_tracker.json').write_text('{"schema_version":1,"records":[{"id":', encoding='utf-8')
        with self.assertRaises(ValueError):
            load_tracker(legacy)


if __name__ == '__main__':
    unittest.main()
