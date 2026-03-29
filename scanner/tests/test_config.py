"""Tests for ProjectConfig (.compliancelintrc support)."""
import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.config import ProjectConfig


class TestProjectConfigLoad:
    """Test loading config from various file names."""

    def test_load_compliancelintrc(self, tmp_path):
        """Load config from .compliancelintrc file."""
        config_data = {"skip_articles": [5, 6], "custom_source_dirs": ["src/"]}
        config_file = tmp_path / ".compliancelintrc"
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        config = ProjectConfig.load(str(tmp_path))
        assert config.skip_articles == [5, 6]
        assert config.custom_source_dirs == ["src/"]
        assert config.has_config is True

    def test_load_compliancelintrc_json(self, tmp_path):
        """Load config from .compliancelintrc.json file."""
        config_data = {"skip_articles": [9]}
        config_file = tmp_path / ".compliancelintrc.json"
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        config = ProjectConfig.load(str(tmp_path))
        assert config.skip_articles == [9]

    def test_load_compliancelint_json(self, tmp_path):
        """Load config from compliancelint.json file."""
        config_data = {"risk_classification_override": "not_high_risk"}
        config_file = tmp_path / "compliancelint.json"
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        config = ProjectConfig.load(str(tmp_path))
        assert config.risk_classification_override == "not_high_risk"

    def test_priority_order(self, tmp_path):
        """.compliancelintrc takes priority over .compliancelintrc.json."""
        rc = tmp_path / ".compliancelintrc"
        rc.write_text(json.dumps({"skip_articles": [1]}), encoding="utf-8")
        rc_json = tmp_path / ".compliancelintrc.json"
        rc_json.write_text(json.dumps({"skip_articles": [2]}), encoding="utf-8")

        config = ProjectConfig.load(str(tmp_path))
        assert config.skip_articles == [1]


class TestProjectConfigEmpty:
    """Test behavior when no config file exists."""

    def test_empty_config_when_no_file(self, tmp_path):
        """Return empty config when no config file found."""
        config = ProjectConfig.load(str(tmp_path))
        assert config.skip_articles == []
        assert config.process_managed_externally == {}
        assert config.custom_source_dirs == []
        assert config.custom_test_dirs == []
        assert config.risk_classification_override == ""
        assert config.has_config is False

    def test_empty_config_on_invalid_json(self, tmp_path):
        """Return empty config when config file has invalid JSON."""
        config_file = tmp_path / ".compliancelintrc"
        config_file.write_text("not valid json {{{", encoding="utf-8")

        config = ProjectConfig.load(str(tmp_path))
        assert config.has_config is False


class TestSkipArticles:
    """Test skip_articles filtering logic."""

    def test_skip_articles_list(self, tmp_path):
        config_data = {"skip_articles": [5, 12, 50]}
        config_file = tmp_path / ".compliancelintrc"
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        config = ProjectConfig.load(str(tmp_path))
        assert 5 in config.skip_articles
        assert 12 in config.skip_articles
        assert 50 in config.skip_articles
        assert 9 not in config.skip_articles

    def test_empty_skip_articles(self, tmp_path):
        config_data = {"skip_articles": []}
        config_file = tmp_path / ".compliancelintrc"
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        config = ProjectConfig.load(str(tmp_path))
        assert config.skip_articles == []
        # Empty lists should not count as "has_config"
        assert config.has_config is False


class TestProcessManagedExternally:
    """Test process_managed_externally field."""

    def test_process_managed_externally(self, tmp_path):
        config_data = {
            "process_managed_externally": {
                "art9": "Risk assessment in Confluence: https://wiki.example.com/risk",
                "art11": "Technical docs in SharePoint",
            }
        }
        config_file = tmp_path / ".compliancelintrc"
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        config = ProjectConfig.load(str(tmp_path))
        assert "art9" in config.process_managed_externally
        assert "Confluence" in config.process_managed_externally["art9"]
        assert config.has_config is True

    def test_empty_process_managed(self, tmp_path):
        config_data = {"process_managed_externally": {}}
        config_file = tmp_path / ".compliancelintrc"
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        config = ProjectConfig.load(str(tmp_path))
        assert config.process_managed_externally == {}


class TestFullConfig:
    """Test a full config file with all fields."""

    def test_full_config(self, tmp_path):
        config_data = {
            "skip_articles": [5],
            "process_managed_externally": {
                "art9": "Risk assessment managed in Confluence",
            },
            "custom_source_dirs": ["src/", "lib/"],
            "custom_test_dirs": ["spec/", "__tests__/"],
            "risk_classification_override": "not_high_risk",
        }
        config_file = tmp_path / ".compliancelintrc"
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        config = ProjectConfig.load(str(tmp_path))
        assert config.skip_articles == [5]
        assert config.process_managed_externally["art9"] == "Risk assessment managed in Confluence"
        assert config.custom_source_dirs == ["src/", "lib/"]
        assert config.custom_test_dirs == ["spec/", "__tests__/"]
        assert config.risk_classification_override == "not_high_risk"
        assert config.has_config is True

    def test_partial_config_only_sets_given_fields(self, tmp_path):
        """Fields not in the config file should use defaults."""
        config_data = {"skip_articles": [12]}
        config_file = tmp_path / ".compliancelintrc"
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        config = ProjectConfig.load(str(tmp_path))
        assert config.skip_articles == [12]
        assert config.process_managed_externally == {}
        assert config.custom_source_dirs == []
        assert config.risk_classification_override == ""
