"""
Módulo de configuração do sistema de monitoramento.

Este módulo gerencia o carregamento e validação de configurações do sistema,
incluindo carregamento de variáveis de ambiente via python-dotenv.
"""
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Configuração de logging
logger = logging.getLogger(__name__)

# Constantes de valores padrão
DEFAULT_SUCCESS_ORG_LABEL = "PREFEITURA MUNICIPAL DE JAPERI"
DEFAULT_CHECK_INTERVAL_HOURS = 3
DEFAULT_CHECK_INTERVAL_MINUTES = 5
DEFAULT_TIMEZONE = "America/Sao_Paulo"
DEFAULT_DAILY_REPORT_HOUR = 23
DEFAULT_BASE_DIR_NAME = "relatorio"

# Valores mínimos e máximos para validação
MIN_CHECK_INTERVAL_MINUTES = 1
MAX_CHECK_INTERVAL_MINUTES = 60
MIN_CHECK_INTERVAL_HOURS = 1
MAX_CHECK_INTERVAL_HOURS = 24
MIN_DAILY_REPORT_HOUR = 0
MAX_DAILY_REPORT_HOUR = 23

# Configurações SSL/TLS
DEFAULT_SSL_EXPIRATION_WARNING_DAYS = 30  # Dias antes da expiração para alertar
MIN_SSL_EXPIRATION_WARNING_DAYS = 1
MAX_SSL_EXPIRATION_WARNING_DAYS = 365

# Configurações Dashboard
DEFAULT_DASHBOARD_PORT = 8080
MIN_DASHBOARD_PORT = 1024
MAX_DASHBOARD_PORT = 65535


