"""
Tests for migration 0006 — copilot_conversations table.

Validates the migration file structure using AST parsing (no database required).
"""
import ast
import pytest


MIGRATION_PATH = "alembic/versions/0006_copilot_conversations.py"


def _parse_migration():
    with open(MIGRATION_PATH) as f:
        return ast.parse(f.read())


def test_migration_file_parses():
    """Migration file must be valid Python."""
    tree = _parse_migration()
    assert tree is not None


def test_migration_has_correct_revision():
    """Revision chain must be 0005 -> 0006."""
    tree = _parse_migration()
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
    }
    assert assignments["revision"] == "0006"
    assert assignments["down_revision"] == "0005"


def test_migration_has_upgrade_and_downgrade():
    """Migration must define both upgrade() and downgrade() functions."""
    tree = _parse_migration()
    func_names = [
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    ]
    assert "upgrade" in func_names
    assert "downgrade" in func_names


def test_migration_creates_copilot_conversations_table():
    """upgrade() must contain a create_table call for copilot_conversations."""
    with open(MIGRATION_PATH) as f:
        source = f.read()
    assert "copilot_conversations" in source
    assert "create_table" in source


def test_migration_downgrade_drops_table():
    """downgrade() must drop the copilot_conversations table."""
    with open(MIGRATION_PATH) as f:
        source = f.read()
    assert "drop_table" in source


def test_migration_has_required_columns():
    """Table must have id, user_id, title, messages, created_at, updated_at."""
    with open(MIGRATION_PATH) as f:
        source = f.read()
    for col in ["id", "user_id", "title", "messages", "created_at", "updated_at", "provider"]:
        assert f'"{col}"' in source, f"Missing column: {col}"


def test_migration_user_id_has_foreign_key():
    """user_id must reference users.id with CASCADE delete."""
    with open(MIGRATION_PATH) as f:
        source = f.read()
    assert "users.id" in source
    assert "CASCADE" in source
