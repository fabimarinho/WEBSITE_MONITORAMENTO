"""
Módulo de verificação de disponibilidade de sites.

Este módulo implementa verificações HTTP e de interface usando Playwright
para monitorar a disponibilidade e funcionalidade de sites.
"""
import logging
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import requests
from playwright.sync_api import (
    sync_playwright,
    Playwright,
    Browser,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)
from requests.exceptions import (
    RequestException,
    Timeout,
    ConnectionError as RequestsConnectionError,
)
from tenacity import retry, stop_after_attempt, wait_exponential

from config import Settings
from error_history import ErrorHistory, ErrorType, ErrorSeverity
from ssl_check import SSLChecker
from utils import now_str, append_log, send_slack

# Configuração de logging
logger = logging.getLogger(__name__)

# Constantes de configuração
DEFAULT_HTTP_TIMEOUT = 15
DEFAULT_PAGE_LOAD_TIMEOUT = 30000
DEFAULT_ELEMENT_TIMEOUT = 10000
DEFAULT_ORG_SELECT_TIMEOUT = 5000
DEFAULT_DOC_VIEWER_TIMEOUT = 10000
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_WAIT_MIN = 4
DEFAULT_RETRY_WAIT_MAX = 10

# Seletores CSS
SELECTOR_ORG_SELECT = '[data-testid="org-select"], select:has-text("Organização")'
SELECTOR_DOC_LIST = '[data-testid="doc-list"], .documents-list'
SELECTOR_DOC_LINK = '[data-testid="doc-link"], a:has-text("Visualizar")'
SELECTOR_DOC_VIEWER = 'iframe[src*="pdf"], embed[type="application/pdf"]'


