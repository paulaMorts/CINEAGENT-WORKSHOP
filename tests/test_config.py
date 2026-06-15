"""Unit tests for the configuration module."""

import os
from unittest.mock import patch

import pytest

from app.config import AppConfig, load_config


class TestLoadConfigSuccess:
    """Test that load_config returns AppConfig when all vars are set."""

    def test_returns_config_with_all_vars_set(self):
        env = {
            "OMDB_API_KEY": "test-key-123",
            "AWS_REGION": "us-east-1",
            "BEDROCK_MODEL_ID": "anthropic.claude-3-sonnet-20240229-v1:0",
            "AGENTCORE_RUNTIME_ARN": "arn:aws:bedrock-agentcore:us-east-1:123456789:agent/abc123",
            "AGENTCORE_REGION": "us-east-1",
            "MEMORY_ID": "mem-abc123def456",
            "GATEWAY_URL": "https://gw-id.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
            "GATEWAY_ACCESS_TOKEN": "test-token-xyz",
        }
        with patch("app.config.load_dotenv"):
            with patch.dict(os.environ, env, clear=True):
                config = load_config()

        assert isinstance(config, AppConfig)
        assert config.omdb_api_key == "test-key-123"
        assert config.aws_region == "us-east-1"
        assert config.bedrock_model_id == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert config.agentcore_runtime_arn == "arn:aws:bedrock-agentcore:us-east-1:123456789:agent/abc123"
        assert config.agentcore_region == "us-east-1"
        assert config.memory_id == "mem-abc123def456"
        assert config.gateway_url == "https://gw-id.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
        assert config.gateway_access_token == "test-token-xyz"


class TestLoadConfigMissingVars:
    """Test that load_config exits when required vars are missing."""

    def test_exits_when_omdb_api_key_missing(self):
        env = {
            "AWS_REGION": "us-east-1",
            "BEDROCK_MODEL_ID": "anthropic.claude-3-sonnet-20240229-v1:0",
        }
        with patch("app.config.load_dotenv"):
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(SystemExit) as exc_info:
                    load_config()
        assert exc_info.value.code == 1

    def test_exits_when_aws_region_missing(self):
        env = {
            "OMDB_API_KEY": "test-key",
            "BEDROCK_MODEL_ID": "anthropic.claude-3-sonnet-20240229-v1:0",
        }
        with patch("app.config.load_dotenv"):
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(SystemExit) as exc_info:
                    load_config()
        assert exc_info.value.code == 1

    def test_exits_when_bedrock_model_id_missing(self):
        env = {
            "OMDB_API_KEY": "test-key",
            "AWS_REGION": "us-east-1",
        }
        with patch("app.config.load_dotenv"):
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(SystemExit) as exc_info:
                    load_config()
        assert exc_info.value.code == 1

    def test_exits_when_all_vars_missing(self):
        with patch("app.config.load_dotenv"):
            with patch.dict(os.environ, {}, clear=True):
                with pytest.raises(SystemExit) as exc_info:
                    load_config()
        assert exc_info.value.code == 1


class TestLoadConfigEmptyVars:
    """Test that load_config exits when required vars are empty strings."""

    def test_exits_when_omdb_api_key_empty(self):
        env = {
            "OMDB_API_KEY": "",
            "AWS_REGION": "us-east-1",
            "BEDROCK_MODEL_ID": "model-id",
        }
        with patch("app.config.load_dotenv"):
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(SystemExit) as exc_info:
                    load_config()
        assert exc_info.value.code == 1

    def test_exits_when_aws_region_empty(self):
        env = {
            "OMDB_API_KEY": "key",
            "AWS_REGION": "",
            "BEDROCK_MODEL_ID": "model-id",
        }
        with patch("app.config.load_dotenv"):
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(SystemExit) as exc_info:
                    load_config()
        assert exc_info.value.code == 1

    def test_exits_when_bedrock_model_id_empty(self):
        env = {
            "OMDB_API_KEY": "key",
            "AWS_REGION": "us-east-1",
            "BEDROCK_MODEL_ID": "",
        }
        with patch("app.config.load_dotenv"):
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(SystemExit) as exc_info:
                    load_config()
        assert exc_info.value.code == 1


class TestLoadConfigLogsError:
    """Test that load_config logs an error for each missing variable."""

    def test_logs_error_for_missing_var(self, caplog):
        env = {
            "AWS_REGION": "us-east-1",
            "BEDROCK_MODEL_ID": "model-id",
        }
        with patch("app.config.load_dotenv"):
            with patch.dict(os.environ, env, clear=True):
                import logging

                with caplog.at_level(logging.ERROR, logger="app.config"):
                    with pytest.raises(SystemExit):
                        load_config()

        assert "OMDB_API_KEY" in caplog.text

    def test_logs_error_for_multiple_missing_vars(self, caplog):
        with patch("app.config.load_dotenv"):
            with patch.dict(os.environ, {}, clear=True):
                import logging

                with caplog.at_level(logging.ERROR, logger="app.config"):
                    with pytest.raises(SystemExit):
                        load_config()

        assert "OMDB_API_KEY" in caplog.text
        assert "AWS_REGION" in caplog.text
        assert "BEDROCK_MODEL_ID" in caplog.text
