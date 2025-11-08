"""
Módulo de verificação de certificados SSL/TLS.

Este módulo implementa verificações completas de certificados SSL/TLS,
incluindo validação, expiração, cadeia de certificados e informações de segurança.
"""
import logging
import socket
import ssl
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse

# Configuração de logging
logger = logging.getLogger(__name__)

# Constantes
DEFAULT_SSL_TIMEOUT = 10  # Segundos
DEFAULT_EXPIRATION_WARNING_DAYS = 30  # Dias antes da expiração para alertar
MIN_CERT_VALIDITY_DAYS = 7  # Mínimo de dias de validade para considerar seguro
SSL_PORT = 443
TLS_VERSION_MIN = ssl.PROTOCOL_TLSv1_2  # TLS 1.2 ou superior


class SSLChecker:
    """
    Classe responsável por verificar certificados SSL/TLS.
    
    Realiza verificações completas de certificados, incluindo:
    - Validade do certificado
    - Expiração e tempo restante
    - Cadeia de certificados
    - Informações do certificado (emissor, assunto, etc.)
    - Versão do protocolo TLS
    - Cipher suites
    """
    
    def __init__(
        self,
        expiration_warning_days: int = DEFAULT_EXPIRATION_WARNING_DAYS,
        timeout: int = DEFAULT_SSL_TIMEOUT
    ):
        """
        Inicializa o verificador SSL.
        
        Args:
            expiration_warning_days: Número de dias antes da expiração para alertar.
            timeout: Timeout em segundos para conexões SSL.
        """
        self.expiration_warning_days = expiration_warning_days
        self.timeout = timeout
        logger.debug(
            f"SSLChecker inicializado: "
            f"expiration_warning_days={expiration_warning_days}, "
            f"timeout={timeout}s"
        )
    
    def check_ssl_certificate(self, url: str) -> Dict[str, Any]:
        """
        Verifica o certificado SSL/TLS de uma URL.
        
        Args:
            url: URL a ser verificada (ex: https://example.com).
        
        Returns:
            Dict com informações sobre o certificado e status da verificação.
        """
        logger.info(f"Verificando certificado SSL/TLS para {url}")
        
        try:
            # Parse da URL
            parsed_url = urlparse(url)
            hostname = parsed_url.hostname
            port = parsed_url.port or SSL_PORT
            
            if not hostname:
                raise ValueError(f"URL inválida: não foi possível extrair hostname de {url}")
            
            # Verifica se é HTTPS
            if parsed_url.scheme and parsed_url.scheme.lower() != 'https':
                logger.warning(f"URL não é HTTPS: {url}")
                return {
                    "ok_ssl": False,
                    "ssl_detail": {
                        "error": "URL não é HTTPS",
                        "scheme": parsed_url.scheme
                    }
                }
            
            # Obtém informações do certificado
            cert_info = self._get_certificate_info(hostname, port)
            
            # Verifica validade
            validity = self._check_certificate_validity(cert_info)
            
            # Verifica expiração
            expiration_status = self._check_expiration(cert_info)
            
            # Verifica protocolo TLS
            tls_info = self._get_tls_info(hostname, port)
            
            # Compila resultado
            result = {
                "ok_ssl": validity["is_valid"] and expiration_status["is_ok"],
                "ssl_detail": {
                    "hostname": hostname,
                    "port": port,
                    "valid": validity["is_valid"],
                    "validity": validity,
                    "expiration": expiration_status,
                    "certificate": cert_info,
                    "tls": tls_info,
                }
            }
            
            if result["ok_ssl"]:
                logger.info(
                    f"Certificado SSL válido para {hostname}: "
                    f"expira em {expiration_status['days_until_expiration']} dias"
                )
            else:
                logger.warning(
                    f"Problemas detectados no certificado SSL para {hostname}: "
                    f"{expiration_status.get('warning', 'Certificado inválido')}"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao verificar certificado SSL para {url}: {e}", exc_info=True)
            return {
                "ok_ssl": False,
                "ssl_detail": {
                    "error": type(e).__name__,
                    "message": str(e)
                }
            }
    
    def _get_certificate_info(self, hostname: str, port: int) -> Dict[str, Any]:
        """
        Obtém informações do certificado SSL.
        
        Args:
            hostname: Nome do host.
            port: Porta do servidor.
        
        Returns:
            Dict com informações do certificado.
        """
        try:
            # Cria contexto SSL
            context = ssl.create_default_context()
            
            # Conecta ao servidor
            with socket.create_connection((hostname, port), timeout=self.timeout) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    # Obtém certificado
                    cert = ssock.getpeercert()
                    cert_binary = ssock.getpeercert(binary_form=True)
                    
                    # Obtém informações adicionais
                    cipher = ssock.cipher()
                    version = ssock.version()
                    
                    # Parse do certificado
                    cert_info = self._parse_certificate(cert, cert_binary)
                    
                    # Adiciona informações de cipher e TLS
                    cert_info["cipher"] = {
                        "name": cipher[0] if cipher else None,
                        "version": cipher[1] if cipher else None,
                        "bits": cipher[2] if cipher else None,
                    }
                    cert_info["tls_version"] = version
                    cert_info["protocol"] = version
                    
                    return cert_info
                    
        except socket.timeout:
            raise TimeoutError(f"Timeout ao conectar a {hostname}:{port}")
        except ssl.SSLError as e:
            raise ValueError(f"Erro SSL ao conectar a {hostname}:{port}: {e}")
        except Exception as e:
            raise RuntimeError(f"Erro ao obter certificado de {hostname}:{port}: {e}") from e
    
    def _parse_certificate(
        self,
        cert: Dict[str, Any],
        cert_binary: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Parse do certificado SSL.
        
        Args:
            cert: Dicionário com informações do certificado.
            cert_binary: Certificado em formato binário (opcional).
        
        Returns:
            Dict com informações parseadas do certificado.
        """
        try:
            # Parse de datas - o Python ssl retorna no formato "Jan 15 10:30:00 2024 GMT"
            not_before_str = cert.get('notBefore')
            not_after_str = cert.get('notAfter')
            
            not_before = self._parse_cert_date(not_before_str) if not_before_str else None
            not_after = self._parse_cert_date(not_after_str) if not_after_str else None
            
            # Parse de assunto e emissor
            subject = self._parse_cert_name(cert.get('subject', []))
            issuer = self._parse_cert_name(cert.get('issuer', []))
            
            # Informações do certificado
            cert_info = {
                "subject": subject,
                "issuer": issuer,
                "serial_number": cert.get('serialNumber'),
                "version": cert.get('version'),
                "not_before": not_before.isoformat() if not_before else None,
                "not_after": not_after.isoformat() if not_after else None,
                "not_before_timestamp": not_before.timestamp() if not_before else None,
                "not_after_timestamp": not_after.timestamp() if not_after else None,
                "subject_alt_name": cert.get('subjectAltName', []),
                # Mantém strings originais para referência
                "not_before_raw": not_before_str,
                "not_after_raw": not_after_str,
            }
            
            return cert_info
            
        except Exception as e:
            logger.error(f"Erro ao fazer parse do certificado: {e}", exc_info=True)
            raise
    
    def _parse_cert_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse de data do certificado SSL.
        
        Args:
            date_str: String de data no formato do certificado.
        
        Returns:
            Datetime object ou None.
        """
        if not date_str:
            return None
        
        try:
            # Formato comum do Python ssl: "Jan 15 10:30:00 2024 GMT"
            # O formato pode variar, então tentamos diferentes abordagens
            if isinstance(date_str, bytes):
                date_str = date_str.decode('utf-8', errors='ignore')
            
            # Remove espaços extras
            date_str = date_str.strip()
            
            # Tenta diferentes formatos comuns
            formats = [
                "%b %d %H:%M:%S %Y %Z",      # Jan 15 10:30:00 2024 GMT
                "%b %d %H:%M:%S %Y GMT",     # Jan 15 10:30:00 2024 GMT (sem timezone no parse)
                "%b  %d %H:%M:%S %Y %Z",     # Jan  15 10:30:00 2024 GMT (dois espaços)
                "%Y%m%d%H%M%SZ",             # ASN.1 format: 20240115103000Z
                "%Y-%m-%d %H:%M:%S",         # ISO format
                "%Y-%m-%dT%H:%M:%SZ",        # ISO format with T
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt
                except ValueError:
                    continue
            
            # Tenta usar dateutil se disponível (mais flexível)
            try:
                from dateutil import parser
                return parser.parse(date_str)
            except ImportError:
                pass
            except Exception:
                pass
            
            # Última tentativa: parsing manual básico
            # Formato comum: "Jan 15 10:30:00 2024 GMT"
            parts = date_str.split()
            if len(parts) >= 4:
                try:
                    month_str = parts[0]
                    day_str = parts[1]
                    time_str = parts[2]
                    year_str = parts[3]
                    
                    # Mapeia mês
                    months = {
                        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4,
                        'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8,
                        'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
                    }
                    
                    if month_str in months:
                        month = months[month_str]
                        day = int(day_str)
                        year = int(year_str)
                        
                        # Parse do tempo
                        time_parts = time_str.split(':')
                        if len(time_parts) == 3:
                            hour = int(time_parts[0])
                            minute = int(time_parts[1])
                            second = int(time_parts[2])
                            
                            return datetime(year, month, day, hour, minute, second)
                except (ValueError, KeyError, IndexError):
                    pass
            
            # Se nenhum formato funcionou
            logger.warning(f"Formato de data não reconhecido: {date_str}")
            return None
            
        except Exception as e:
            logger.error(f"Erro ao fazer parse de data do certificado: {e}", exc_info=True)
            return None
    
    def _parse_cert_name(self, name_list: list) -> Dict[str, str]:
        """
        Parse de nome do certificado (subject ou issuer).
        
        Args:
            name_list: Lista de tuplas com informações do nome.
        
        Returns:
            Dict com informações do nome organizadas.
        """
        result = {}
        
        if not name_list:
            return result
        
        try:
            # name_list é uma lista de tuplas: [('CN', 'example.com'), ('O', 'Organization'), ...]
            if isinstance(name_list, list):
                for item in name_list:
                    if isinstance(item, tuple) and len(item) == 2:
                        key, value = item
                        result[key] = value
                    elif isinstance(item, list):
                        # Pode ser uma lista aninhada
                        for subitem in item:
                            if isinstance(subitem, tuple) and len(subitem) == 2:
                                key, value = subitem
                                result[key] = value
            
            return result
            
        except Exception as e:
            logger.warning(f"Erro ao fazer parse de nome do certificado: {e}")
            return {}
    
    def _check_certificate_validity(self, cert_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verifica a validade do certificado.
        
        Args:
            cert_info: Informações do certificado.
        
        Returns:
            Dict com informações sobre a validade.
        """
        now = datetime.now()
        not_before_str = cert_info.get("not_before")
        not_after_str = cert_info.get("not_after")
        
        # Tenta obter das timestamps primeiro (mais confiável)
        not_before_ts = cert_info.get("not_before_timestamp")
        not_after_ts = cert_info.get("not_after_timestamp")
        
        if not_before_ts and not_after_ts:
            try:
                not_before_dt = datetime.fromtimestamp(not_before_ts)
                not_after_dt = datetime.fromtimestamp(not_after_ts)
            except (ValueError, OSError, OverflowError):
                not_before_dt = None
                not_after_dt = None
        else:
            not_before_dt = None
            not_after_dt = None
        
        # Se não conseguiu das timestamps, tenta parse das strings
        if not not_before_dt and not_before_str:
            not_before_dt = self._parse_cert_date(not_before_str)
        
        if not not_after_dt and not_after_str:
            not_after_dt = self._parse_cert_date(not_after_str)
        
        if not not_before_dt or not not_after_dt:
            return {
                "is_valid": False,
                "error": "Datas de validade não disponíveis ou inválidas"
            }
        
        try:
            is_valid = not_before_dt <= now <= not_after_dt
            
            return {
                "is_valid": is_valid,
                "not_before": not_before_dt.isoformat(),
                "not_after": not_after_dt.isoformat(),
                "current_time": now.isoformat(),
                "is_not_yet_valid": now < not_before_dt,
                "is_expired": now > not_after_dt,
            }
            
        except Exception as e:
            logger.error(f"Erro ao verificar validade do certificado: {e}", exc_info=True)
            return {
                "is_valid": False,
                "error": str(e)
            }
    
    def _check_expiration(self, cert_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verifica a expiração do certificado.
        
        Args:
            cert_info: Informações do certificado.
        
        Returns:
            Dict com informações sobre expiração.
        """
        now = datetime.now()
        not_after_str = cert_info.get("not_after")
        
        # Tenta obter da timestamp primeiro (mais confiável)
        not_after_ts = cert_info.get("not_after_timestamp")
        
        if not_after_ts:
            try:
                not_after_dt = datetime.fromtimestamp(not_after_ts)
            except (ValueError, OSError, OverflowError):
                not_after_dt = None
        else:
            not_after_dt = None
        
        # Se não conseguiu da timestamp, tenta parse da string
        if not not_after_dt and not_after_str:
            not_after_dt = self._parse_cert_date(not_after_str)
        
        if not not_after_dt:
            return {
                "is_ok": False,
                "error": "Data de expiração não disponível ou inválida"
            }
        
        try:
            # Calcula dias até expiração
            delta = not_after_dt - now
            days_until_expiration = delta.days
            
            # Calcula também horas para precisão
            total_seconds = delta.total_seconds()
            hours_until_expiration = int(total_seconds / 3600)
            
            # Verifica se está expirado
            is_expired = days_until_expiration < 0
            
            # Verifica se está próximo da expiração
            is_expiring_soon = 0 <= days_until_expiration <= self.expiration_warning_days
            
            # Verifica se tem validade mínima
            has_min_validity = days_until_expiration >= MIN_CERT_VALIDITY_DAYS
            
            # Status geral
            is_ok = not is_expired and has_min_validity and not is_expiring_soon
            
            # Mensagens de warning
            warnings = []
            if is_expired:
                warnings.append(f"Certificado expirado há {abs(days_until_expiration)} dias")
            elif is_expiring_soon:
                if days_until_expiration == 0:
                    warnings.append(f"Certificado expira hoje (em {hours_until_expiration} horas)")
                else:
                    warnings.append(f"Certificado expira em {days_until_expiration} dias")
            if not has_min_validity and not is_expired:
                warnings.append(f"Certificado tem menos de {MIN_CERT_VALIDITY_DAYS} dias de validade")
            
            return {
                "is_ok": is_ok,
                "is_expired": is_expired,
                "is_expiring_soon": is_expiring_soon,
                "has_min_validity": has_min_validity,
                "days_until_expiration": days_until_expiration,
                "hours_until_expiration": hours_until_expiration,
                "expiration_date": not_after_dt.isoformat(),
                "warning": warnings[0] if warnings else None,
                "warnings": warnings,
            }
            
        except Exception as e:
            logger.error(f"Erro ao verificar expiração do certificado: {e}", exc_info=True)
            return {
                "is_ok": False,
                "error": str(e)
            }
    
    def _get_tls_info(self, hostname: str, port: int) -> Dict[str, Any]:
        """
        Obtém informações sobre o protocolo TLS.
        
        Args:
            hostname: Nome do host.
            port: Porta do servidor.
        
        Returns:
            Dict com informações do TLS.
        """
        try:
            context = ssl.create_default_context()
            
            with socket.create_connection((hostname, port), timeout=self.timeout) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    version = ssock.version()
                    cipher = ssock.cipher()
                    
                    # Verifica versão mínima recomendada (TLS 1.2+)
                    is_secure_version = version in ['TLSv1.2', 'TLSv1.3']
                    
                    return {
                        "version": version,
                        "is_secure_version": is_secure_version,
                        "cipher_suite": cipher[0] if cipher else None,
                        "cipher_version": cipher[1] if cipher else None,
                        "cipher_bits": cipher[2] if cipher else None,
                    }
                    
        except Exception as e:
            logger.warning(f"Erro ao obter informações TLS: {e}")
            return {
                "error": str(e)
            }


def check_ssl_certificate(
    url: str,
    expiration_warning_days: int = DEFAULT_EXPIRATION_WARNING_DAYS
) -> Dict[str, Any]:
    """
    Função helper para verificar certificado SSL/TLS.
    
    Args:
        url: URL a ser verificada.
        expiration_warning_days: Dias antes da expiração para alertar.
    
    Returns:
        Dict com informações sobre o certificado.
    """
    checker = SSLChecker(expiration_warning_days=expiration_warning_days)
    return checker.check_ssl_certificate(url)

