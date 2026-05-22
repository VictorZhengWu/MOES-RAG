# -*- coding: utf-8 -*-
"""
Shared test fixtures for M1 Doc Parsing Engine.

WHY: test_config.py injects a fake torch MagicMock into sys.modules at
module load time to work around broken CUDA libraries. This fake torch
interferes with docling imports in test_docling_backend.py (transformers
and docling try to use fake torch submodules that don't exist).

The fixture below removes the fake torch only for docling backend tests,
so both test modules can coexist in the same pytest session.
"""

import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _isolate_torch_for_docling(request):
    """
    Remove fake-torch MagicMock from sys.modules for docling backend tests.

    WHAT: before each test in test_docling_backend.py, checks if
    torch in sys.modules is a MagicMock (injected by test_config.py).
    If so, temporarily removes it so docling/transformers imports
    resolve against the real installation. Restores after the test.

    WHY scoped to docling tests only: the config tests NEED the fake
    torch because detect_hardware() does ``import torch`` internally
    and the real torch has broken CUDA shared libraries. The @patch
    decorators mock torch.cuda.* at the correct level, but the actual
    import statement must succeed with a usable module object.

    For backend tests, docling and its dependency chain (transformers,
    torchvision, etc.) need the real torch with all submodules present.
    Removing the MagicMock allows the real torch to be imported.
    """
    # Intervene for any test that imports docling (backend or converter)
    node_path = str(request.node.fspath)
    if "test_docling_backend" not in node_path and "test_converter" not in node_path:
        yield
        return

    # Save and remove fake torch
    fake_torch = None
    if "torch" in sys.modules:
        maybe_fake = sys.modules["torch"]
        if isinstance(maybe_fake, MagicMock):
            fake_torch = sys.modules.pop("torch")

    yield

    # Restore fake torch for subsequent config tests
    if fake_torch is not None and "torch" not in sys.modules:
        sys.modules["torch"] = fake_torch
