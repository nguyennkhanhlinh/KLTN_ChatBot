import pytest

import src.memory.long_memory as lm


_EMB_REGISTRY: dict[str, int] = {}
_EMB_DIM = 256


def _canon(text: str) -> str:
    t = " ".join(text.lower().split())
    return t.replace("bđs", "bất động sản") 


class _MockEmb:
    async def aembed_query(self, text: str) -> list[float]:
        idx = _EMB_REGISTRY.setdefault(_canon(text), len(_EMB_REGISTRY))
        vec = [0.0] * _EMB_DIM
        vec[idx % _EMB_DIM] = 1.0
        return vec


@pytest.fixture(autouse=True)
def mock_emb(monkeypatch):
    """Thay embedding thật bằng mock để test hermetic, không phụ thuộc API/mạng."""
    monkeypatch.setattr(lm, "_memory_embeddings", lambda: _MockEmb())


class _MockItem:
    def __init__(self, value):
        self.value = value


class _MockStore:
    def __init__(self):
        self.data = {}  # (namespace, key) -> value

    async def aput(self, namespace, key, value):
        self.data[(namespace, key)] = value

    async def aget(self, namespace, key):
        value = self.data.get((namespace, key))
        return _MockItem(value) if value is not None else None


class _MockCM:
    def __init__(self):
        self.exited = False

    async def __aexit__(self, *exc):
        self.exited = True


@pytest.fixture
def mock_store(monkeypatch):
    store = _MockStore()
    monkeypatch.setattr(lm, "_store", store)
    return store


async def test_save_and_get_user_memory(mock_store):
    await lm.save_user_memory("u1", "preferences", {"rules": ["a"]})
    # ghi đúng namespace ("users", user_id)
    assert mock_store.data[(("users", "u1"), "preferences")] == {"rules": ["a"]}
    got = await lm.get_user_memory("u1", "preferences")
    assert got == {"rules": ["a"]}


async def test_get_user_memory_missing_returns_none(mock_store):
    assert await lm.get_user_memory("u1", "khong-co") is None


async def test_save_requires_init(monkeypatch):
    monkeypatch.setattr(lm, "_store", None)
    with pytest.raises(AssertionError):
        await lm.save_user_memory("u1", "k", {})


async def test_get_requires_init(monkeypatch):
    monkeypatch.setattr(lm, "_store", None)
    with pytest.raises(AssertionError):
        await lm.get_user_memory("u1", "k")


async def test_update_preferences_from_empty(mock_store):
    await lm.update_user_preferences("u1", ["thích quận Cầu Giấy", "ngân sách 5 tỷ"])
    saved = mock_store.data[(("users", "u1"), "preferences")]
    assert saved == {"rules": ["thích quận Cầu Giấy", "ngân sách 5 tỷ"]}


async def test_update_preferences_dedup(mock_store):
    mock_store.data[(("users", "u1"), "preferences")] = {"rules": ["a", "b"]}
    await lm.update_user_preferences("u1", ["a", "c", "c", "b", "d"])
    saved = mock_store.data[(("users", "u1"), "preferences")]
    # giữ thứ tự, không thêm rule trùng
    assert saved == {"rules": ["a", "b", "c", "d"]}


async def test_update_profile_dedup(mock_store):
    mock_store.data[(("users", "u9"), "profile")] = {"rules": ["gia đình 4 người"]}
    await lm.update_user_profile("u9", ["gia đình 4 người", "có trẻ nhỏ"])
    saved = mock_store.data[(("users", "u9"), "profile")]
    assert saved == {"rules": ["gia đình 4 người", "có trẻ nhỏ"]}


async def test_update_preferences_semantic_dedup(mock_store):
    # "BĐS" và "bất động sản" khác chữ nhưng CÙNG NGHĨA → phải gộp còn 1.
    mock_store.data[(("users", "u2"), "preferences")] = {"rules": ["Quan tâm BĐS ở Gia Lâm"]}
    await lm.update_user_preferences(
        "u2", ["Quan tâm bất động sản ở Gia Lâm", "Muốn mua ở Ba Đình"]
    )
    saved = mock_store.data[(("users", "u2"), "preferences")]
    # câu trùng nghĩa bị bỏ (giữ câu cũ); câu khác khu vực được giữ
    assert saved == {"rules": ["Quan tâm BĐS ở Gia Lâm", "Muốn mua ở Ba Đình"]}

async def test_close_long_memory(monkeypatch):
    cm = _MockCM()
    monkeypatch.setattr(lm, "_cm", cm)
    monkeypatch.setattr(lm, "_store", _MockStore())
    await lm.close_long_memory()
    assert cm.exited is True
    assert lm._cm is None
    assert lm._store is None
    assert lm.get_store() is None


async def test_close_long_memory_noop_when_not_init(monkeypatch):
    monkeypatch.setattr(lm, "_cm", None)
    await lm.close_long_memory()
    assert lm._cm is None
