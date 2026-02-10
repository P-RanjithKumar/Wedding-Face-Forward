"""
Unit tests for the clustering module.
"""

import numpy as np
import pytest
import tempfile
from pathlib import Path

from app.cluster import (
    cosine_distance,
    euclidean_distance,
    find_nearest_person,
    update_centroid,
    assign_person,
    get_cluster_stats,
)
from app.db import Database, Person
from app.config import reset_config


class TestCosineDistance:
    """Tests for cosine distance calculation."""
    
    def test_identical_vectors(self):
        """Identical vectors should have distance 0."""
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([1.0, 0.0, 0.0])
        assert cosine_distance(a, b) == pytest.approx(0.0)
    
    def test_orthogonal_vectors(self):
        """Orthogonal vectors should have distance 1."""
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        assert cosine_distance(a, b) == pytest.approx(1.0)
    
    def test_opposite_vectors(self):
        """Opposite vectors should have distance 2."""
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([-1.0, 0.0, 0.0])
        assert cosine_distance(a, b) == pytest.approx(2.0)
    
    def test_similar_vectors(self):
        """Similar vectors should have small distance."""
        a = np.array([1.0, 0.1, 0.0])
        b = np.array([1.0, 0.0, 0.0])
        distance = cosine_distance(a, b)
        assert distance < 0.1
    
    def test_zero_vector(self):
        """Zero vector should have max distance."""
        a = np.array([0.0, 0.0, 0.0])
        b = np.array([1.0, 0.0, 0.0])
        assert cosine_distance(a, b) == 2.0


class TestCentroidUpdate:
    """Tests for centroid update logic."""
    
    def test_first_update(self):
        """First update should move centroid towards new embedding."""
        old_centroid = np.array([1.0, 0.0, 0.0])
        new_embedding = np.array([0.0, 1.0, 0.0])
        
        new_centroid = update_centroid(old_centroid, new_embedding, old_count=1)
        
        # Should be normalized average
        expected = np.array([0.5, 0.5, 0.0])
        expected = expected / np.linalg.norm(expected)
        np.testing.assert_array_almost_equal(new_centroid, expected)
    
    def test_weighted_update(self):
        """Centroid should move less with more existing faces."""
        old_centroid = np.array([1.0, 0.0, 0.0])
        new_embedding = np.array([0.0, 1.0, 0.0])
        
        # With 9 existing faces, new embedding has less weight
        new_centroid = update_centroid(old_centroid, new_embedding, old_count=9)
        
        # Should be closer to old centroid
        assert new_centroid[0] > new_centroid[1]


class TestAssignPerson:
    """Tests for person assignment with database integration."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        reset_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.initialize()
            yield db
            db.close()
    
    def test_new_person_when_empty(self, temp_db, monkeypatch):
        """New embedding creates person when database is empty."""
        # Mock get_db to return our temp_db
        monkeypatch.setattr("app.cluster.get_db", lambda: temp_db)
        monkeypatch.setattr("app.cluster.get_config", lambda: type("Config", (), {"cluster_threshold": 0.6})())
        
        embedding = np.random.randn(512).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        
        person_id = assign_person(embedding, threshold=0.6)
        
        assert person_id == 1
        persons = temp_db.get_all_persons()
        assert len(persons) == 1
    
    def test_assign_to_existing_when_similar(self, temp_db, monkeypatch):
        """Embedding within threshold joins existing cluster."""
        monkeypatch.setattr("app.cluster.get_db", lambda: temp_db)
        monkeypatch.setattr("app.cluster.get_config", lambda: type("Config", (), {"cluster_threshold": 0.6})())
        
        # Create initial person
        base_embedding = np.random.randn(512).astype(np.float32)
        base_embedding = base_embedding / np.linalg.norm(base_embedding)
        temp_db.create_person("Person_001", base_embedding)
        
        # Create similar embedding (small perturbation)
        similar_embedding = base_embedding + np.random.randn(512).astype(np.float32) * 0.1
        similar_embedding = similar_embedding / np.linalg.norm(similar_embedding)
        
        person_id = assign_person(similar_embedding, threshold=0.6)
        
        # Should join existing person
        assert person_id == 1
        persons = temp_db.get_all_persons()
        assert len(persons) == 1
        assert persons[0].face_count == 2
    
    def test_create_new_when_different(self, temp_db, monkeypatch):
        """Different embedding creates new person."""
        monkeypatch.setattr("app.cluster.get_db", lambda: temp_db)
        monkeypatch.setattr("app.cluster.get_config", lambda: type("Config", (), {"cluster_threshold": 0.3})())
        
        # Create initial person
        base_embedding = np.zeros(512, dtype=np.float32)
        base_embedding[0] = 1.0
        temp_db.create_person("Person_001", base_embedding)
        
        # Create very different embedding
        diff_embedding = np.zeros(512, dtype=np.float32)
        diff_embedding[1] = 1.0  # Orthogonal to first
        
        person_id = assign_person(diff_embedding, threshold=0.3)
        
        # Should create new person
        assert person_id == 2
        persons = temp_db.get_all_persons()
        assert len(persons) == 2


class TestFindNearestPerson:
    """Tests for finding the nearest person cluster."""
    
    def test_empty_persons_list(self):
        """Should return None with infinite distance for empty list."""
        embedding = np.array([1.0, 0.0, 0.0])
        person, distance = find_nearest_person(embedding, [])
        
        assert person is None
        assert distance == float("inf")
    
    def test_single_person(self):
        """Should return the only person available."""
        embedding = np.array([1.0, 0.0, 0.0])
        person = Person(
            id=1,
            name="Person_001",
            centroid=np.array([0.9, 0.1, 0.0]),
            face_count=5,
            created_at=None
        )
        
        nearest, distance = find_nearest_person(embedding, [person])
        
        assert nearest.id == 1
        assert distance < 0.5
    
    def test_multiple_persons_finds_nearest(self):
        """Should find the nearest person among multiple."""
        embedding = np.array([1.0, 0.0, 0.0])
        
        persons = [
            Person(1, "Person_001", np.array([0.0, 1.0, 0.0]), 1, None),  # Orthogonal
            Person(2, "Person_002", np.array([0.9, 0.1, 0.0]), 1, None),  # Similar
            Person(3, "Person_003", np.array([-1.0, 0.0, 0.0]), 1, None),  # Opposite
        ]
        
        nearest, distance = find_nearest_person(embedding, persons)
        
        assert nearest.id == 2  # The similar one


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