@dataclass(frozen=True)
class Settings:
    """
    Configurações do sistema de monitoramento.
    
    Esta classe é imutável (frozen) para garantir que as configurações
    não sejam alteradas após a inicialização.
    
    Attributes:
        SITE_URL: URL do site a ser monitorado (obrigatório).
        PORTAL_URL: URL do portal a ser verificado (obrigatório).
        SUCCESS_ORG_LABEL: Label da organização para teste de sucesso.
        CHECK_INTERVAL_HOURS: Intervalo de verificação em horas.
        CHECK_INTERVAL_MINUTES: Intervalo de verificação em minutos.
        SLACK_WEBHOOK: URL do webhook do Slack para notificações (opcional).
        TIMEZONE: Timezone do sistema (padrão: America/Sao_Paulo).
        DAILY_REPORT_HOUR: Hora do dia para geração de relatório diário (0-23).
        SSL_EXPIRATION_WARNING_DAYS: Dias antes da expiração do certificado SSL para alertar (1-365).
        DASHBOARD_PORT: Porta do dashboard Flask (padrão: 8080).
        BASE_DIR: Diretório base para relatórios e logs.
        FAIL_DIR: Diretório para screenshots de falhas.
        DAILY_DIR: Diretório para relatórios diários.
        MONTHLY_DIR: Diretório para relatórios mensais.
        LOG_FILE: Caminho do arquivo de log.
        tz: Objeto ZoneInfo com o timezone configurado.
    
    Raises:
        ValueError: Se alguma configuração for inválida.
        OSError: Se não for possível criar os diretórios necessários.
    """
    
    SITE_URL: str
    PORTAL_URL: str
    SUCCESS_ORG_LABEL: str = DEFAULT_SUCCESS_ORG_LABEL
    CHECK_INTERVAL_HOURS: int = DEFAULT_CHECK_INTERVAL_HOURS
    CHECK_INTERVAL_MINUTES: int = DEFAULT_CHECK_INTERVAL_MINUTES
    SLACK_WEBHOOK: Optional[str] = None
    TIMEZONE: str = DEFAULT_TIMEZONE
    DAILY_REPORT_HOUR: int = DEFAULT_DAILY_REPORT_HOUR
    SSL_EXPIRATION_WARNING_DAYS: int = DEFAULT_SSL_EXPIRATION_WARNING_DAYS
    DASHBOARD_PORT: int = DEFAULT_DASHBOARD_PORT
    BASE_DIR: Path = field(default_factory=lambda: Path.cwd() / DEFAULT_BASE_DIR_NAME)
    FAIL_DIR: Path = field(init=False)
    DAILY_DIR: Path = field(init=False)
    MONTHLY_DIR: Path = field(init=False)
    LOG_FILE: Path = field(init=False)
    tz: ZoneInfo = field(init=False)
    
    def __post_init__(self) -> None:
        """
        Valida e inicializa configurações após a criação do objeto.
        
        Este método é chamado automaticamente pelo dataclass após a inicialização.
        Ele valida todas as configurações e cria os diretórios necessários.
        """
        # Valida URLs obrigatórias
        self._validate_urls()
        
        # Valida valores numéricos
        self._validate_numeric_values()
        
        # Valida configurações SSL
        self._validate_ssl_settings()
        
        # Valida webhook do Slack (se fornecido)
        self._validate_slack_webhook()
        
        # Valida timezone
        self._validate_timezone()
        
        # Inicializa diretórios derivados
        self._initialize_directories()
        
        # Cria diretórios necessários
        self._create_directories()
        
        logger.info(
            f"Configurações inicializadas: "
            f"SITE_URL={self.SITE_URL}, "
            f"PORTAL_URL={self.PORTAL_URL}, "
            f"TIMEZONE={self.TIMEZONE}"
        )
    
    def _validate_urls(self) -> None:
        """Valida se as URLs fornecidas são válidas."""
        if not self.SITE_URL or not self.SITE_URL.strip():
            raise ValueError("SITE_URL é obrigatório e não pode estar vazio")
        
        if not self.PORTAL_URL or not self.PORTAL_URL.strip():
            raise ValueError("PORTAL_URL é obrigatório e não pode estar vazio")
        
        # Valida formato das URLs
        try:
            site_parsed = urlparse(self.SITE_URL.strip())
            if not site_parsed.scheme or not site_parsed.netloc:
                raise ValueError(
                    f"SITE_URL inválida: deve ser uma URL completa "
                    f"(ex: https://example.com). Recebido: {self.SITE_URL}"
                )
        except Exception as e:
            raise ValueError(f"SITE_URL inválida: {e}") from e
        
        try:
            portal_parsed = urlparse(self.PORTAL_URL.strip())
            if not portal_parsed.scheme or not portal_parsed.netloc:
                raise ValueError(
                    f"PORTAL_URL inválida: deve ser uma URL completa "
                    f"(ex: https://example.com). Recebido: {self.PORTAL_URL}"
                )
        except Exception as e:
            raise ValueError(f"PORTAL_URL inválida: {e}") from e
        
        # Normaliza URLs (remove espaços)
        object.__setattr__(self, "SITE_URL", self.SITE_URL.strip())
        object.__setattr__(self, "PORTAL_URL", self.PORTAL_URL.strip())
    
    def _validate_numeric_values(self) -> None:
        """Valida valores numéricos dentro dos limites aceitáveis."""
        if not isinstance(self.CHECK_INTERVAL_MINUTES, int):
            raise TypeError(
                f"CHECK_INTERVAL_MINUTES deve ser um inteiro. "
                f"Recebido: {type(self.CHECK_INTERVAL_MINUTES)}"
            )
        
        if not (MIN_CHECK_INTERVAL_MINUTES <= self.CHECK_INTERVAL_MINUTES <= MAX_CHECK_INTERVAL_MINUTES):
            raise ValueError(
                f"CHECK_INTERVAL_MINUTES deve estar entre "
                f"{MIN_CHECK_INTERVAL_MINUTES} e {MAX_CHECK_INTERVAL_MINUTES}. "
                f"Recebido: {self.CHECK_INTERVAL_MINUTES}"
            )
        
        if not isinstance(self.CHECK_INTERVAL_HOURS, int):
            raise TypeError(
                f"CHECK_INTERVAL_HOURS deve ser um inteiro. "
                f"Recebido: {type(self.CHECK_INTERVAL_HOURS)}"
            )
        
        if not (MIN_CHECK_INTERVAL_HOURS <= self.CHECK_INTERVAL_HOURS <= MAX_CHECK_INTERVAL_HOURS):
            raise ValueError(
                f"CHECK_INTERVAL_HOURS deve estar entre "
                f"{MIN_CHECK_INTERVAL_HOURS} e {MAX_CHECK_INTERVAL_HOURS}. "
                f"Recebido: {self.CHECK_INTERVAL_HOURS}"
            )
        
        if not isinstance(self.DAILY_REPORT_HOUR, int):
            raise TypeError(
                f"DAILY_REPORT_HOUR deve ser um inteiro. "
                f"Recebido: {type(self.DAILY_REPORT_HOUR)}"
            )
        
        if not (MIN_DAILY_REPORT_HOUR <= self.DAILY_REPORT_HOUR <= MAX_DAILY_REPORT_HOUR):
            raise ValueError(
                f"DAILY_REPORT_HOUR deve estar entre "
                f"{MIN_DAILY_REPORT_HOUR} e {MAX_DAILY_REPORT_HOUR}. "
                f"Recebido: {self.DAILY_REPORT_HOUR}"
            )
        
        if not isinstance(self.DASHBOARD_PORT, int):
            raise TypeError(
                f"DASHBOARD_PORT deve ser um inteiro. "
                f"Recebido: {type(self.DASHBOARD_PORT)}"
            )
        
        if not (MIN_DASHBOARD_PORT <= self.DASHBOARD_PORT <= MAX_DASHBOARD_PORT):
            raise ValueError(
                f"DASHBOARD_PORT deve estar entre "
                f"{MIN_DASHBOARD_PORT} e {MAX_DASHBOARD_PORT}. "
                f"Recebido: {self.DASHBOARD_PORT}"
            )
    
    def _validate_ssl_settings(self) -> None:
        """Valida configurações SSL/TLS."""
        if not isinstance(self.SSL_EXPIRATION_WARNING_DAYS, int):
            raise TypeError(
                f"SSL_EXPIRATION_WARNING_DAYS deve ser um inteiro. "
                f"Recebido: {type(self.SSL_EXPIRATION_WARNING_DAYS)}"
            )
        
        if not (MIN_SSL_EXPIRATION_WARNING_DAYS <= self.SSL_EXPIRATION_WARNING_DAYS <= MAX_SSL_EXPIRATION_WARNING_DAYS):
            raise ValueError(
                f"SSL_EXPIRATION_WARNING_DAYS deve estar entre "
                f"{MIN_SSL_EXPIRATION_WARNING_DAYS} e {MAX_SSL_EXPIRATION_WARNING_DAYS}. "
                f"Recebido: {self.SSL_EXPIRATION_WARNING_DAYS}"
            )
    
    def _validate_slack_webhook(self) -> None:
        """Valida o formato da URL do webhook do Slack (se fornecido)."""
        if self.SLACK_WEBHOOK is not None:
            webhook = self.SLACK_WEBHOOK.strip()
            if not webhook:
                # Se vazio após strip, define como None
                object.__setattr__(self, "SLACK_WEBHOOK", None)
                return
            
            try:
                parsed = urlparse(webhook)
                if not parsed.scheme or not parsed.netloc:
                    raise ValueError(
                        f"SLACK_WEBHOOK inválida: deve ser uma URL completa. "
                        f"Recebido: {webhook}"
                    )
                
                # Valida se é uma URL do Slack
                if "slack.com" not in parsed.netloc and "hooks.slack.com" not in parsed.netloc:
                    logger.warning(
                        f"SLACK_WEBHOOK pode não ser uma URL válida do Slack: {webhook}"
                    )
                
                # Normaliza URL
                object.__setattr__(self, "SLACK_WEBHOOK", webhook)
            except Exception as e:
                raise ValueError(f"SLACK_WEBHOOK inválida: {e}") from e
    
    def _validate_timezone(self) -> None:
        """Valida e configura o timezone."""
        if not self.TIMEZONE or not self.TIMEZONE.strip():
            raise ValueError("TIMEZONE não pode estar vazio")
        
        try:
            tz = ZoneInfo(self.TIMEZONE.strip())
            object.__setattr__(self, "tz", tz)
            object.__setattr__(self, "TIMEZONE", self.TIMEZONE.strip())
        except Exception as e:
            raise ValueError(
                f"Timezone inválido: {self.TIMEZONE}. "
                f"Use um timezone válido da IANA timezone database "
                f"(ex: 'America/Sao_Paulo', 'UTC'). Erro: {e}"
            ) from e
    
    def _initialize_directories(self) -> None:
        """Inicializa os caminhos dos diretórios derivados."""
        object.__setattr__(self, "FAIL_DIR", self.BASE_DIR / "failures")
        object.__setattr__(self, "DAILY_DIR", self.BASE_DIR / "daily")
        object.__setattr__(self, "MONTHLY_DIR", self.BASE_DIR / "monthly")
        object.__setattr__(self, "LOG_FILE", self.BASE_DIR / "logs.jsonl")
    
    def _create_directories(self) -> None:
        """Cria os diretórios necessários se não existirem."""
        directories = (self.BASE_DIR, self.FAIL_DIR, self.DAILY_DIR, self.MONTHLY_DIR)
        
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Diretório verificado/criado: {directory}")
            except OSError as e:
                raise OSError(
                    f"Não foi possível criar o diretório {directory}: {e}"
                ) from e


