import pytest

import src.memory.long_memory as lm
class _FakeItem:
    def __init__(self, value):
        self.value = value


class _FakeStore:
    def __init__(self):
        self.data = {}  # (namespace, key) -> value

    async def aput(self, namespace, key, value):
        self.data[(namespace, key)] = value

    async def aget(self, namespace, key):
        value = self.data.get((namespace, key))
        return _FakeItem(value) if value is not None else None


class _FakeCM:
    def __init__(self):
        self.exited = False

    async def __aexit__(self, *exc):
        self.exited = True


@pytest.fixture
def fake_store(monkeypatch):
    store = _FakeStore()
    monkeypatch.setattr(lm, "_store", store)
    return store


async def test_save_and_get_user_memory(fake_store):
    await lm.save_user_memory("u1", "preferences", {"rules": ["a"]})
    # ghi đúng namespace ("users", user_id)
    assert fake_store.data[(("users", "u1"), "preferences")] == {"rules": ["a"]}
    got = await lm.get_user_memory("u1", "preferences")
    assert got == {"rules": ["a"]}


async def test_get_user_memory_missing_returns_none(fake_store):
    assert await lm.get_user_memory("u1", "khong-co") is None


async def test_save_requires_init(monkeypatch):
    monkeypatch.setattr(lm, "_store", None)
    with pytest.raises(AssertionError):
        await lm.save_user_memory("u1", "k", {})


async def test_get_requires_init(monkeypatch):
    monkeypatch.setattr(lm, "_store", None)
    with pytest.raises(AssertionError):
        await lm.get_user_memory("u1", "k")


async def test_update_preferences_from_empty(fake_store):
    await lm.update_user_preferences("u1", ["thích quận Cầu Giấy", "ngân sách 5 tỷ"])
    saved = fake_store.data[(("users", "u1"), "preferences")]
    assert saved == {"rules": ["thích quận Cầu Giấy", "ngân sách 5 tỷ"]}


async def test_update_preferences_dedup(fake_store):
    fake_store.data[(("users", "u1"), "preferences")] = {"rules": ["a", "b"]}
    await lm.update_user_preferences("u1", ["a", "c", "c", "b", "d"])
    saved = fake_store.data[(("users", "u1"), "preferences")]
    # giữ thứ tự, không thêm rule trùng
    assert saved == {"rules": ["a", "b", "c", "d"]}


async def test_update_profile_dedup(fake_store):
    fake_store.data[(("users", "u9"), "profile")] = {"rules": ["gia đình 4 người"]}
    await lm.update_user_profile("u9", ["gia đình 4 người", "có trẻ nhỏ"])
    saved = fake_store.data[(("users", "u9"), "profile")]
    assert saved == {"rules": ["gia đình 4 người", "có trẻ nhỏ"]}

async def test_close_long_memory(monkeypatch):
    cm = _FakeCM()
    monkeypatch.setattr(lm, "_cm", cm)
    monkeypatch.setattr(lm, "_store", _FakeStore())
    await lm.close_long_memory()
    assert cm.exited is True
    assert lm._cm is None
    assert lm._store is None
    assert lm.get_store() is None


async def test_close_long_memory_noop_when_not_init(monkeypatch):
    monkeypatch.setattr(lm, "_cm", None)
    await lm.close_long_memory()
    assert lm._cm is None
