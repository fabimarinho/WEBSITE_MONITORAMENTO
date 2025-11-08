"""
Módulo de utilitários do sistema de monitoramento.

Este módulo fornece funções utilitárias para formatação de timestamps,
manipulação de logs e envio de notificações via Slack.
"""
import json
import logging
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    RequestException,
    Timeout,
)

from config import Settings

# Configuração de logging
logger = logging.getLogger(__name__)

# Constantes
DEFAULT_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S %Z"
DEFAULT_SLACK_TIMEOUT = 10  # Segundos
DEFAULT_SLACK_RETRIES = 2  # Número de tentativas em caso de falha
LOG_ENCODING = "utf-8"
JSON_ENSURE_ASCII = False


def now_str(settings: Settings, format_str: Optional[str] = None) -> str:
    """
    Retorna timestamp atual formatado usando o timezone das configurações.
    
    Args:
        settings: Configurações do sistema contendo o timezone.
        format_str: Formato customizado para o timestamp. Se None, usa o padrão.
    
    Returns:
        String com o timestamp formatado.
    
    Example:
        ```python
        timestamp = now_str(settings)
        # Retorna: "2024-01-15 10:30:00 BRT"
        ```
    """
    if format_str is None:
        format_str = DEFAULT_TIMESTAMP_FORMAT
    
    try:
        return datetime.now(settings.tz).strftime(format_str)
    except Exception as e:
        logger.error(f"Erro ao formatar timestamp: {e}", exc_info=True)
        # Fallback para UTC se houver erro
        return datetime.utcnow().strftime(format_str)


def append_log(settings: Settings, entry: Dict[str, Any]) -> None:
    """
    Adiciona uma entrada ao arquivo de log em formato JSONL (JSON Lines).
    
    A função cria uma cópia do dicionário de entrada para evitar modificar
    o objeto original, adiciona o timestamp de registro e escreve no arquivo
    de log em formato JSONL.
    
    Args:
        settings: Configurações do sistema contendo o caminho do arquivo de log.
        entry: Dicionário com os dados da entrada de log.
    
    Raises:
        OSError: Se não for possível criar ou escrever no arquivo de log.
        ValueError: Se a entrada não puder ser serializada para JSON.
    
    Note:
        A função não modifica o dicionário de entrada original. Uma cópia
        é criada antes de adicionar o campo 'recorded_at'.
    
    Example:
        ```python
        log_entry = {
            "timestamp": "2024-01-15 10:30:00",
            "ok_http": True,
            "ok_playwright": True
        }
        append_log(settings, log_entry)
        ```
    """
    try:
        # Cria uma cópia para não modificar o original
        log_entry = deepcopy(entry)
        
        # Adiciona timestamp de registro
        log_entry['recorded_at'] = now_str(settings)
        
        # Garante que o diretório existe
        settings.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Serializa para JSON
        try:
            json_line = json.dumps(log_entry, ensure_ascii=JSON_ENSURE_ASCII, default=str)
        except (TypeError, ValueError) as e:
            logger.error(f"Erro ao serializar entrada de log: {e}", exc_info=True)
            raise ValueError(f"Entrada de log não pode ser serializada para JSON: {e}") from e
        
        # Escreve no arquivo
        try:
            with open(settings.LOG_FILE, "a", encoding=LOG_ENCODING) as f:
                f.write(json_line + "\n")
            
            logger.debug(f"Entrada de log adicionada: {settings.LOG_FILE}")
            
        except OSError as e:
            logger.error(f"Erro ao escrever no arquivo de log {settings.LOG_FILE}: {e}", exc_info=True)
            raise
        
    except Exception as e:
        logger.error(f"Erro inesperado ao adicionar entrada de log: {e}", exc_info=True)
        raise


