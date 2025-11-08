"""
Configuração compartilhada para testes pytest.

Este arquivo contém fixtures e configurações que são compartilhadas
entre todos os testes do projeto.
"""
import os
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, MagicMock

import pytest
from zoneinfo import ZoneInfo

from config import Settings, load_settings


@pytest.fixture
def temp_dir():
    """
    Cria um diretório temporário para testes.
    
    Yields:
        Path: Caminho do diretório temporário.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_env_file(temp_dir: Path) -> Path:
    """
    Cria um arquivo .env de exemplo para testes.
    
    Args:
        temp_dir: Diretório temporário.
    
    Returns:
        Path: Caminho do arquivo .env criado.
    """
    env_file = temp_dir / ".env"
    env_content = """SITE_URL=https://example.com
PORTAL_URL=https://portal.example.com
SUCCESS_ORG_LABEL=TEST ORG
CHECK_INTERVAL_HOURS=1
CHECK_INTERVAL_MINUTES=10
SLACK_WEBHOOK=https://hooks.slack.com/services/TEST/WEBHOOK
TIMEZONE=America/Sao_Paulo
DAILY_REPORT_HOUR=12
SSL_EXPIRATION_WARNING_DAYS=15
"""
    env_file.write_text(env_content, encoding="utf-8")
    return env_file


@pytest.fixture
def sample_settings(temp_dir: Path) -> Settings:
    """
    Cria uma instância de Settings para testes.
    
    Args:
        temp_dir: Diretório temporário.
    
    Returns:
        Settings: Instância de configurações de teste.
    """
    return Settings(
        SITE_URL="https://example.com",
        PORTAL_URL="https://portal.example.com",
        SUCCESS_ORG_LABEL="TEST ORG",
        CHECK_INTERVAL_HOURS=1,
        CHECK_INTERVAL_MINUTES=10,
        SLACK_WEBHOOK="https://hooks.slack.com/services/TEST/WEBHOOK",
        TIMEZONE="America/Sao_Paulo",
        DAILY_REPORT_HOUR=12,
        SSL_EXPIRATION_WARNING_DAYS=15,
        BASE_DIR=temp_dir / "relatorio"
    )


@pytest.fixture
def mock_requests(monkeypatch):
    """
    Mock para a biblioteca requests.
    
    Args:
        monkeypatch: Fixture do pytest para monkey patching.
    
    Returns:
        Mock: Mock do módulo requests.
    """
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.elapsed.total_seconds.return_value = 0.5
    mock_response.url = "https://example.com"
    mock_response.headers = {"Content-Type": "text/html"}
    mock_response.iter_content.return_value = [b"<html>test</html>"]
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=False)
    
    def mock_get(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr("requests.get", mock_get)
    return mock_response


@pytest.fixture
def mock_playwright(monkeypatch):
    """
    Mock para a biblioteca Playwright.
    
    Args:
        monkeypatch: Fixture do pytest para monkey patching.
    
    Returns:
        Mock: Mock do Playwright.
    """
    mock_page = Mock()
    mock_page.goto.return_value = None
    mock_page.locator.return_value = Mock()
    mock_page.evaluate.return_value = {
        "dns_time": 10,
        "tcp_time": 20,
        "ttfb": 100,
        "load_complete": 2000,
        "total_resources": 5,
        "total_resource_size": 100000
    }
    mock_page.screenshot.return_value = None
    
    mock_browser = Mock()
    mock_browser.new_page.return_value = mock_page
    mock_browser.close.return_value = None
    
    mock_playwright_instance = Mock()
    mock_playwright_instance.chromium.launch.return_value = mock_browser
    
    def mock_sync_playwright():
        context_manager = Mock()
        context_manager.__enter__ = Mock(return_value=mock_playwright_instance)
        context_manager.__exit__ = Mock(return_value=False)
        return context_manager
    
    monkeypatch.setattr("playwright.sync_api.sync_playwright", mock_sync_playwright)
    return mock_page


@pytest.fixture
def sample_log_entry() -> Dict[str, Any]:
    """
    Cria uma entrada de log de exemplo para testes.
    
    Returns:
        Dict: Entrada de log de exemplo.
    """
    return {
        "timestamp": "2024-01-15 10:30:00",
        "site_url": "https://example.com",
        "portal_url": "https://portal.example.com",
        "ok_ssl": True,
        "ok_http": True,
        "ok_playwright": True,
        "http_detail": {
            "status_code": 200,
            "elapsed": 0.5,
            "performance": {
                "ttfb": 0.1,
                "total_time": 0.5,
                "content_length": 1024
            }
        },
        "playwright_detail": {
            "messages": ["Test message"],
            "performance": {
                "navigation_time": 1.5,
                "load_complete_ms": 2000
            }
        }
    }


@pytest.fixture
def sample_logs(sample_log_entry: Dict[str, Any]) -> list:
    """
    Cria uma lista de logs de exemplo para testes.
    
    Args:
        sample_log_entry: Entrada de log de exemplo.
    
    Returns:
        List: Lista de logs de exemplo.
    """
    return [sample_log_entry]


@pytest.fixture(autouse=True)
def reset_env():
    """
    Reseta variáveis de ambiente antes de cada teste.
    
    Esta fixture é executada automaticamente antes de cada teste.
    """
    # Salva variáveis de ambiente originais
    original_env = dict(os.environ)
    
    yield
    
    # Restaura variáveis de ambiente
    os.environ.clear()
    os.environ.update(original_env)

