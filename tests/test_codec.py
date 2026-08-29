import json
import unittest
from pathlib import Path

from anvil_alpha import AVP1Codec, CodecError, ContextMismatchError, canonical_json


ROOT = Path(__file__).resolve().parents[1]


class AVP1CodecTests(unittest.TestCase):
    def setUp(self):
        self.codec = AVP1Codec()
        self.sample = json.loads((ROOT / "examples/governed_mission.json").read_text())

    def test_exact_round_trip(self):
        wire = self.codec.encode(self.sample)
        self.assertEqual(canonical_json(self.sample), canonical_json(self.codec.decode(wire)))

    def test_authority_round_trip(self):
        decoded = self.codec.decode(self.codec.encode(self.sample))
        self.assertEqual(self.sample["authority"], decoded["authority"])

    def test_wrong_profile_fails_closed(self):
        wire = self.codec.encode(self.sample)
        with self.assertRaises(ContextMismatchError):
            AVP1Codec("wrong-profile").decode(wire)

    def test_corruption_rejected(self):
        wire = self.codec.encode(self.sample)
        with self.assertRaises(CodecError):
            self.codec.decode(wire[:-1])

    def test_reserved_prefixes_escape(self):
        source = {"@0": "#0", "ordinary": "##literal", "version": "0.1"}
        decoded = self.codec.decode(self.codec.encode(source))
        self.assertEqual(source, decoded)

    def test_encoding_is_deterministic(self):
        reversed_source = dict(reversed(list(self.sample.items())))
        self.assertEqual(self.codec.encode(self.sample), self.codec.encode(reversed_source))


if __name__ == "__main__":
    unittest.main()
