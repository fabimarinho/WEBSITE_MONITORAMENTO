"""
Testes para o módulo ssl_check.py.

Testa verificação de certificados SSL/TLS.
"""
import socket
import ssl
from unittest.mock import Mock, patch, MagicMock

import pytest

from ssl_check import SSLChecker, check_ssl_certificate, DEFAULT_EXPIRATION_WARNING_DAYS


class TestSSLChecker:
    """Testes para a classe SSLChecker."""
    
    def test_ssl_checker_initialization(self):
        """Testa inicialização do SSLChecker."""
        checker = SSLChecker(expiration_warning_days=15, timeout=5)
        
        assert checker.expiration_warning_days == 15
        assert checker.timeout == 5
    
    def test_ssl_checker_defaults(self):
        """Testa valores padrão do SSLChecker."""
        checker = SSLChecker()
        
        assert checker.expiration_warning_days == DEFAULT_EXPIRATION_WARNING_DAYS
        assert checker.timeout == 10
    
    @patch('ssl_check.socket.create_connection')
    @patch('ssl_check.ssl.create_default_context')
    def test_check_ssl_certificate_success(self, mock_context, mock_connection):
        """Testa verificação bem-sucedida de certificado SSL."""
        from datetime import datetime, timedelta
        
        # Mock do certificado com datas válidas
        future_date = datetime.now() + timedelta(days=90)
        not_after = future_date.strftime("%b %d %H:%M:%S %Y GMT")
        not_before = datetime.now().strftime("%b %d %H:%M:%S %Y GMT")
        
        mock_cert = {
            'subject': [('CN', 'example.com')],
            'issuer': [('CN', 'Test CA')],
            'notBefore': not_before,
            'notAfter': not_after,
            'serialNumber': '123456',
            'version': 3,
            'subjectAltName': []
        }
        
        # Mock do socket SSL
        mock_ssock = MagicMock()
        mock_ssock.getpeercert.return_value = mock_cert
        mock_ssock.getpeercert.return_value = mock_cert
        mock_ssock.cipher.return_value = ('TLS_AES_256_GCM_SHA384', 'TLSv1.3', 256)
        mock_ssock.version.return_value = 'TLSv1.3'
        mock_ssock.__enter__ = Mock(return_value=mock_ssock)
        mock_ssock.__exit__ = Mock(return_value=False)
        
        # Mock do socket normal
        mock_sock = MagicMock()
        mock_sock.__enter__ = Mock(return_value=mock_sock)
        mock_sock.__exit__ = Mock(return_value=False)
        
        mock_connection.return_value = mock_sock
        mock_ssl_context = MagicMock()
        mock_ssl_context.wrap_socket.return_value = mock_ssock
        mock_context.return_value = mock_ssl_context
        
        checker = SSLChecker()
        result = checker.check_ssl_certificate("https://example.com")
        
        assert result["ok_ssl"] is True
        assert "ssl_detail" in result
        assert "expiration" in result["ssl_detail"]
    
    def test_check_ssl_certificate_non_https(self):
        """Testa comportamento com URL não HTTPS."""
        checker = SSLChecker()
        result = checker.check_ssl_certificate("http://example.com")
        
        assert result["ok_ssl"] is False
        assert "error" in result["ssl_detail"]
    
    def test_check_ssl_certificate_invalid_url(self):
        """Testa comportamento com URL inválida."""
        checker = SSLChecker()
        result = checker.check_ssl_certificate("not-a-url")
        
        assert result["ok_ssl"] is False
        assert "error" in result["ssl_detail"]
    
    @patch('ssl_check.socket.create_connection')
    def test_check_ssl_certificate_timeout(self, mock_connection):
        """Testa tratamento de timeout."""
        mock_connection.side_effect = socket.timeout("Connection timeout")
        
        checker = SSLChecker()
        result = checker.check_ssl_certificate("https://example.com")
        
        assert result["ok_ssl"] is False
        assert "error" in result["ssl_detail"]
    
    @patch('ssl_check.socket.create_connection')
    @patch('ssl_check.ssl.create_default_context')
    def test_check_ssl_certificate_ssl_error(self, mock_context, mock_connection):
        """Testa tratamento de erro SSL."""
        mock_sock = MagicMock()
        mock_sock.__enter__ = Mock(return_value=mock_sock)
        mock_sock.__exit__ = Mock(return_value=False)
        mock_connection.return_value = mock_sock
        
        mock_ssl_context = MagicMock()
        mock_ssl_context.wrap_socket.side_effect = ssl.SSLError("SSL Error")
        mock_context.return_value = mock_ssl_context
        
        checker = SSLChecker()
        result = checker.check_ssl_certificate("https://example.com")
        
        assert result["ok_ssl"] is False
        assert "error" in result["ssl_detail"]
    
    def test_parse_cert_date_valid(self):
        """Testa parsing de data válida do certificado."""
        from datetime import datetime
        
        checker = SSLChecker()
        
        # Formato comum: "Jan 15 10:30:00 2024 GMT"
        date_str = "Jan 15 10:30:00 2024 GMT"
        result = checker._parse_cert_date(date_str)
        
        assert result is not None
        assert isinstance(result, datetime)  # Verifica se é um objeto datetime
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
    
    def test_parse_cert_date_invalid(self):
        """Testa parsing de data inválida."""
        from datetime import datetime
        
        checker = SSLChecker()
        
        result = checker._parse_cert_date("invalid date")
        
        # Deve retornar None para data inválida
        assert result is None
    
    def test_parse_cert_name(self):
        """Testa parsing de nome do certificado."""
        checker = SSLChecker()
        
        name_list = [('CN', 'example.com'), ('O', 'Test Org')]
        result = checker._parse_cert_name(name_list)
        
        assert result["CN"] == "example.com"
        assert result["O"] == "Test Org"


class TestCheckSSLCertificateFunction:
    """Testes para a função helper check_ssl_certificate."""
    
    @patch('ssl_check.SSLChecker.check_ssl_certificate')
    def test_check_ssl_certificate_function(self, mock_check):
        """Testa função helper check_ssl_certificate."""
        mock_check.return_value = {"ok_ssl": True, "ssl_detail": {}}
        
        result = check_ssl_certificate("https://example.com", expiration_warning_days=15)
        
        assert result["ok_ssl"] is True
        mock_check.assert_called_once_with("https://example.com")

