"""Focused outer-ip_dict compatibility tests; no PYNQ import and inert collector deps."""
from __future__ import annotations

from collections import UserDict
import contextlib
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest


HERE = Path(__file__).resolve().parent
COLLECT_PRIVATE_PATH = Path(os.environ.get(
    "REPRDICT_COLLECT_PRIVATE_PATH", HERE / "collect_private_diag.py")).resolve()
COLLECTOR_PATH = Path(os.environ.get(
    "REPRDICT_COLLECTOR_PATH", HERE / "g05_capture" / "collector" / "collector.py")).resolve()
BASE = 0x40000000
SPAN = 0x1000


class ReprDict(dict):
    """Stand-in for pynqutils.runtime.repr_dict.ReprDict."""


class InnerDict(dict):
    """Inner entries must remain exact dict instances."""


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_module(name, path):
    if not path.is_file():
        raise FileNotFoundError("candidate source not found: " + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load candidate source: " + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def _collector_dependency_stubs():
    missing = object()
    saved = {name: sys.modules.get(name, missing) for name in ("pins", "transport")}
    pins = ModuleType("pins")
    transport = ModuleType("transport")
    transport.run_transport = lambda *args, **kwargs: None
    transport.stop_once = lambda *args, **kwargs: None
    sys.modules["pins"] = pins
    sys.modules["transport"] = transport
    try:
        yield
    finally:
        for name, previous in saved.items():
            if previous is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


print("reprdict candidate collect_private=" + str(COLLECT_PRIVATE_PATH) +
      " sha256=" + _sha256(COLLECT_PRIVATE_PATH))
print("reprdict candidate collector=" + str(COLLECTOR_PATH) +
      " sha256=" + _sha256(COLLECTOR_PATH))

collect_private = _load_module("_reprdict_collect_private_candidate", COLLECT_PRIVATE_PATH)
with _collector_dependency_stubs():
    collector = _load_module("_reprdict_collector_candidate", COLLECTOR_PATH)


class CollectPrivateOverlayTests(unittest.TestCase):
    module = collect_private
    instance = collect_private.INSTANCE
    vlnv = collect_private.VLNV

    def setUp(self):
        self.item = {
            "fullpath": self.instance,
            "type": self.vlnv,
            "phys_addr": BASE,
            "addr_range": SPAN,
        }
        self.validated = SimpleNamespace(base=BASE, span=SPAN)

    def check(self, ips):
        self.module.check_overlay(SimpleNamespace(ip_dict=ips), self.validated)

    def assert_rejected(self, ips):
        with self.assertRaises(self.module.Rejected):
            self.check(ips)

    def test_plain_dict_outer_accepted(self):
        self.check({self.instance: self.item})

    def test_dict_subclass_outer_accepted(self):
        self.check(ReprDict({self.instance: self.item}))

    def test_wrong_outer_types_rejected(self):
        for ips in ([], [self.item], UserDict({self.instance: self.item})):
            with self.subTest(outer_type=type(ips).__name__):
                self.assert_rejected(ips)

    def test_missing_identity_rejected(self):
        self.assert_rejected({})

    def test_duplicate_identity_rejected(self):
        self.assert_rejected({
            self.instance: self.item,
            "/" + self.instance: dict(self.item),
        })

    def test_wrong_identity_rejected(self):
        for ips in (
            {"other": {**self.item, "fullpath": "other"}},
            {self.instance: {**self.item, "fullpath": "other"}},
        ):
            with self.subTest(ip_dict=ips):
                self.assert_rejected(ips)

    def test_wrong_vlnv_rejected(self):
        self.assert_rejected({self.instance: {**self.item, "type": "wrong:vendor:ip:1.0"}})

    def test_wrong_base_rejected(self):
        self.assert_rejected({self.instance: {**self.item, "phys_addr": BASE + 4}})

    def test_wrong_span_rejected(self):
        self.assert_rejected({self.instance: {**self.item, "addr_range": SPAN + 4}})

    def test_bad_value_types_rejected(self):
        for field, value in (
            ("phys_addr", True),
            ("phys_addr", "0x40000000"),
            ("phys_addr", float(BASE)),
            ("addr_range", False),
            ("addr_range", "4096"),
            ("addr_range", float(SPAN)),
        ):
            with self.subTest(field=field, value=value):
                self.assert_rejected({self.instance: {**self.item, field: value}})

    def test_inner_dict_subclass_rejected(self):
        self.assert_rejected({self.instance: InnerDict(self.item)})

    def test_missing_inner_field_rejected(self):
        item = dict(self.item)
        del item["fullpath"]
        self.assert_rejected({self.instance: item})

    def test_non_dict_inner_entry_rejected(self):
        self.assert_rejected({self.instance: "not-an-entry"})


class CollectorOverlayTests(unittest.TestCase):
    module = collector
    instance = "g05_diag_i"
    vlnv = "carlandfpga:diagnostic:g05_capture:1.0"

    def setUp(self):
        self.item = {
            "fullpath": self.instance,
            "type": self.vlnv,
            "phys_addr": BASE,
            "addr_range": SPAN,
        }
        self.mapping = {
            "instance": self.instance,
            "vlnv": self.vlnv,
            "base": hex(BASE),
            "span": SPAN,
        }

    def check(self, ips):
        self.module.check_overlay(SimpleNamespace(ip_dict=ips), self.mapping)

    def assert_rejected(self, ips):
        with self.assertRaises(self.module.Rejected):
            self.check(ips)

    def test_plain_dict_outer_accepted(self):
        self.check({self.instance: self.item})

    def test_dict_subclass_outer_accepted(self):
        self.check(ReprDict({self.instance: self.item}))

    def test_wrong_outer_types_rejected(self):
        for ips in ([], [self.item], UserDict({self.instance: self.item})):
            with self.subTest(outer_type=type(ips).__name__):
                self.assert_rejected(ips)

    def test_missing_identity_rejected(self):
        self.assert_rejected({})

    def test_duplicate_identity_rejected(self):
        self.assert_rejected({
            self.instance: self.item,
            "/" + self.instance: dict(self.item),
        })

    def test_wrong_identity_rejected(self):
        for ips in (
            {"other": {**self.item, "fullpath": "other"}},
            {self.instance: {**self.item, "fullpath": "other"}},
        ):
            with self.subTest(ip_dict=ips):
                self.assert_rejected(ips)

    def test_wrong_vlnv_rejected(self):
        self.assert_rejected({self.instance: {**self.item, "type": "wrong:vendor:ip:1.0"}})

    def test_wrong_base_rejected(self):
        self.assert_rejected({self.instance: {**self.item, "phys_addr": BASE + 4}})

    def test_wrong_span_rejected(self):
        self.assert_rejected({self.instance: {**self.item, "addr_range": SPAN + 4}})

    def test_bad_value_types_rejected(self):
        for field, value in (
            ("phys_addr", True),
            ("phys_addr", "0x40000000"),
            ("phys_addr", float(BASE)),
            ("addr_range", False),
            ("addr_range", "4096"),
            ("addr_range", float(SPAN)),
        ):
            with self.subTest(field=field, value=value):
                self.assert_rejected({self.instance: {**self.item, field: value}})

    def test_inner_dict_subclass_rejected(self):
        self.assert_rejected({self.instance: InnerDict(self.item)})

    def test_missing_inner_field_rejected(self):
        item = dict(self.item)
        del item["fullpath"]
        self.assert_rejected({self.instance: item})

    def test_non_dict_inner_entry_rejected(self):
        self.assert_rejected({self.instance: "not-an-entry"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