def _get_env_int(
    key: str,
    default: int,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None
) -> int:
    """
    Obtém e valida um valor inteiro de uma variável de ambiente.
    
    Args:
        key: Nome da variável de ambiente.
        default: Valor padrão se a variável não existir.
        min_value: Valor mínimo permitido (opcional).
        max_value: Valor máximo permitido (opcional).
    
    Returns:
        Valor inteiro da variável de ambiente ou valor padrão.
    
    Raises:
        ValueError: Se o valor não puder ser convertido para inteiro ou
                   estiver fora dos limites.
    """
    value_str = os.getenv(key)
    if value_str is None:
        return default
    
    try:
        value = int(value_str.strip())
    except ValueError as e:
        raise ValueError(
            f"Variável de ambiente {key} deve ser um número inteiro. "
            f"Recebido: '{value_str}'"
        ) from e
    
    if min_value is not None and value < min_value:
        raise ValueError(
            f"Variável de ambiente {key} deve ser >= {min_value}. "
            f"Recebido: {value}"
        )
    
    if max_value is not None and value > max_value:
        raise ValueError(
            f"Variável de ambiente {key} deve ser <= {max_value}. "
            f"Recebido: {value}"
        )
    
    return value


def _get_env_str(key: str, default: str) -> str:
    """
    Obtém uma string de uma variável de ambiente.
    
    Args:
        key: Nome da variável de ambiente.
        default: Valor padrão se a variável não existir.
    
    Returns:
        Valor da variável de ambiente ou valor padrão (sem espaços).
    """
    value = os.getenv(key, default)
    return value.strip() if value else default


