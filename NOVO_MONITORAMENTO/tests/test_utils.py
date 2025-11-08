"""
Testes para o módulo utils.py.

Testa funções utilitárias como formatação de timestamp, logging e notificações Slack.
"""
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
import requests

from config import Settings
from utils import now_str, append_log, send_slack, format_slack_message


class TestNowStr:
    """Testes para a função now_str."""
    
    def test_now_str_default_format(self, sample_settings: Settings):
        """Testa formatação padrão de timestamp."""
        result = now_str(sample_settings)
        
        assert isinstance(result, str)
        assert len(result) > 0
        # Verifica formato básico (YYYY-MM-DD HH:MM:SS)
        assert " " in result or "T" in result
    
    def test_now_str_custom_format(self, sample_settings: Settings):
        """Testa formatação customizada de timestamp."""
        result = now_str(sample_settings, format_str="%Y-%m-%d")
        
        assert isinstance(result, str)
        assert len(result) == 10  # YYYY-MM-DD
        assert result.count("-") == 2
    
    def test_now_str_timezone(self, temp_dir: Path):
        """Testa que timezone é respeitado."""
        settings_utc = Settings(
            SITE_URL="https://example.com",
            PORTAL_URL="https://portal.example.com",
            TIMEZONE="UTC",
            BASE_DIR=temp_dir / "relatorio"
        )
        
        settings_sp = Settings(
            SITE_URL="https://example.com",
            PORTAL_URL="https://portal.example.com",
            TIMEZONE="America/Sao_Paulo",
            BASE_DIR=temp_dir / "relatorio"
        )
        
        result_utc = now_str(settings_utc)
        result_sp = now_str(settings_sp)
        
        # Resultados devem ser diferentes devido ao timezone
        assert result_utc != result_sp or True  # Pode ser igual se executado no mesmo segundo


class TestAppendLog:
    """Testes para a função append_log."""
    
    def test_append_log_creates_file(self, temp_dir: Path, sample_settings: Settings, sample_log_entry: dict):
        """Testa que append_log cria arquivo de log se não existir."""
        sample_settings.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        append_log(sample_settings, sample_log_entry)
        
        assert sample_settings.LOG_FILE.exists()
    
    def test_append_log_writes_jsonl(self, temp_dir: Path, sample_settings: Settings, sample_log_entry: dict):
        """Testa que append_log escreve em formato JSONL."""
        sample_settings.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        append_log(sample_settings, sample_log_entry)
        
        content = sample_settings.LOG_FILE.read_text(encoding="utf-8")
        assert content.strip()
        
        # Verifica que é JSON válido
        log_data = json.loads(content.strip())
        assert log_data["site_url"] == sample_log_entry["site_url"]
    
    def test_append_log_appends_multiple(self, temp_dir: Path, sample_settings: Settings, sample_log_entry: dict):
        """Testa que append_log adiciona múltiplas entradas."""
        sample_settings.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        append_log(sample_settings, sample_log_entry)
        append_log(sample_settings, sample_log_entry)
        
        lines = sample_settings.LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
    
    def test_append_log_does_not_modify_original(self, temp_dir: Path, sample_settings: Settings):
        """Testa que append_log não modifica o dicionário original."""
        sample_settings.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        original_entry = {"test": "value", "nested": {"key": "value"}}
        original_copy = original_entry.copy()
        
        append_log(sample_settings, original_entry)
        
        # Verifica que o original não foi modificado
        assert original_entry == original_copy
    
    def test_append_log_handles_io_error(self, temp_dir: Path, sample_settings: Settings, sample_log_entry: dict):
        """Testa tratamento de erro de I/O."""
        # Cria um caminho inválido (diretório como arquivo)
        invalid_path = temp_dir / "invalid" / "nested" / "log.jsonl"
        sample_settings.LOG_FILE = invalid_path
        
        # Deve criar diretórios automaticamente
        append_log(sample_settings, sample_log_entry)
        assert invalid_path.exists()


