import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from lab import overnight as O


class TestOvernight(unittest.TestCase):
    def test_compare_flags_only_real_changes(self):
        b = {"S2": {"p": 0.01, "coef": -0.3}, "carried": {"ES": ["E13"]}}
        a = {"S2": {"p": 0.01 + 1e-9, "coef": -0.25}, "carried": {"ES": ["E13"]}}
        d = O.compare(b, a, ["S2.p", "S2.coef", "carried", "missing.key"])
        self.assertEqual([x["key"] for x in d], ["S2.coef"])

    def test_never_takes_a_first_look(self):
        called = []
        fake = types.SimpleNamespace(run=lambda **k: called.append(1))
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(O, "ARTIFACTS_DIR", Path(d)), mock.patch.object(O, "ROOT", Path(d) / "overnight"), \
                mock.patch.object(O, "STUDIES", [("9.9", "fake", "phase99/results.json", {}, [])]), \
                mock.patch.object(O, "PROSPECTIVE", []), mock.patch("importlib.import_module", return_value=fake):
            r = O.run(log=lambda m: None)
            self.assertEqual(called, [])
            self.assertTrue(r["studies"][0]["status"].startswith("skipped"))
            self.assertTrue((Path(d) / "overnight" / "latest.json").exists())

    def test_reproduction_detects_change(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "phase99" / "results.json"
            f.parent.mkdir()
            f.write_text(json.dumps({"x": 1.0}))
            fake = types.SimpleNamespace(run=lambda **k: f.write_text(json.dumps({"x": 2.0})))
            with mock.patch.object(O, "ARTIFACTS_DIR", Path(d)), mock.patch.object(O, "ROOT", Path(d) / "overnight"), \
                    mock.patch.object(O, "STUDIES", [("9.9", "fake", "phase99/results.json", {}, ["x"])]), \
                    mock.patch.object(O, "PROSPECTIVE", []), mock.patch("importlib.import_module", return_value=fake):
                r = O.run(log=lambda m: None)
            self.assertEqual(r["studies"][0]["status"], "CHANGED")
            self.assertIn("x: 1.0 -> 2.0", O.summary_md(r))


if __name__ == "__main__":
    unittest.main()