def send_slack(
    settings: Settings,
    text: str,
    timeout: int = DEFAULT_SLACK_TIMEOUT,
    retries: int = DEFAULT_SLACK_RETRIES
) -> bool:
    """
    Envia uma mensagem para o Slack via webhook.
    
    A função verifica se o webhook está configurado e envia a mensagem.
    Em caso de falha, tenta novamente até o número máximo de tentativas.
    
    Args:
        settings: Configurações do sistema contendo o webhook do Slack.
        text: Texto da mensagem a ser enviada.
        timeout: Timeout em segundos para a requisição (padrão: 10).
        retries: Número de tentativas em caso de falha (padrão: 2).
    
    Returns:
        True se a mensagem foi enviada com sucesso, False caso contrário.
    
    Note:
        Se o webhook não estiver configurado, a função apenas registra
        um aviso e retorna False, sem lançar exceção.
    
    Example:
        ```python
        success = send_slack(settings, "Alerta: Site indisponível")
        if not success:
            logger.warning("Falha ao enviar notificação para Slack")
        ```
    """
    # Verifica se o webhook está configurado
    if not settings.SLACK_WEBHOOK:
        logger.warning(
            "Webhook do Slack não configurado. Mensagem não enviada. "
            f"Conteúdo: {text[:100]}..." if len(text) > 100 else f"Conteúdo: {text}"
        )
        return False
    
    # Valida o texto da mensagem
    if not text or not text.strip():
        logger.warning("Tentativa de enviar mensagem vazia para Slack")
        return False
    
    # Tenta enviar a mensagem com retry
    last_exception = None
    
    for attempt in range(retries + 1):
        try:
            logger.debug(f"Enviando mensagem para Slack (tentativa {attempt + 1}/{retries + 1})")
            
            response = requests.post(
                settings.SLACK_WEBHOOK,
                json={"text": text},
                timeout=timeout,
                headers={"Content-Type": "application/json"}
            )
            
            # Verifica o status da resposta
            response.raise_for_status()
            
            logger.info("Mensagem enviada para Slack com sucesso")
            return True
            
        except Timeout:
            last_exception = Timeout(f"Timeout ao enviar mensagem para Slack após {timeout}s")
            logger.warning(
                f"Timeout ao enviar mensagem para Slack (tentativa {attempt + 1}/{retries + 1})"
            )
            if attempt < retries:
                continue
            
        except RequestsConnectionError as e:
            last_exception = e
            logger.warning(
                f"Erro de conexão ao enviar mensagem para Slack "
                f"(tentativa {attempt + 1}/{retries + 1}): {e}"
            )
            if attempt < retries:
                continue
            
        except RequestException as e:
            last_exception = e
            status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            
            if status_code:
                logger.error(
                    f"Erro HTTP {status_code} ao enviar mensagem para Slack "
                    f"(tentativa {attempt + 1}/{retries + 1}): {e}"
                )
            else:
                logger.error(
                    f"Erro na requisição ao enviar mensagem para Slack "
                    f"(tentativa {attempt + 1}/{retries + 1}): {e}"
                )
            
            # Não tenta novamente para erros HTTP 4xx (erros do cliente)
            if status_code and 400 <= status_code < 500:
                break
            
            if attempt < retries:
                continue
            
        except Exception as e:
            last_exception = e
            logger.error(
                f"Erro inesperado ao enviar mensagem para Slack "
                f"(tentativa {attempt + 1}/{retries + 1}): {e}",
                exc_info=True
            )
            if attempt < retries:
                continue
    
    # Se chegou aqui, todas as tentativas falharam
    logger.error(
        f"Falha ao enviar mensagem para Slack após {retries + 1} tentativa(s). "
        f"Último erro: {last_exception}",
        exc_info=last_exception
    )
    return False


def format_slack_message(
    title: str,
    content: str,
    fields: Optional[Dict[str, Any]] = None,
    color: Optional[str] = None
) -> str:
    """
    Formata uma mensagem para o Slack com estrutura organizada.
    
    Args:
        title: Título da mensagem.
        content: Conteúdo principal da mensagem.
        fields: Dicionário opcional com campos adicionais (chave: valor).
        color: Emoji ou indicador de cor (opcional).
    
    Returns:
        String formatada para envio ao Slack.
    
    Example:
        ```python
        message = format_slack_message(
            title="🚨 Alerta",
            content="Site indisponível",
            fields={"URL": "https://example.com", "Status": "500"},
            color="🔴"
        )
        send_slack(settings, message)
        ```
    """
    lines = []
    
    if color:
        lines.append(f"{color} {title}")
    else:
        lines.append(title)
    
    lines.append("")
    lines.append(content)
    
    if fields:
        lines.append("")
        lines.append("Detalhes:")
        for key, value in fields.items():
            lines.append(f"  • {key}: {value}")
    
    return "\n".join(lines)