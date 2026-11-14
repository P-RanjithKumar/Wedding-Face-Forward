"""
Unit tests for database idempotency and state management.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from app.db import Database, Photo, Face, Person
from app.config import reset_config


class TestDatabaseIdempotency:
    """Tests for database idempotency - ensuring no duplicate processing."""
    
    @pytest.fixture
    def db(self):
        """Create a fresh temporary database for each test."""
        reset_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            database = Database(db_path)
            database.initialize()
            yield database
            database.close()
    
    def test_same_hash_processed_only_once(self, db):
        """Same file hash should not create duplicate records."""
        file_hash = "abc123def456"
        
        # First insert should succeed
        photo_id_1 = db.create_photo(file_hash, "/path/to/photo1.jpg")
        assert photo_id_1 == 1
        
        # Second insert with same hash should fail (UNIQUE constraint)
        with pytest.raises(Exception):
            db.create_photo(file_hash, "/path/to/photo2.jpg")
        
        # Only one record should exist
        photo = db.get_photo_by_hash(file_hash)
        assert photo is not None
        assert photo.id == 1
    
    def test_photo_exists_check(self, db):
        """photo_exists should correctly identify existing photos."""
        file_hash = "abc123def456"
        
        # Should not exist initially
        assert db.photo_exists(file_hash) is False
        
        # Create photo
        db.create_photo(file_hash, "/path/to/photo.jpg")
        
        # Should exist now
        assert db.photo_exists(file_hash) is True
    
    def test_processing_status_tracked(self, db):
        """Photo status should be tracked correctly through processing."""
        file_hash = "abc123def456"
        
        # Create photo - should be pending
        photo_id = db.create_photo(file_hash, "/path/to/photo.jpg")
        photo = db.get_photo_by_id(photo_id)
        assert photo.status == "pending"
        
        # Update to processing
        db.update_photo_status(photo_id, "processing")
        photo = db.get_photo_by_id(photo_id)
        assert photo.status == "processing"
        
        # Complete processing
        db.update_photo_processing(
            photo_id,
            "/path/to/processed.jpg",
            "/path/to/thumb.jpg",
            face_count=2,
            status="completed"
        )
        photo = db.get_photo_by_id(photo_id)
        assert photo.status == "completed"
        assert photo.face_count == 2
        assert photo.processed_at is not None
    
    def test_restart_resumes_from_pending(self, db):
        """After restart, only pending items should be returned."""
        # Create photos in various states
        db.create_photo("hash1", "/path/1.jpg")
        db.create_photo("hash2", "/path/2.jpg")
        db.create_photo("hash3", "/path/3.jpg")
        
        # Mark some as completed
        db.update_photo_status(1, "completed")
        db.update_photo_status(2, "processing")  # Simulate interrupted
        # Photo 3 remains pending
        
        # Get pending photos (simulating restart)
        pending = db.get_pending_photos()
        
        # Only truly pending photos should be returned
        assert len(pending) == 1
        assert pending[0].id == 3
    
    def test_error_status_persists(self, db):
        """Error status should persist and not be reprocessed."""
        file_hash = "corrupt_file_hash"
        photo_id = db.create_photo(file_hash, "/path/to/corrupt.jpg")
        
        # Mark as error
        db.update_photo_status(photo_id, "error")
        
        # Get pending - should not include error
        pending = db.get_pending_photos()
        assert len(pending) == 0
        
        # But photo should still exist
        photo = db.get_photo_by_hash(file_hash)
        assert photo is not None
        assert photo.status == "error"


class TestDatabaseCRUD:
    """Tests for basic CRUD operations."""
    
    @pytest.fixture
    def db(self):
        """Create a fresh temporary database for each test."""
        reset_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            database = Database(db_path)
            database.initialize()
            yield database
            database.close()
    
    def test_create_and_retrieve_photo(self, db):
        """Should create and retrieve photo correctly."""
        photo_id = db.create_photo("test_hash", "/test/path.jpg")
        
        photo = db.get_photo_by_id(photo_id)
        assert photo.file_hash == "test_hash"
        assert photo.original_path == "/test/path.jpg"
        assert photo.status == "pending"
    
    def test_create_and_retrieve_person(self, db):
        """Should create and retrieve person correctly."""
        import numpy as np
        
        centroid = np.random.randn(512).astype(np.float32)
        person_id = db.create_person("Person_001", centroid)
        
        person = db.get_person_by_id(person_id)
        assert person.name == "Person_001"
        assert person.face_count == 1
        np.testing.assert_array_equal(person.centroid, centroid)
    
    def test_create_face_with_embedding(self, db):
        """Should store and retrieve face embeddings correctly."""
        import numpy as np
        
        # Create photo first
        photo_id = db.create_photo("test_hash", "/test/path.jpg")
        
        # Create face with embedding
        embedding = np.random.randn(512).astype(np.float32)
        face_id = db.create_face(
            photo_id=photo_id,
            bbox=(100, 100, 200, 200),
            embedding=embedding,
            confidence=0.95
        )
        
        # Retrieve faces
        faces = db.get_faces_by_photo(photo_id)
        assert len(faces) == 1
        assert faces[0].confidence == pytest.approx(0.95)
        np.testing.assert_array_equal(faces[0].embedding, embedding)
    
    def test_get_unique_persons_in_photo(self, db):
        """Should correctly identify unique persons in a photo."""
        import numpy as np
        
        photo_id = db.create_photo("test_hash", "/test/path.jpg")
        embedding = np.random.randn(512).astype(np.float32)
        
        # Create two persons
        person1_id = db.create_person("Person_001", embedding)
        person2_id = db.create_person("Person_002", embedding)
        
        # Add faces for both persons
        db.create_face(photo_id, (0, 0, 100, 100), embedding, 0.9, person1_id)
        db.create_face(photo_id, (200, 0, 100, 100), embedding, 0.9, person2_id)
        db.create_face(photo_id, (0, 200, 100, 100), embedding, 0.9, person1_id)  # Same person again
        
        unique_persons = db.get_unique_persons_in_photo(photo_id)
        assert len(unique_persons) == 2
        assert set(unique_persons) == {person1_id, person2_id}
    
    def test_update_person_centroid(self, db):
        """Should update person centroid and face count."""
        import numpy as np
        
        old_centroid = np.array([1.0] + [0.0] * 511, dtype=np.float32)
        person_id = db.create_person("Person_001", old_centroid)
        
        new_centroid = np.array([0.0, 1.0] + [0.0] * 510, dtype=np.float32)
        db.update_person_centroid(person_id, new_centroid, face_count=5)
        
        person = db.get_person_by_id(person_id)
        assert person.face_count == 5
        np.testing.assert_array_equal(person.centroid, new_centroid)


class TestDatabaseStats:
    """Tests for statistics retrieval."""
    
    @pytest.fixture
    def populated_db(self):
        """Create a database with sample data."""
        reset_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.initialize()
            
            # Add sample photos
            db.create_photo("hash1", "/path/1.jpg")
            db.create_photo("hash2", "/path/2.jpg")
            db.create_photo("hash3", "/path/3.jpg")
            
            db.update_photo_status(1, "completed")
            db.update_photo_status(2, "completed")
            # 3 remains pending
            
            yield db
            db.close()
    
    def test_get_stats(self, populated_db):
        """Should return correct statistics."""
        stats = populated_db.get_stats()
        
        assert stats["photos_by_status"]["completed"] == 2
        assert stats["photos_by_status"]["pending"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
