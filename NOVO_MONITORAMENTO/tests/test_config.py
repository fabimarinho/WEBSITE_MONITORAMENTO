"""
Testes para o módulo config.py.

Testa o carregamento, validação e inicialização de configurações.
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from config import (
    Settings,
    load_settings,
    DEFAULT_TIMEZONE,
    DEFAULT_CHECK_INTERVAL_HOURS,
    MIN_CHECK_INTERVAL_HOURS,
    MAX_CHECK_INTERVAL_HOURS,
)


class TestSettings:
    """Testes para a classe Settings."""
    
    def test_settings_creation(self, temp_dir: Path):
        """Testa criação básica de Settings."""
        settings = Settings(
            SITE_URL="https://example.com",
            PORTAL_URL="https://portal.example.com",
            BASE_DIR=temp_dir / "relatorio"
        )
        
        assert settings.SITE_URL == "https://example.com"
        assert settings.PORTAL_URL == "https://portal.example.com"
        assert settings.BASE_DIR == temp_dir / "relatorio"
    
    def test_settings_defaults(self, temp_dir: Path):
        """Testa valores padrão de Settings."""
        settings = Settings(
            SITE_URL="https://example.com",
            PORTAL_URL="https://portal.example.com",
            BASE_DIR=temp_dir / "relatorio"
        )
        
        assert settings.SUCCESS_ORG_LABEL == "PREFEITURA MUNICIPAL DE JAPERI"
        assert settings.CHECK_INTERVAL_HOURS == DEFAULT_CHECK_INTERVAL_HOURS
        assert settings.TIMEZONE == DEFAULT_TIMEZONE
    
    def test_settings_immutable(self, temp_dir: Path):
        """Testa que Settings é imutável (frozen)."""
        settings = Settings(
            SITE_URL="https://example.com",
            PORTAL_URL="https://portal.example.com",
            BASE_DIR=temp_dir / "relatorio"
        )
        
        with pytest.raises(Exception):  # frozen=True causa AttributeError
            settings.SITE_URL = "https://changed.com"
    
    def test_settings_directory_creation(self, temp_dir: Path):
        """Testa criação automática de diretórios."""
        settings = Settings(
            SITE_URL="https://example.com",
            PORTAL_URL="https://portal.example.com",
            BASE_DIR=temp_dir / "relatorio"
        )
        
        assert settings.FAIL_DIR.exists()
        assert settings.DAILY_DIR.exists()
        assert settings.MONTHLY_DIR.exists()
        assert settings.LOG_FILE.parent.exists()
    
    def test_settings_invalid_url(self, temp_dir: Path):
        """Testa validação de URL inválida."""
        with pytest.raises(ValueError, match="URL inválida"):
            Settings(
                SITE_URL="not-a-url",
                PORTAL_URL="https://portal.example.com",
                BASE_DIR=temp_dir / "relatorio"
            )
    
    def test_settings_invalid_interval(self, temp_dir: Path):
        """Testa validação de intervalo inválido."""
        with pytest.raises(ValueError, match="CHECK_INTERVAL_HOURS"):
            Settings(
                SITE_URL="https://example.com",
                PORTAL_URL="https://portal.example.com",
                CHECK_INTERVAL_HOURS=MAX_CHECK_INTERVAL_HOURS + 1,
                BASE_DIR=temp_dir / "relatorio"
            )
    
    def test_settings_invalid_timezone(self, temp_dir: Path):
        """Testa validação de timezone inválido."""
        with pytest.raises(ValueError, match="Timezone"):
            Settings(
                SITE_URL="https://example.com",
                PORTAL_URL="https://portal.example.com",
                TIMEZONE="Invalid/Timezone",
                BASE_DIR=temp_dir / "relatorio"
            )
    
    def test_settings_ssl_warning_days(self, temp_dir: Path):
        """Testa configuração de dias de aviso SSL."""
        settings = Settings(
            SITE_URL="https://example.com",
            PORTAL_URL="https://portal.example.com",
            SSL_EXPIRATION_WARNING_DAYS=15,
            BASE_DIR=temp_dir / "relatorio"
        )
        
        assert settings.SSL_EXPIRATION_WARNING_DAYS == 15


class TestLoadSettings:
    """Testes para a função load_settings."""
    
    def test_load_settings_from_env_file(self, sample_env_file: Path):
        """Testa carregamento de configurações de arquivo .env."""
        settings = load_settings(env_file=str(sample_env_file))
        
        assert settings.SITE_URL == "https://example.com"
        assert settings.PORTAL_URL == "https://portal.example.com"
        assert settings.SUCCESS_ORG_LABEL == "TEST ORG"
        assert settings.CHECK_INTERVAL_HOURS == 1
        assert settings.CHECK_INTERVAL_MINUTES == 10
    
    def test_load_settings_from_environment(self, temp_dir: Path):
        """Testa carregamento de configurações de variáveis de ambiente."""
        os.environ["SITE_URL"] = "https://env.example.com"
        os.environ["PORTAL_URL"] = "https://env.portal.example.com"
        
        settings = load_settings()
        
        assert settings.SITE_URL == "https://env.example.com"
        assert settings.PORTAL_URL == "https://env.portal.example.com"
    
    @patch('config.load_dotenv')
    def test_load_settings_required_vars(self, mock_load_dotenv, temp_dir: Path):
        """Testa que variáveis obrigatórias são necessárias."""
        # Mock load_dotenv para retornar True (sucesso)
        mock_load_dotenv.return_value = True
        
        # Salva as variáveis originais
        original_env = os.environ.copy()
        
        try:
            # Limpa TODAS as variáveis de ambiente
            os.environ.clear()
            
            # Testa sem SITE_URL e PORTAL_URL
            with pytest.raises(ValueError, match=r"SITE_URL é obrigatório"):
                load_settings()
            
            # Testa sem PORTAL_URL
            os.environ['SITE_URL'] = "https://example.com"
            with pytest.raises(ValueError, match=r"PORTAL_URL é obrigatório"):
                load_settings()
            
            # Testa sem SITE_URL
            os.environ.clear()
            os.environ['PORTAL_URL'] = "https://portal.example.com"
            with pytest.raises(ValueError, match=r"SITE_URL é obrigatório"):
                load_settings()
            
            # Testa que funciona com ambas as variáveis
            os.environ['SITE_URL'] = "https://example.com"
            os.environ['PORTAL_URL'] = "https://portal.example.com"
            settings = load_settings()
            assert settings.SITE_URL == "https://example.com"
            assert settings.PORTAL_URL == "https://portal.example.com"
        
        finally:
            # Restaura as variáveis originais
            os.environ.clear()
            os.environ.update(original_env)
    
    def test_load_settings_defaults(self, sample_env_file: Path):
        """Testa que valores padrão são usados quando não especificados."""
        # Remove algumas variáveis do arquivo de teste
        env_content = sample_env_file.read_text()
        env_content = env_content.replace("CHECK_INTERVAL_HOURS=1\n", "")
        sample_env_file.write_text(env_content)
        
        settings = load_settings(env_file=str(sample_env_file))
        
        assert settings.CHECK_INTERVAL_HOURS == DEFAULT_CHECK_INTERVAL_HOURS
    
    def test_load_settings_invalid_file(self, temp_dir: Path):
        """Testa comportamento com arquivo .env inválido."""
        invalid_file = temp_dir / "invalid.env"
        invalid_file.write_text("INVALID_CONTENT=test\n", encoding="utf-8")
        
        # Deve usar valores padrão ou variáveis de ambiente
        # Se não houver variáveis obrigatórias, deve falhar
        os.environ["SITE_URL"] = "https://example.com"
        os.environ["PORTAL_URL"] = "https://portal.example.com"
        
        settings = load_settings(env_file=str(invalid_file))
        assert settings.SITE_URL == "https://example.com"

