"""
Testes para o módulo check.py.

Testa verificações HTTP, SSL e Playwright.
"""
from unittest.mock import Mock, patch, MagicMock

import pytest
import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from pathlib import Path

from check import SiteChecker
from config import Settings


class TestSiteChecker:
    """Testes para a classe SiteChecker."""
    
    def test_site_checker_initialization(self, sample_settings: Settings):
        """Testa inicialização do SiteChecker."""
        checker = SiteChecker(sample_settings)
        
        assert checker.settings == sample_settings
        assert checker.ssl_checker is not None
    
    def test_site_checker_invalid_settings(self, temp_dir: Path):
        """Testa validação de configurações inválidas."""
        with pytest.raises(ValueError, match="SITE_URL é obrigatório e não pode estar vazio"):
            Settings(
                SITE_URL="",  # URL vazia
                PORTAL_URL="https://portal.example.com",
                SUCCESS_ORG_LABEL="Test Organization",
                BASE_DIR=temp_dir / "relatorio"
            )
    
    @patch('check.SSLChecker.check_ssl_certificate')
    @patch('check.requests.get')
    @patch('check.sync_playwright')
    @patch('check.time.time')
    def test_perform_check_success(
        self,
        mock_time,
        mock_playwright,
        mock_requests_get,
        mock_ssl_check,
        sample_settings: Settings
    ):
        """Testa verificação completa bem-sucedida."""
        # Mock time
        mock_time.side_effect = [0.0, 0.1, 0.5, 0.0, 1.5, 2.0]  # HTTP: start, ttfb, end; Playwright: nav_start, nav_end, interaction_end
        
        # Mock SSL
        mock_ssl_check.return_value = {
            "ok_ssl": True,
            "ssl_detail": {"expiration": {"days_until_expiration": 100}}
        }
        
        # Mock HTTP
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.5
        mock_response.url = "https://example.com"
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.iter_content.return_value = iter([b"<html>test</html>"])
        mock_requests_get.return_value = mock_response
        
        # Mock Playwright
        mock_page = Mock()
        mock_page.goto.return_value = None
        mock_locator = Mock()
        mock_locator.wait_for.return_value = None
        mock_locator.select_option.return_value = None
        mock_locator.first = mock_locator
        mock_locator.click.return_value = None
        mock_page.locator.return_value = mock_locator
        mock_page.evaluate.return_value = {
            "dns_time": 10,
            "tcp_time": 20,
            "ttfb": 100,
            "load_complete": 2000,
            "total_resources": 5,
            "total_resource_size": 100000
        }
        
        mock_browser = Mock()
        mock_browser.new_page.return_value = mock_page
        
        mock_playwright_instance = Mock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        
        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_playwright_instance)
        mock_context.__exit__ = Mock(return_value=False)
        mock_playwright.return_value = mock_context
        
        checker = SiteChecker(sample_settings)
        result = checker.perform_check()
        
        assert "ok_ssl" in result
        assert "ok_http" in result
        assert "ok_playwright" in result
        assert result["timestamp"] is not None
    
    @patch('check.requests.get')
    def test_do_http_check_success(self, mock_get, sample_settings: Settings):
        """Testa verificação HTTP bem-sucedida."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.5
        mock_response.url = "https://example.com"
        mock_response.iter_content.return_value = [b"<html>test</html>"]
        mock_get.return_value = mock_response
        
        checker = SiteChecker(sample_settings)
        result = checker._do_http_check()
        
        assert result["ok_http"] is True
        assert result["http_detail"]["status_code"] == 200
        assert "performance" in result["http_detail"]
        assert "ttfb" in result["http_detail"]["performance"]
    
    @patch('check.requests.get')
    def test_do_http_check_timeout(self, mock_get, sample_settings: Settings):
        """Testa tratamento de timeout HTTP."""
        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")
        
        checker = SiteChecker(sample_settings)
        result = checker._do_http_check()
        
        assert result["ok_http"] is False
        assert "error" in result["http_detail"]
    
    @patch('check.requests.get')
    def test_do_http_check_connection_error(self, mock_get, sample_settings: Settings):
        """Testa tratamento de erro de conexão HTTP."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        checker = SiteChecker(sample_settings)
        result = checker._do_http_check()
        
        assert result["ok_http"] is False
        assert result["http_detail"]["error"] == "Connection error"
    
    @patch('check.sync_playwright')
    def test_do_playwright_check_success(self, mock_playwright, sample_settings: Settings):
        """Testa verificação Playwright bem-sucedida."""
        
        mock_page = Mock()
        mock_page.goto.return_value = None
        mock_locator = Mock()
        mock_locator.wait_for.return_value = None
        mock_locator.select_option.return_value = None
        mock_locator.first = mock_locator
        mock_locator.click.return_value = None
        mock_page.locator.return_value = mock_locator
        mock_page.evaluate.return_value = {
            "dns_time": 10,
            "tcp_time": 20,
            "ttfb": 100,
            "load_complete": 2000,
            "total_resources": 5,
            "total_resource_size": 100000
        }
        
        mock_browser = Mock()
        mock_browser.new_page.return_value = mock_page
        
        mock_playwright_instance = Mock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        
        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_playwright_instance)
        mock_context.__exit__ = Mock(return_value=False)
        mock_playwright.return_value = mock_context
        
        checker = SiteChecker(sample_settings)
        result = checker._do_playwright_check()
        
        assert "ok_playwright" in result
        assert "playwright_detail" in result
        assert "performance" in result["playwright_detail"]
    
    @patch('check.sync_playwright')
    def test_do_playwright_check_timeout(self, mock_playwright, sample_settings: Settings):
        """Testa tratamento de timeout no Playwright."""
        mock_page = Mock()
        mock_page.goto.side_effect = PlaywrightTimeoutError("Page load timeout")
        
        mock_browser = Mock()
        mock_browser.new_page.return_value = mock_page
        
        mock_playwright_instance = Mock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        
        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_playwright_instance)
        mock_context.__exit__ = Mock(return_value=False)
        mock_playwright.return_value = mock_context
        
        checker = SiteChecker(sample_settings)
        result = checker._do_playwright_check()
        
        assert result["ok_playwright"] is False
        assert "error" in result["playwright_detail"]
    
    @patch('check.send_slack')
    def test_notify_failure(self, mock_send_slack, sample_settings: Settings):
        """Testa notificação de falha via Slack."""
        mock_send_slack.return_value = True
        
        result = {
            "site_url": "https://example.com",
            "timestamp": "2024-01-15 10:30:00",
            "ok_http": False,
            "ok_ssl": True,
            "ok_playwright": True,
            "http_detail": {"error": "Connection error"}
        }
        
        checker = SiteChecker(sample_settings)
        checker._notify_failure(result)
        
        mock_send_slack.assert_called_once()
        call_args = mock_send_slack.call_args[0]
        assert call_args[0] == sample_settings
        assert isinstance(call_args[1], str)
        assert "Problema detectado" in call_args[1]

