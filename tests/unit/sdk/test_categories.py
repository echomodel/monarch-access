"""Tests for categories operations."""

import pytest


class TestCategoriesList:
    """Test listing categories."""

    def test_get_categories_returns_list(self, local_provider):
        """Test that get_categories returns a list."""
        categories = local_provider.get_categories()

        assert isinstance(categories, list)
        assert len(categories) > 0

    def test_get_categories_has_expected_fields(self, local_provider):
        """Test that categories have expected fields."""
        categories = local_provider.get_categories()
        category = categories[0]

        expected_fields = ["id", "name", "icon", "group"]
        for field in expected_fields:
            assert field in category, f"Missing field: {field}"

    def test_get_categories_has_group_info(self, local_provider):
        """Test that categories include group information."""
        categories = local_provider.get_categories()

        for category in categories:
            assert "group" in category
            group = category["group"]
            assert "id" in group
            assert "name" in group
            assert "type" in group

    def test_get_categories_includes_expense_and_income(self, local_provider):
        """Test that categories include both expense and income types."""
        categories = local_provider.get_categories()
        group_types = {c["group"]["type"] for c in categories}

        assert "expense" in group_types
        assert "income" in group_types

    def test_get_categories_common_names_present(self, local_provider):
        """Test that common category names are present."""
        categories = local_provider.get_categories()
        names = {c["name"] for c in categories}

        # Based on our seed data
        assert "Groceries" in names
        assert "Restaurants" in names
        assert "Shopping" in names
        assert "Salary" in names