class SiteChecker:
    """
    Classe responsável por realizar verificações de disponibilidade e funcionalidade de sites.
    
    Realiza três verificações principais:
    1. Verificação SSL/TLS (validade e expiração do certificado)
    2. Verificação HTTP básica (status code e tempo de resposta)
    3. Verificação funcional com Playwright (interação com elementos da página)
    """
    
    def __init__(self, settings: Settings):
        """
        Inicializa o SiteChecker com as configurações fornecidas.
        
        Args:
            settings: Instância de Settings com configurações do sistema.
            
        Raises:
            ValueError: Se as configurações não forem válidas.
        """
        self.settings = settings
        self._validate_settings()
        self.ssl_checker = SSLChecker(
            expiration_warning_days=getattr(settings, 'SSL_EXPIRATION_WARNING_DAYS', 30)
        )
        self.error_history = ErrorHistory(settings)
        logger.info(
            f"SiteChecker inicializado para {settings.SITE_URL} "
            f"(portal: {settings.PORTAL_URL})"
        )
    
    def _validate_settings(self) -> None:
        """Valida as configurações fornecidas."""
        if not self.settings.SITE_URL:
            raise ValueError("SITE_URL não pode estar vazio")
        if not self.settings.PORTAL_URL:
            raise ValueError("PORTAL_URL não pode estar vazio")
        if not self.settings.SUCCESS_ORG_LABEL:
            raise ValueError("SUCCESS_ORG_LABEL não pode estar vazio")
    
    @retry(
        stop=stop_after_attempt(DEFAULT_RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=1,
            min=DEFAULT_RETRY_WAIT_MIN,
            max=DEFAULT_RETRY_WAIT_MAX
        )
    )
    def perform_check(self) -> Dict[str, Any]:
        """
        Executa todas as verificações do site.
        
        Realiza verificações SSL/TLS, HTTP e com Playwright, registra os resultados
        e notifica em caso de falhas.
        
        Returns:
            Dict contendo os resultados das verificações com as chaves:
                - timestamp: Timestamp da verificação
                - site_url: URL do site verificado
                - portal_url: URL do portal verificado
                - ok_ssl: Boolean indicando sucesso da verificação SSL/TLS
                - ssl_detail: Detalhes da verificação SSL/TLS
                - ok_http: Boolean indicando sucesso da verificação HTTP
                - http_detail: Detalhes da verificação HTTP
                - ok_playwright: Boolean indicando sucesso da verificação Playwright
                - playwright_detail: Detalhes da verificação Playwright
                - screenshot: Caminho para screenshot em caso de falha (opcional)
        """
        timestamp = now_str(self.settings)
        logger.info(f"Iniciando verificação completa em {timestamp}")
        
        result: Dict[str, Any] = {
            "timestamp": timestamp,
            "site_url": self.settings.SITE_URL,
            "portal_url": self.settings.PORTAL_URL,
            "ok_http": False,
            "http_detail": None,
            "ok_ssl": False,
            "ssl_detail": None,
            "ok_playwright": False,
            "playwright_detail": None,
            "screenshot": None,
        }
        
        # Executa verificação SSL/TLS
        ssl_result = self._do_ssl_check()
        result.update(ssl_result)
        logger.debug(f"Resultado verificação SSL: {ssl_result}")
        
        # Executa verificação HTTP
        http_result = self._do_http_check()
        result.update(http_result)
        logger.debug(f"Resultado verificação HTTP: {http_result}")
        
        # Executa verificação Playwright
        playwright_result = self._do_playwright_check()
        result.update(playwright_result)
        logger.debug(f"Resultado verificação Playwright: {playwright_result}")
        
        # Registra resultado no log
        try:
            append_log(self.settings, result)
            logger.debug("Resultado registrado no log")
        except Exception as e:
            logger.error(f"Erro ao registrar log: {e}", exc_info=True)
        
        # Notifica em caso de falha
        if not result["ok_http"] or not result["ok_ssl"] or not result["ok_playwright"]:
            logger.warning("Falhas detectadas nas verificações")
            self._notify_failure(result)
        else:
            logger.info("Todas as verificações foram bem-sucedidas")
        
        return result
    
    def _do_ssl_check(self) -> Dict[str, Any]:
        """
        Realiza verificação SSL/TLS do site.
        
        Verifica a validade, expiração e informações do certificado SSL/TLS.
        
        Returns:
            Dict com chaves 'ok_ssl' e 'ssl_detail'.
        """
        logger.info(f"Executando verificação SSL/TLS para {self.settings.SITE_URL}")
        
        try:
            ssl_result = self.ssl_checker.check_ssl_certificate(self.settings.SITE_URL)
            
            # Registra erro no histórico se falhou
            if not ssl_result.get("ok_ssl"):
                error_detail = ssl_result.get("ssl_detail", {})
                error_message = error_detail.get("message", "SSL verification failed")
                
                self.error_history.record_error(
                    error_type=ErrorType.SSL_ERROR,
                    severity=ErrorSeverity.CRITICAL,
                    message=f"SSL certificate check failed: {error_message}",
                    details=error_detail,
                    ok_ssl=False,
                    ok_http=True,
                    ok_playwright=True,
                )
            
            return ssl_result
        except Exception as e:
            logger.error(f"Erro inesperado na verificação SSL: {e}", exc_info=True)
            
            # Registra erro no histórico
            self.error_history.record_error(
                error_type=ErrorType.SSL_ERROR,
                severity=ErrorSeverity.CRITICAL,
                message=f"Unexpected error in SSL check: {str(e)}",
                details={"error": str(e), "type": type(e).__name__},
                ok_ssl=False,
                ok_http=True,
                ok_playwright=True,
            )
            
            return {
                "ok_ssl": False,
                "ssl_detail": {
                    "error": "Unexpected error",
                    "message": str(e),
                    "type": type(e).__name__,
                }
            }
    
    def _do_http_check(self) -> Dict[str, Any]:
        """
        Realiza verificação HTTP básica do site com métricas de performance.
        
        Verifica se o site responde com status 200 e mede:
        - TTFB (Time To First Byte)
        - Tempo total de resposta
        - Tamanho da resposta
        
        Returns:
            Dict com chaves 'ok_http' e 'http_detail' incluindo métricas de performance.
        """
        logger.info(f"Executando verificação HTTP para {self.settings.SITE_URL}")
        
        try:
            # Mede TTFB manualmente
            start_time = time.time()
            
            response = requests.get(
                self.settings.SITE_URL,
                timeout=DEFAULT_HTTP_TIMEOUT,
                allow_redirects=True,
                stream=True  # Stream para medir TTFB
            )
            
            # Mede TTFB (tempo até primeiro byte)
            ttfb_start = time.time()
            # Lê primeiro chunk para garantir que recebeu o primeiro byte
            content = b''
            for chunk in response.iter_content(chunk_size=1):
                content = chunk
                break
            ttfb = time.time() - ttfb_start
            
            # Lê o resto da resposta
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
            
            # Tempo total
            total_time = time.time() - start_time
            elapsed_time = response.elapsed.total_seconds()
            
            # Tamanho da resposta
            content_length = len(content)
            headers_size = len(str(response.headers).encode('utf-8'))
            total_size = content_length + headers_size
            
            is_ok = response.status_code == 200
            
            # Calcula velocidade de download (bytes/segundo)
            download_speed = content_length / elapsed_time if elapsed_time > 0 else 0
            
            result = {
                "ok_http": is_ok,
                "http_detail": {
                    "status_code": response.status_code,
                    "elapsed": elapsed_time,
                    "url": response.url,
                    "performance": {
                        "ttfb": round(ttfb, 3),  # Time To First Byte em segundos
                        "total_time": round(total_time, 3),  # Tempo total da requisição
                        "response_time": round(elapsed_time, 3),  # Tempo de resposta (requests.elapsed)
                        "content_length": content_length,  # Tamanho do conteúdo em bytes
                        "total_size": total_size,  # Tamanho total (headers + content)
                        "download_speed": round(download_speed, 2),  # Velocidade em bytes/segundo
                        "download_speed_mbps": round(download_speed * 8 / 1_000_000, 2),  # Velocidade em Mbps
                    }
                }
            }
            
            if is_ok:
                logger.info(
                    f"Verificação HTTP bem-sucedida: "
                    f"status {response.status_code}, "
                    f"TTFB {ttfb:.3f}s, "
                    f"tempo total {elapsed_time:.2f}s, "
                    f"tamanho {content_length} bytes"
                )
            else:
                logger.warning(
                    f"Verificação HTTP falhou: "
                    f"status {response.status_code}, "
                    f"TTFB {ttfb:.3f}s, "
                    f"tempo total {elapsed_time:.2f}s"
                )
                
                # Registra erro no histórico
                self.error_history.record_error(
                    error_type=ErrorType.HTTP_ERROR,
                    severity=ErrorSeverity.WARNING,
                    message=f"HTTP check failed with status code {response.status_code}",
                    details=result.get("http_detail", {}),
                    ok_ssl=True,
                    ok_http=False,
                    ok_playwright=True,
                )
            
            return result
            
        except Timeout:
            logger.error(f"Timeout na verificação HTTP após {DEFAULT_HTTP_TIMEOUT}s")
            
            # Registra erro no histórico
            self.error_history.record_error(
                error_type=ErrorType.HTTP_TIMEOUT,
                severity=ErrorSeverity.CRITICAL,
                message=f"HTTP request timeout after {DEFAULT_HTTP_TIMEOUT}s",
                details={"timeout_seconds": DEFAULT_HTTP_TIMEOUT},
                ok_ssl=True,
                ok_http=False,
                ok_playwright=True,
            )
            
            return {
                "ok_http": False,
                "http_detail": {
                    "error": "Request timeout",
                    "timeout_seconds": DEFAULT_HTTP_TIMEOUT,
                }
            }
        except RequestsConnectionError as e:
            logger.error(f"Erro de conexão na verificação HTTP: {e}")
            
            # Registra erro no histórico
            self.error_history.record_error(
                error_type=ErrorType.HTTP_ERROR,
                severity=ErrorSeverity.CRITICAL,
                message=f"HTTP connection error: {str(e)}",
                details={"error": str(e)},
                ok_ssl=True,
                ok_http=False,
                ok_playwright=True,
            )
            
            return {
                "ok_http": False,
                "http_detail": {
                    "error": "Connection error",
                    "message": str(e),
                }
            }
        except RequestException as e:
            logger.error(f"Erro na requisição HTTP: {e}", exc_info=True)
            
            # Registra erro no histórico
            self.error_history.record_error(
                error_type=ErrorType.HTTP_ERROR,
                severity=ErrorSeverity.WARNING,
                message=f"HTTP request error: {str(e)}",
                details={"error": str(e), "type": type(e).__name__},
                ok_ssl=True,
                ok_http=False,
                ok_playwright=True,
            )
            
            return {
                "ok_http": False,
                "http_detail": {
                    "error": type(e).__name__,
                    "message": str(e),
                }
            }
        except Exception as e:
            logger.error(f"Erro inesperado na verificação HTTP: {e}", exc_info=True)
            
            # Registra erro no histórico
            self.error_history.record_error(
                error_type=ErrorType.HTTP_ERROR,
                severity=ErrorSeverity.WARNING,
                message=f"Unexpected error in HTTP check: {str(e)}",
                details={"error": str(e), "type": type(e).__name__},
                ok_ssl=True,
                ok_http=False,
                ok_playwright=True,
            )
            
            return {
                "ok_http": False,
                "http_detail": {
                    "error": "Unexpected error",
                    "message": str(e),
                    "type": type(e).__name__,
                }
            }
    
    @contextmanager
    def _browser_context(self, playwright: Playwright) -> Browser:
        """
        Context manager para gerenciar o ciclo de vida do browser.
        
        Args:
            playwright: Instância do Playwright.
            
        Yields:
            Browser: Instância do browser.
        """
        browser = None
        try:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            logger.debug("Browser iniciado com sucesso")
            yield browser
        finally:
            if browser:
                try:
                    browser.close()
                    logger.debug("Browser fechado com sucesso")
                except Exception as e:
                    logger.warning(f"Erro ao fechar browser: {e}")
    
    def _do_playwright_check(self) -> Dict[str, Any]:
        """
        Realiza verificação funcional usando Playwright.
        
        Navega até o portal, interage com elementos da página e verifica
        se o fluxo completo funciona corretamente.
        
        Returns:
            Dict com chaves 'ok_playwright', 'playwright_detail' e 'screenshot'.
        """
        logger.info(f"Executando verificação Playwright para {self.settings.PORTAL_URL}")
        
        try:
            with sync_playwright() as playwright:
                with self._browser_context(playwright) as browser:
                    page = browser.new_page()
                    
                    try:
                        # Navega para o portal e mede performance
                        logger.debug(f"Navegando para {self.settings.PORTAL_URL}")
                        
                        # Mede tempo de navegação
                        navigation_start = time.time()
                        
                        # Obtém métricas de performance do navegador
                        page.goto(
                            self.settings.PORTAL_URL,
                            wait_until="networkidle",
                            timeout=DEFAULT_PAGE_LOAD_TIMEOUT
                        )
                        
                        navigation_time = time.time() - navigation_start
                        logger.debug(f"Página carregada em {navigation_time:.2f}s")
                        
                        # Obtém métricas de performance do navegador usando Performance API
                        performance_metrics = self._get_page_performance_metrics(page)
                        
                        # Interage com a página
                        interaction_start = time.time()
                        detail_messages: List[str] = []
                        playwright_ok = self._interact_with_page(page, detail_messages)
                        interaction_time = time.time() - interaction_start
                        
                        # Compila métricas de performance
                        performance_metrics.update({
                            "navigation_time": round(navigation_time, 3),
                            "interaction_time": round(interaction_time, 3),
                            "total_time": round(navigation_time + interaction_time, 3),
                        })
                        
                        # Tira screenshot em caso de falha
                        screenshot_path: Optional[str] = None
                        if not playwright_ok:
                            logger.warning("Falha na interação com a página, tirando screenshot")
                            screenshot_path = self._take_failure_screenshot(page)
                            
                            # Registra erro no histórico
                            self.error_history.record_error(
                                error_type=ErrorType.PLAYWRIGHT_ERROR,
                                severity=ErrorSeverity.WARNING,
                                message=f"Playwright interaction failed: {'; '.join(detail_messages)}",
                                details={"messages": detail_messages, "screenshot": screenshot_path},
                                ok_ssl=True,
                                ok_http=True,
                                ok_playwright=False,
                            )
                        
                        return {
                            "ok_playwright": playwright_ok,
                            "playwright_detail": {
                                "messages": detail_messages,
                                "performance": performance_metrics
                            },
                            "screenshot": screenshot_path
                        }
                    finally:
                        try:
                            page.close()
                        except Exception as e:
                            logger.warning(f"Erro ao fechar página: {e}")
                            
        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout no Playwright: {e}")
            
            # Registra erro no histórico
            self.error_history.record_error(
                error_type=ErrorType.PLAYWRIGHT_TIMEOUT,
                severity=ErrorSeverity.CRITICAL,
                message=f"Playwright timeout error: {str(e)}",
                details={"error": str(e)},
                ok_ssl=True,
                ok_http=True,
                ok_playwright=False,
            )
            
            return {
                "ok_playwright": False,
                "playwright_detail": {
                    "error": "Playwright timeout",
                    "message": str(e),
                }
            }
        except Exception as e:
            logger.error(f"Erro inesperado no Playwright: {e}", exc_info=True)
            
            # Registra erro no histórico
            self.error_history.record_error(
                error_type=ErrorType.PLAYWRIGHT_ERROR,
                severity=ErrorSeverity.WARNING,
                message=f"Unexpected error in Playwright check: {str(e)}",
                details={"error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()},
                ok_ssl=True,
                ok_http=True,
                ok_playwright=False,
            )
            
            return {
                "ok_playwright": False,
                "playwright_detail": {
                    "error": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc(),
                }
            }
    
    def _get_page_performance_metrics(self, page: Page) -> Dict[str, Any]:
        """
        Obtém métricas de performance da página usando Performance API do navegador.
        
        Args:
            page: Instância da página do Playwright.
        
        Returns:
            Dict com métricas de performance.
        """
        try:
            # Usa Performance API do navegador para obter métricas detalhadas
            metrics = page.evaluate("""
                () => {
                    const perfData = window.performance.timing;
                    const navigation = window.performance.navigation;
                    const memory = window.performance.memory || {};
                    
                    // Calcula métricas de navegação
                    const dns = perfData.domainLookupEnd - perfData.domainLookupStart;
                    const tcp = perfData.connectEnd - perfData.connectStart;
                    const ssl = perfData.secureConnectionStart > 0 
                        ? perfData.connectEnd - perfData.secureConnectionStart 
                        : 0;
                    const ttfb = perfData.responseStart - perfData.requestStart;
                    const download = perfData.responseEnd - perfData.responseStart;
                    const domProcessing = perfData.domComplete - perfData.domInteractive;
                    const domContentLoaded = perfData.domContentLoadedEventEnd - perfData.navigationStart;
                    const loadComplete = perfData.loadEventEnd - perfData.navigationStart;
                    
                    // Resource timing
                    const resources = window.performance.getEntriesByType('resource');
                    const totalResources = resources.length;
                    const totalResourceSize = resources.reduce((sum, r) => {
                        return sum + (r.transferSize || 0);
                    }, 0);
                    
                    return {
                        // Tempos de navegação
                        dns_time: dns,
                        tcp_time: tcp,
                        ssl_time: ssl,
                        ttfb: ttfb,
                        download_time: download,
                        dom_processing: domProcessing,
                        dom_content_loaded: domContentLoaded,
                        load_complete: loadComplete,
                        
                        // Informações de navegação
                        redirect_count: navigation.redirectCount,
                        navigation_type: navigation.type,
                        
                        // Recursos
                        total_resources: totalResources,
                        total_resource_size: totalResourceSize,
                        
                        // Memória (se disponível)
                        memory_used: memory.usedJSHeapSize || 0,
                        memory_total: memory.totalJSHeapSize || 0,
                        memory_limit: memory.jsHeapSizeLimit || 0,
                    };
                }
            """)
            
            # Converte para formato mais legível
            return {
                "dns_time_ms": round(metrics.get("dns_time", 0), 2),
                "tcp_time_ms": round(metrics.get("tcp_time", 0), 2),
                "ssl_time_ms": round(metrics.get("ssl_time", 0), 2),
                "ttfb_ms": round(metrics.get("ttfb", 0), 2),
                "download_time_ms": round(metrics.get("download_time", 0), 2),
                "dom_processing_ms": round(metrics.get("dom_processing", 0), 2),
                "dom_content_loaded_ms": round(metrics.get("dom_content_loaded", 0), 2),
                "load_complete_ms": round(metrics.get("load_complete", 0), 2),
                "redirect_count": metrics.get("redirect_count", 0),
                "navigation_type": metrics.get("navigation_type", 0),
                "total_resources": metrics.get("total_resources", 0),
                "total_resource_size_bytes": metrics.get("total_resource_size", 0),
                "memory_used_mb": round(metrics.get("memory_used", 0) / 1024 / 1024, 2),
                "memory_total_mb": round(metrics.get("memory_total", 0) / 1024 / 1024, 2),
                "memory_limit_mb": round(metrics.get("memory_limit", 0) / 1024 / 1024, 2),
            }
            
        except Exception as e:
            logger.warning(f"Erro ao obter métricas de performance: {e}")
            return {
                "error": "Não foi possível obter métricas de performance",
                "message": str(e)
            }
    
    def _interact_with_page(
        self,
        page: Page,
        detail_messages: List[str]
    ) -> bool:
        """
        Interage com a página seguindo o fluxo esperado.
        
        Executa os seguintes passos:
        1. Seleciona organização no select
        2. Aguarda lista de documentos aparecer
        3. Clica no primeiro documento
        4. Verifica se o documento abriu corretamente
        
        Args:
            page: Instância da página do Playwright.
            detail_messages: Lista para armazenar mensagens de detalhamento.
            
        Returns:
            True se todas as interações foram bem-sucedidas, False caso contrário.
        """
        try:
            # Seleciona organização
            logger.debug("Localizando select de organização")
            org_select = page.locator(SELECTOR_ORG_SELECT)
            org_select.wait_for(state="visible", timeout=DEFAULT_ORG_SELECT_TIMEOUT)
            org_select.select_option(label=self.settings.SUCCESS_ORG_LABEL)
            detail_messages.append("Select de organização selecionado com sucesso")
            logger.debug(f"Organização '{self.settings.SUCCESS_ORG_LABEL}' selecionada")
            
            # Aguarda lista de documentos
            logger.debug("Aguardando lista de documentos")
            doc_list = page.locator(SELECTOR_DOC_LIST)
            doc_list.wait_for(state="visible", timeout=DEFAULT_ELEMENT_TIMEOUT)
            detail_messages.append("Lista de documentos carregada")
            logger.debug("Lista de documentos visível")
            
            # Abre primeiro documento
            logger.debug("Localizando primeiro documento")
            first_doc = page.locator(SELECTOR_DOC_LINK).first
            first_doc.wait_for(state="visible", timeout=DEFAULT_ELEMENT_TIMEOUT)
            first_doc.click()
            detail_messages.append("Primeiro documento clicado")
            logger.debug("Primeiro documento clicado")
            
            # Verifica se documento abriu
            logger.debug("Verificando se documento abriu")
            doc_viewer = page.locator(SELECTOR_DOC_VIEWER)
            doc_viewer.wait_for(state="visible", timeout=DEFAULT_DOC_VIEWER_TIMEOUT)
            detail_messages.append("Documento aberto com sucesso")
            logger.info("Fluxo completo executado com sucesso")
            
            return True
            
        except PlaywrightTimeoutError as e:
            error_msg = f"Timeout ao interagir com elemento: {str(e)}"
            detail_messages.append(error_msg)
            logger.error(error_msg)
            return False
        except Exception as e:
            error_msg = f"Erro ao interagir com página: {str(e)}"
            detail_messages.append(error_msg)
            logger.error(error_msg, exc_info=True)
            return False
    
    def _take_failure_screenshot(self, page: Page) -> Optional[str]:
        """
        Tira screenshot da página em caso de falha.
        
        Args:
            page: Instância da página do Playwright.
            
        Returns:
            Caminho do arquivo de screenshot ou None em caso de erro.
        """
        try:
            # Garante que o diretório existe
            self.settings.FAIL_DIR.mkdir(parents=True, exist_ok=True)
            
            # Gera nome único para o screenshot
            timestamp = datetime.now(self.settings.tz).strftime("%Y%m%d_%H%M%S_%f")
            screenshot_path = self.settings.FAIL_DIR / f"fail_{timestamp}.png"
            
            # Tira o screenshot
            page.screenshot(path=str(screenshot_path), full_page=True)
            
            logger.info(f"Screenshot salvo em: {screenshot_path}")
            return str(screenshot_path)
            
        except Exception as e:
            logger.error(f"Erro ao tirar screenshot: {e}", exc_info=True)
            return None
    
    def _notify_failure(self, result: Dict[str, Any]) -> None:
        """
        Envia notificação de falha via Slack.
        
        Args:
            result: Dict com os resultados das verificações.
        """
        try:
            # Constrói mensagem formatada
            message_parts = [
                f"🚨 Problema detectado em {result['site_url']}",
                f"Timestamp: {result['timestamp']}",
                f"HTTP OK: {result['ok_http']}",
                f"SSL OK: {result.get('ok_ssl', 'N/A')}",
                f"Playwright OK: {result['ok_playwright']}",
            ]
            
            # Adiciona detalhes SSL
            if result.get('ssl_detail'):
                ssl_detail = result['ssl_detail']
                if 'expiration' in ssl_detail:
                    exp = ssl_detail['expiration']
                    if exp.get('is_expired'):
                        message_parts.append(
                            f"SSL: ❌ Certificado EXPIRADO há {abs(exp.get('days_until_expiration', 0))} dias"
                        )
                    elif exp.get('is_expiring_soon'):
                        message_parts.append(
                            f"SSL: ⚠️ Certificado expira em {exp.get('days_until_expiration', 0)} dias"
                        )
                    elif exp.get('warning'):
                        message_parts.append(f"SSL: ⚠️ {exp['warning']}")
                elif 'error' in ssl_detail:
                    message_parts.append(f"SSL Error: {ssl_detail['error']}")
            
            # Adiciona detalhes HTTP
            if result.get('http_detail'):
                http_detail = result['http_detail']
                if 'status_code' in http_detail:
                    elapsed = http_detail.get('elapsed', 0)
                    perf = http_detail.get('performance', {})
                    ttfb = perf.get('ttfb', 0)
                    message_parts.append(
                        f"HTTP Status: {http_detail['status_code']} "
                        f"(TTFB: {ttfb:.3f}s, Total: {elapsed:.2f}s)"
                    )
                    if perf.get('download_speed_mbps'):
                        message_parts.append(
                            f"  Velocidade: {perf['download_speed_mbps']} Mbps"
                        )
                elif 'error' in http_detail:
                    message_parts.append(f"HTTP Error: {http_detail['error']}")
            
            # Adiciona detalhes Playwright
            if result.get('playwright_detail'):
                playwright_detail = result['playwright_detail']
                if 'messages' in playwright_detail:
                    messages = playwright_detail['messages']
                    message_parts.append("Mensagens:")
                    for msg in messages:
                        message_parts.append(f"  - {msg}")
                    
                    # Adiciona métricas de performance
                    perf = playwright_detail.get('performance', {})
                    if perf and 'error' not in perf:
                        nav_time = perf.get('navigation_time', 0)
                        load_time = perf.get('load_complete_ms', 0)
                        if load_time > 0:
                            message_parts.append(
                                f"Performance: Navegação {nav_time:.2f}s, "
                                f"Carregamento completo {load_time/1000:.2f}s"
                            )
                elif 'error' in playwright_detail:
                    message_parts.append(
                        f"Playwright Error: {playwright_detail['error']}"
                    )
            
            # Adiciona informação sobre screenshot
            if result.get('screenshot'):
                screenshot_path = Path(result['screenshot'])
                message_parts.append(
                    f"Screenshot: {screenshot_path.name} "
                    f"({screenshot_path.parent})"
                )
            
            message = "\n".join(message_parts)
            logger.info("Enviando notificação de falha")
            send_slack(self.settings, message)
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificação: {e}", exc_info=True)