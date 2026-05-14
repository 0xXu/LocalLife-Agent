import unittest
from backend.agents.memory import MemoryItem, MemoryStore


class TestMemoryItem(unittest.TestCase):
    def test_create_preference_item(self):
        item = MemoryItem(
            type="preference",
            content={"diet": "low_fat"},
            source="user_explicit",
            confidence=1.0,
        )
        self.assertEqual(item.type, "preference")
        self.assertEqual(item.source, "user_explicit")
        self.assertEqual(item.confidence, 1.0)

    def test_create_history_item(self):
        item = MemoryItem(
            type="history",
            content={"poi_id": "poi_001", "action": "selected"},
            source="user_behavior",
            confidence=0.8,
        )
        self.assertEqual(item.type, "history")

    def test_default_values(self):
        item = MemoryItem(type="preference", content={}, source="user_explicit", confidence=1.0)
        self.assertIsNone(item.expires_at)


class TestMemoryStore(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()

    def test_put_and_get_preference(self):
        self.store.put_preference("user_1", {"diet": "low_fat"})
        pref = self.store.get_preference("user_1")
        self.assertEqual(pref["diet"], "low_fat")

    def test_get_missing_preference_returns_empty(self):
        pref = self.store.get_preference("nonexistent")
        self.assertEqual(pref, {})

    def test_add_history_entry(self):
        self.store.add_history("user_1", {"poi_id": "poi_001", "action": "selected"})
        self.store.add_history("user_1", {"poi_id": "poi_002", "action": "rejected"})
        history = self.store.get_history("user_1", limit=10)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["poi_id"], "poi_001")

    def test_history_limit(self):
        for i in range(5):
            self.store.add_history("user_1", {"idx": i})
        history = self.store.get_history("user_1", limit=3)
        self.assertEqual(len(history), 3)

    def test_add_poi_feedback(self):
        self.store.add_poi_feedback("poi_001", {"rating": 4.5, "comment": "great"})
        feedback = self.store.get_poi_feedback("poi_001")
        self.assertEqual(len(feedback), 1)
        self.assertEqual(feedback[0]["rating"], 4.5)

    def test_build_context_message(self):
        self.store.put_preference("user_1", {"diet": "low_fat", "budget": "medium"})
        self.store.add_history("user_1", {"poi_id": "poi_001", "action": "selected"})
        msg = self.store.build_context_message("user_1")
        self.assertIn("low_fat", msg)
        self.assertIn("poi_001", msg)


if __name__ == "__main__":
    unittest.main()