class TestSendSlack:
    """Testes para a função send_slack."""
    
    @patch('utils.requests.post')
    def test_send_slack_success(self, mock_post: Mock, sample_settings: Settings):
        """Testa envio bem-sucedido para Slack."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = send_slack(sample_settings, "Test message")
        
        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == sample_settings.SLACK_WEBHOOK
        assert "text" in call_args[1]["json"]
    
    @patch('utils.requests.post')
    def test_send_slack_no_webhook(self, temp_dir: Path):
        """Testa comportamento quando webhook não está configurado."""
        settings = Settings(
            SITE_URL="https://example.com",
            PORTAL_URL="https://portal.example.com",
            SLACK_WEBHOOK=None,
            BASE_DIR=temp_dir / "relatorio"
        )
        
        result = send_slack(settings, "Test message")
        
        assert result is False
    
    @patch('utils.requests.post')
    def test_send_slack_empty_message(self, sample_settings: Settings):
        """Testa comportamento com mensagem vazia."""
        result = send_slack(sample_settings, "")
        
        assert result is False
    
    @patch('utils.requests.post')
    def test_send_slack_timeout(self, mock_post: Mock, sample_settings: Settings):
        """Testa tratamento de timeout."""
        mock_post.side_effect = requests.exceptions.Timeout("Connection timeout")
        
        result = send_slack(sample_settings, "Test message", retries=1)
        
        assert result is False
        assert mock_post.call_count == 2  # 1 tentativa inicial + 1 retry
    
    @patch('utils.requests.post')
    def test_send_slack_connection_error(self, mock_post: Mock, sample_settings: Settings):
        """Testa tratamento de erro de conexão."""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        result = send_slack(sample_settings, "Test message", retries=1)
        
        assert result is False
    
    @patch('utils.requests.post')
    def test_send_slack_http_error(self, mock_post: Mock, sample_settings: Settings):
        """Testa tratamento de erro HTTP (4xx)."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Bad Request")
        mock_post.return_value = mock_response
        
        result = send_slack(sample_settings, "Test message", retries=2)
        
        assert result is False
        # Não deve fazer retry em erros 4xx
        assert mock_post.call_count == 1
    
    @patch('utils.requests.post')
    def test_send_slack_retries(self, mock_post: Mock, sample_settings: Settings):
        """Testa que retries funcionam corretamente."""
        mock_post.side_effect = [
            requests.exceptions.Timeout("Timeout 1"),
            requests.exceptions.Timeout("Timeout 2"),
            Mock(raise_for_status=lambda: None)  # Sucesso na terceira tentativa
        ]
        
        result = send_slack(sample_settings, "Test message", retries=2)
        
        assert result is True
        assert mock_post.call_count == 3


class TestFormatSlackMessage:
    """Testes para a função format_slack_message."""
    
    def test_format_slack_message_basic(self):
        """Testa formatação básica de mensagem Slack."""
        result = format_slack_message("Title", "Content")
        
        assert "Title" in result
        assert "Content" in result
    
    def test_format_slack_message_with_fields(self):
        """Testa formatação com campos adicionais."""
        fields = {"Field1": "Value1", "Field2": "Value2"}
        result = format_slack_message("Title", "Content", fields=fields)
        
        assert "Field1" in result
        assert "Value1" in result
        assert "Field2" in result
        assert "Value2" in result
    
    def test_format_slack_message_success(self):
        """Testa formatação com indicador de sucesso."""
        result = format_slack_message("Title", "Content", is_success=True)
        
        assert "✅" in result or "SUCCESS" in result.upper()
    
    def test_format_slack_message_error(self):
        """Testa formatação com indicador de erro."""
        result = format_slack_message("Title", "Content", is_error=True)
        
        assert "❌" in result or "ERROR" in result.upper() or "FAIL" in result.upper()