def load_settings(env_file: Optional[str] = None) -> Settings:
    """
    Carrega as configurações do sistema a partir de variáveis de ambiente.
    
    Carrega variáveis de ambiente de um arquivo .env (se existir) e do ambiente,
    validando e criando uma instância de Settings.
    
    Args:
        env_file: Caminho opcional para o arquivo .env. Se None, usa o padrão
                 do python-dotenv (procura por .env no diretório atual e pais).
    
    Returns:
        Instância de Settings com as configurações carregadas e validadas.
    
    Raises:
        ValueError: Se alguma configuração obrigatória estiver faltando ou
                   for inválida.
        OSError: Se não for possível criar os diretórios necessários.
    
    Example:
        ```python
        # Carrega do arquivo .env padrão
        settings = load_settings()
        
        # Carrega de um arquivo específico
        settings = load_settings(".env.production")
        ```
    """
    # Carrega variáveis de ambiente do arquivo .env
    env_path = load_dotenv(env_file)
    
    if env_path:
        logger.info(f"Variáveis de ambiente carregadas de: {env_path}")
    else:
        logger.debug("Nenhum arquivo .env encontrado, usando apenas variáveis de ambiente")
    
    # Obtém variáveis de ambiente com validação
    try:
        site_url = _get_env_str("SITE_URL", "")
        portal_url = _get_env_str("PORTAL_URL", "")
        
        if not site_url:
            raise ValueError(
                "SITE_URL é obrigatório. "
                "Defina a variável de ambiente SITE_URL ou adicione-a ao arquivo .env"
            )
        
        if not portal_url:
            raise ValueError(
                "PORTAL_URL é obrigatório. "
                "Defina a variável de ambiente PORTAL_URL ou adicione-a ao arquivo .env"
            )
        
        settings = Settings(
            SITE_URL=site_url,
            PORTAL_URL=portal_url,
            SUCCESS_ORG_LABEL=_get_env_str(
                "SUCCESS_ORG_LABEL",
                DEFAULT_SUCCESS_ORG_LABEL
            ),
            CHECK_INTERVAL_HOURS=_get_env_int(
                "CHECK_INTERVAL_HOURS",
                DEFAULT_CHECK_INTERVAL_HOURS,
                min_value=MIN_CHECK_INTERVAL_HOURS,
                max_value=MAX_CHECK_INTERVAL_HOURS
            ),
            CHECK_INTERVAL_MINUTES=_get_env_int(
                "CHECK_INTERVAL_MINUTES",
                DEFAULT_CHECK_INTERVAL_MINUTES,
                min_value=MIN_CHECK_INTERVAL_MINUTES,
                max_value=MAX_CHECK_INTERVAL_MINUTES
            ),
            SLACK_WEBHOOK=os.getenv("SLACK_WEBHOOK", "").strip() or None,
            TIMEZONE=_get_env_str("TIMEZONE", DEFAULT_TIMEZONE),
            DAILY_REPORT_HOUR=_get_env_int(
                "DAILY_REPORT_HOUR",
                DEFAULT_DAILY_REPORT_HOUR,
                min_value=MIN_DAILY_REPORT_HOUR,
                max_value=MAX_DAILY_REPORT_HOUR
            ),
            SSL_EXPIRATION_WARNING_DAYS=_get_env_int(
                "SSL_EXPIRATION_WARNING_DAYS",
                DEFAULT_SSL_EXPIRATION_WARNING_DAYS,
                min_value=MIN_SSL_EXPIRATION_WARNING_DAYS,
                max_value=MAX_SSL_EXPIRATION_WARNING_DAYS
            ),
        )
        
        logger.info("Configurações carregadas com sucesso")
        return settings
        
    except (ValueError, OSError) as e:
        logger.error(f"Erro ao carregar configurações: {e}")
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao carregar configurações: {e}", exc_info=True)
        raise ValueError(f"Erro ao carregar configurações: {e}") from e