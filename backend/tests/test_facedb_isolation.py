"""
Tests for FaceDB user isolation.
All face operations must be scoped to user_id — no cross-user data access.
"""
import os
import sqlite3
import tempfile
import pytest

from stages.facedb import FaceDB, _DEFAULT_USER


@pytest.fixture
def tmp_db(tmp_path):
    """Return a FaceDB instance backed by a temp SQLite file."""
    db_path = tmp_path / "test_faces.db"
    db = FaceDB(db_path=str(db_path))
    yield db
    db.close()


def _insert_face(db: FaceDB, user_id: str, image_hash: str, label: str = ""):
    """Directly insert a face row to test isolation without needing CV libs."""
    import json, time
    db._conn.execute(
        """INSERT INTO faces
           (user_id, image_path, image_hash, face_index, embedding, bbox, confidence, label, indexed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, "/tmp/test.jpg", image_hash, 0,
         json.dumps([0.1] * 512), "[]", 0.99, label,
         time.strftime("%Y-%m-%dT%H:%M:%S"))
    )
    db._conn.commit()


class TestFaceDBIsolation:
    def test_stats_scoped_to_user(self, tmp_db):
        _insert_face(tmp_db, "user_a", "hash_a1")
        _insert_face(tmp_db, "user_a", "hash_a2")
        _insert_face(tmp_db, "user_b", "hash_b1")

        stats_a = tmp_db.stats(user_id="user_a")
        stats_b = tmp_db.stats(user_id="user_b")

        assert stats_a["total_faces"] == 2
        assert stats_b["total_faces"] == 1

    def test_list_images_scoped_to_user(self, tmp_db):
        _insert_face(tmp_db, "user_a", "hash_a1")
        _insert_face(tmp_db, "user_b", "hash_b1")

        imgs_a = tmp_db.list_images(user_id="user_a")
        imgs_b = tmp_db.list_images(user_id="user_b")

        assert len(imgs_a) == 1
        assert imgs_a[0]["hash"] == "hash_a1"
        assert len(imgs_b) == 1
        assert imgs_b[0]["hash"] == "hash_b1"

    def test_search_embedding_scoped_to_user(self, tmp_db):
        """User B's faces must not appear in user A's search results."""
        import json
        embedding = [1.0] + [0.0] * 511  # unit vector
        _insert_face(tmp_db, "user_a", "hash_a1")  # default embedding (not matching)
        # Insert a near-identical embedding for user_b
        tmp_db._conn.execute(
            """INSERT INTO faces
               (user_id, image_path, image_hash, face_index, embedding, bbox, confidence, label, indexed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("user_b", "/tmp/b.jpg", "hash_b1", 0,
             json.dumps(embedding), "[]", 0.99, "target_person",
             "2024-01-01T00:00:00")
        )
        tmp_db._conn.commit()

        results_a = tmp_db.search_embedding(embedding, top_k=10, user_id="user_a")
        results_b = tmp_db.search_embedding(embedding, top_k=10, user_id="user_b")

        # User A has no matching faces
        assert all(r.get("label") != "target_person" for r in results_a)
        # User B should find the match
        assert any(r.get("label") == "target_person" for r in results_b)

    def test_remove_image_scoped_to_user(self, tmp_db):
        """User A cannot delete user B's faces."""
        _insert_face(tmp_db, "user_b", "shared_hash")

        tmp_db.remove_image("shared_hash", user_id="user_a")  # attempt by wrong user

        # user_b's face should still be there
        count = tmp_db._conn.execute(
            "SELECT COUNT(*) FROM faces WHERE user_id = 'user_b' AND image_hash = 'shared_hash'"
        ).fetchone()[0]
        assert count == 1

    def test_label_face_scoped_to_user(self, tmp_db):
        """User A cannot relabel user B's faces."""
        _insert_face(tmp_db, "user_b", "hash_b1", label="original_label")

        tmp_db.label_face("hash_b1", 0, "malicious_label", user_id="user_a")

        row = tmp_db._conn.execute(
            "SELECT label FROM faces WHERE user_id = 'user_b' AND image_hash = 'hash_b1'"
        ).fetchone()
        assert row[0] == "original_label"

    def test_schema_has_user_id_column(self, tmp_db):
        cols = [row[1] for row in tmp_db._conn.execute("PRAGMA table_info(faces)").fetchall()]
        assert "user_id" in cols

    def test_default_user_sentinel(self, tmp_db):
        """CLI mode (no user_id) uses __global__ sentinel — not empty string."""
        _insert_face(tmp_db, _DEFAULT_USER, "hash_cli")
        stats = tmp_db.stats()  # no user_id → uses _DEFAULT_USER
        assert stats["total_faces"] == 1
