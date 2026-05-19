"""
Integration tests for StorageManager lifecycle management.

WHY: The Manager orchestrates 4 independent backends. Its initialize,
health_check, and close methods must handle concurrent execution and
partial failures correctly -- bugs here would cause silent startup
failures or resource leaks in production.
"""

import pytest

from m2_storage.manager import StorageManager


# ---------------------------------------------------------------------------
# Mock backend for controlled testing
# ---------------------------------------------------------------------------

class MockBackend:
    """
    A controllable mock implementing all lifecycle methods.

    WHY not use unittest.mock.AsyncMock: manual tracking of call counts
    and configurable failure modes gives us more precise assertions about
    Manager's orchestration behavior (did it call all 4? in what order?
    did it handle a failure without skipping remaining backends?).
    """

    def __init__(self, name="mock", fail_init=False, fail_health=False):
        self.name = name
        self._fail_init = fail_init
        self._fail_health = fail_health
        self.init_called = 0
        self.health_called = 0
        self.close_called = 0

    async def initialize(self) -> None:
        self.init_called += 1
        if self._fail_init:
            raise RuntimeError(f"{self.name} init failed")

    async def health_check(self) -> bool:
        self.health_called += 1
        if self._fail_health:
            return False
        return True

    async def close(self) -> None:
        self.close_called += 1


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def four_healthy_backends():
    """Return 4 MockBackend instances, all healthy."""
    return (
        MockBackend("vector_store"),
        MockBackend("doc_index"),
        MockBackend("relational_db"),
        MockBackend("file_store"),
    )


@pytest.fixture
def manager(four_healthy_backends):
    """Return a StorageManager with 4 mock backends."""
    vs, di, rdb, fs = four_healthy_backends
    return StorageManager(
        vector_store=vs, doc_index=di, relational_db=rdb, file_store=fs
    )


# ---------------------------------------------------------------------------
# Test 1: initialize calls all 4 backends
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_calls_all_backends(manager, four_healthy_backends):
    """
    initialize() must call each backend's initialize() exactly once.

    WHY: If a backend is skipped during init, it would be in an unknown
    state and fail on first use -- a silent bug that only surfaces when
    someone tries to search or read a file.
    """
    await manager.initialize()
    for backend in four_healthy_backends:
        assert backend.init_called == 1, (
            f"{backend.name} should be initialized exactly once, "
            f"got {backend.init_called}"
        )


# ---------------------------------------------------------------------------
# Test 2: health_check returns correct dict
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_check_all_healthy(manager):
    """
    health_check must return {name: True} for all backends.

    WHY: The health check dict is consumed by monitoring endpoints
    (M7 admin dashboard). The key names must be stable and predictable.
    """
    result = await manager.health_check()
    assert result == {
        "vector_store": True,
        "doc_index": True,
        "relational_db": True,
        "file_store": True,
    }


# ---------------------------------------------------------------------------
# Test 3: close calls all 4 backends
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_close_calls_all_backends(manager, four_healthy_backends):
    """
    close() must call each backend's close() exactly once.

    WHY: If close() skips a backend, that backend's resources
    (connections, file handles) would leak. In Personal mode this
    could exhaust file descriptors; in server mode it would accumulate
    over the process lifetime.
    """
    await manager.close()
    for backend in four_healthy_backends:
        assert backend.close_called == 1, (
            f"{backend.name} should be closed exactly once, "
            f"got {backend.close_called}"
        )


# ---------------------------------------------------------------------------
# Test 4: one backend init failure does not block others
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_partial_init_failure():
    """
    If one backend fails to initialize, others must still be initialized.

    WHY: A broken Meilisearch (which requires an external process) should
    not prevent ChromaDB, SQLite, and LocalFS from starting. The system
    should degrade gracefully rather than fail completely.
    """
    healthy = MockBackend("healthy")
    failing = MockBackend("failing", fail_init=True)
    also_healthy = MockBackend("also_healthy")

    mgr = StorageManager(
        vector_store=healthy,
        doc_index=failing,
        relational_db=also_healthy,
        file_store=MockBackend("fs"),
    )
    # Must not raise -- failures are logged, not propagated
    await mgr.initialize()

    # Healthy backends must have been initialized
    assert healthy.init_called == 1, "Healthy backend was not initialized"
    # Failing backend must have been attempted
    assert failing.init_called == 1, "Failing backend was not attempted"
    # Other healthy backends must also have been initialized
    assert also_healthy.init_called == 1, (
        "Second healthy backend was skipped after failure"
    )


# ---------------------------------------------------------------------------
# Test 5: health_check reflects backend failures
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_check_reflects_failure():
    """
    If a backend's health_check returns False, the Manager must report it.

    WHY: The admin dashboard relies on this dict to show red/green status.
    A False must propagate, not be swallowed.
    """
    unhealthy = MockBackend("unhealthy", fail_health=True)
    mgr = StorageManager(
        vector_store=unhealthy,
        doc_index=MockBackend("di"),
        relational_db=MockBackend("rdb"),
        file_store=MockBackend("fs"),
    )
    result = await mgr.health_check()
    assert result["vector_store"] is False
    assert result["doc_index"] is True
    assert result["relational_db"] is True
    assert result["file_store"] is True
