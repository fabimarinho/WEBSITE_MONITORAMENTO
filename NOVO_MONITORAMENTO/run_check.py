"""
Script para executar uma verificação única do sistema de monitoramento.

Este script permite executar uma verificação manual do site monitorado
e exibir os resultados em diferentes formatos (JSON, texto formatado, etc).
Útil para testes, debugging e execuções manuais.
"""
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from check import SiteChecker
from config import Settings, load_settings

# Configuração de logging
logger = logging.getLogger(__name__)

# Constantes
DEFAULT_JSON_INDENT = 2
EXIT_CODE_SUCCESS = 0
EXIT_CODE_CHECK_FAILED = 1
EXIT_CODE_ERROR = 2


def setup_logging(verbose: bool = False) -> None:
    """
    Configura o sistema de logging.
    
    Args:
        verbose: Se True, define o nível de logging como DEBUG.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def format_result_json(result: Dict[str, Any], indent: int = DEFAULT_JSON_INDENT) -> str:
    """
    Formata o resultado como JSON.
    
    Args:
        result: Dicionário com o resultado da verificação.
        indent: Número de espaços para indentação (padrão: 2).
    
    Returns:
        String JSON formatada.
    """
    return json.dumps(result, ensure_ascii=False, indent=indent, default=str)


def format_result_text(result: Dict[str, Any]) -> str:
    """
    Formata o resultado como texto legível.
    
    Args:
        result: Dicionário com o resultado da verificação.
    
    Returns:
        String formatada em texto legível.
    """
    lines = []
    lines.append("=" * 60)
    lines.append("RESULTADO DA VERIFICAÇÃO")
    lines.append("=" * 60)
    lines.append("")
    
    # Informações gerais
    lines.append(f"Timestamp: {result.get('timestamp', 'N/A')}")
    lines.append(f"Site URL: {result.get('site_url', 'N/A')}")
    lines.append(f"Portal URL: {result.get('portal_url', 'N/A')}")
    lines.append("")
    
    # Verificação SSL/TLS
    lines.append("-" * 60)
    lines.append("VERIFICAÇÃO SSL/TLS")
    lines.append("-" * 60)
    ok_ssl = result.get("ok_ssl", False)
    ssl_detail = result.get("ssl_detail", {})
    
    if isinstance(ssl_detail, dict):
        if "expiration" in ssl_detail:
            exp = ssl_detail["expiration"]
            if exp.get("is_expired"):
                lines.append(f"Status: ❌ EXPIRADO")
                lines.append(f"Dias desde expiração: {abs(exp.get('days_until_expiration', 0))}")
            elif exp.get("is_expiring_soon"):
                lines.append(f"Status: ⚠️ EXPIRANDO EM BREVE")
                lines.append(f"Dias até expiração: {exp.get('days_until_expiration', 0)}")
            else:
                lines.append(f"Status: {'✅ OK' if ok_ssl else '❌ FALHA'}")
                lines.append(f"Dias até expiração: {exp.get('days_until_expiration', 'N/A')}")
            
            if "certificate" in ssl_detail:
                cert = ssl_detail["certificate"]
                if "subject" in cert and "CN" in cert["subject"]:
                    lines.append(f"CN: {cert['subject']['CN']}")
                if "issuer" in cert and "CN" in cert["issuer"]:
                    lines.append(f"Issuer: {cert['issuer']['CN']}")
                if "not_after" in cert:
                    lines.append(f"Expira em: {cert['not_after']}")
        elif "error" in ssl_detail:
            lines.append(f"Status: ❌ ERRO")
            lines.append(f"Erro: {ssl_detail['error']}")
            if "message" in ssl_detail:
                lines.append(f"Detalhes: {ssl_detail['message']}")
        else:
            lines.append(f"Status: {'✅ OK' if ok_ssl else '❌ FALHA'}")
    else:
        lines.append(f"Status: {'✅ OK' if ok_ssl else '❌ FALHA'}")
    lines.append("")
    
    # Verificação HTTP
    lines.append("-" * 60)
    lines.append("VERIFICAÇÃO HTTP")
    lines.append("-" * 60)
    ok_http = result.get("ok_http", False)
    http_detail = result.get("http_detail", {})
    
    if isinstance(http_detail, dict):
        if "status_code" in http_detail:
            status_code = http_detail["status_code"]
            elapsed = http_detail.get("elapsed", 0)
            perf = http_detail.get("performance", {})
            
            lines.append(f"Status: {'✅ OK' if ok_http else '❌ FALHA'}")
            lines.append(f"Código HTTP: {status_code}")
            lines.append(f"Tempo de resposta: {elapsed:.2f}s")
            
            # Métricas de performance
            if perf:
                ttfb = perf.get("ttfb", 0)
                total_time = perf.get("total_time", elapsed)
                content_length = perf.get("content_length", 0)
                download_speed = perf.get("download_speed_mbps", 0)
                
                lines.append("")
                lines.append("Métricas de Performance:")
                lines.append(f"  TTFB (Time To First Byte): {ttfb:.3f}s")
                lines.append(f"  Tempo total: {total_time:.3f}s")
                if content_length > 0:
                    size_mb = content_length / 1024 / 1024
                    lines.append(f"  Tamanho da resposta: {size_mb:.2f} MB ({content_length:,} bytes)")
                if download_speed > 0:
                    lines.append(f"  Velocidade de download: {download_speed:.2f} Mbps")
        elif "error" in http_detail:
            lines.append(f"Status: ❌ ERRO")
            lines.append(f"Erro: {http_detail['error']}")
            if "message" in http_detail:
                lines.append(f"Detalhes: {http_detail['message']}")
    else:
        lines.append(f"Status: {'✅ OK' if ok_http else '❌ FALHA'}")
    lines.append("")
    
    # Verificação Playwright
    lines.append("-" * 60)
    lines.append("VERIFICAÇÃO PLAYWRIGHT")
    lines.append("-" * 60)
    ok_playwright = result.get("ok_playwright", False)
    playwright_detail = result.get("playwright_detail", {})
    
    if isinstance(playwright_detail, dict):
        if "messages" in playwright_detail:
            messages = playwright_detail["messages"]
            perf = playwright_detail.get("performance", {})
            
            lines.append(f"Status: {'✅ OK' if ok_playwright else '❌ FALHA'}")
            if messages:
                lines.append("Mensagens:")
                for msg in messages:
                    lines.append(f"  - {msg}")
            
            # Métricas de performance do Playwright
            if perf and "error" not in perf:
                lines.append("")
                lines.append("Métricas de Performance:")
                nav_time = perf.get("navigation_time", 0)
                interaction_time = perf.get("interaction_time", 0)
                total_time = perf.get("total_time", 0)
                ttfb_ms = perf.get("ttfb_ms", 0)
                dom_loaded = perf.get("dom_content_loaded_ms", 0)
                load_complete = perf.get("load_complete_ms", 0)
                
                if nav_time > 0:
                    lines.append(f"  Tempo de navegação: {nav_time:.3f}s")
                if interaction_time > 0:
                    lines.append(f"  Tempo de interação: {interaction_time:.3f}s")
                if total_time > 0:
                    lines.append(f"  Tempo total: {total_time:.3f}s")
                if ttfb_ms > 0:
                    lines.append(f"  TTFB: {ttfb_ms:.2f}ms")
                if dom_loaded > 0:
                    lines.append(f"  DOM Content Loaded: {dom_loaded/1000:.3f}s")
                if load_complete > 0:
                    lines.append(f"  Load Complete: {load_complete/1000:.3f}s")
                
                # Métricas adicionais
                dns_time = perf.get("dns_time_ms", 0)
                tcp_time = perf.get("tcp_time_ms", 0)
                download_time = perf.get("download_time_ms", 0)
                total_resources = perf.get("total_resources", 0)
                total_size = perf.get("total_resource_size_bytes", 0)
                
                if dns_time > 0 or tcp_time > 0:
                    lines.append("")
                    lines.append("  Detalhes de Conexão:")
                    if dns_time > 0:
                        lines.append(f"    DNS: {dns_time:.2f}ms")
                    if tcp_time > 0:
                        lines.append(f"    TCP: {tcp_time:.2f}ms")
                    if download_time > 0:
                        lines.append(f"    Download: {download_time:.2f}ms")
                
                if total_resources > 0:
                    lines.append("")
                    lines.append(f"  Recursos carregados: {total_resources}")
                    if total_size > 0:
                        size_mb = total_size / 1024 / 1024
                        lines.append(f"  Tamanho total: {size_mb:.2f} MB ({total_size:,} bytes)")
        elif "error" in playwright_detail:
            lines.append(f"Status: ❌ ERRO")
            lines.append(f"Erro: {playwright_detail['error']}")
            if "message" in playwright_detail:
                lines.append(f"Detalhes: {playwright_detail['message']}")
    else:
        lines.append(f"Status: {'✅ OK' if ok_playwright else '❌ FALHA'}")
    lines.append("")
    
    # Screenshot
    screenshot = result.get("screenshot")
    if screenshot:
        lines.append("-" * 60)
        lines.append("SCREENSHOT")
        lines.append("-" * 60)
        lines.append(f"Caminho: {screenshot}")
        lines.append("")
    
    # Resumo
    lines.append("=" * 60)
    lines.append("RESUMO")
    lines.append("=" * 60)
    all_ok = ok_ssl and ok_http and ok_playwright
    lines.append(f"Status Geral: {'✅ SUCESSO' if all_ok else '❌ FALHA'}")
    lines.append(f"SSL/TLS: {'✅ OK' if ok_ssl else '❌ FALHA'}")
    lines.append(f"HTTP: {'✅ OK' if ok_http else '❌ FALHA'}")
    lines.append(f"Playwright: {'✅ OK' if ok_playwright else '❌ FALHA'}")
    lines.append("")
    
    return "\n".join(lines)


def save_result_to_file(result: Dict[str, Any], output_file: Path, format_type: str = "json") -> None:
    """
    Salva o resultado em um arquivo.
    
    Args:
        result: Dicionário com o resultado da verificação.
        output_file: Caminho do arquivo de saída.
        format_type: Formato de saída ('json' ou 'text').
    
    Raises:
        ValueError: Se o formato não for suportado.
        OSError: Se não for possível escrever o arquivo.
    """
    try:
        # Garante que o diretório existe
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Formata o resultado
        if format_type == "json":
            content = format_result_json(result)
        elif format_type == "text":
            content = format_result_text(result)
        else:
            raise ValueError(f"Formato não suportado: {format_type}")
        
        # Escreve o arquivo
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        logger.info(f"Resultado salvo em: {output_file}")
        
    except OSError as e:
        logger.error(f"Erro ao salvar resultado em {output_file}: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao salvar resultado: {e}", exc_info=True)
        raise


def run_check(
    settings: Optional[Settings] = None,
    output_format: str = "json",
    output_file: Optional[Path] = None,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Executa uma verificação única do sistema.
    
    Args:
        settings: Configurações do sistema. Se None, carrega do ambiente.
        output_format: Formato de saída ('json' ou 'text').
        output_file: Caminho do arquivo para salvar o resultado (opcional).
        verbose: Se True, habilita logging verboso.
    
    Returns:
        Dicionário com o resultado da verificação.
    
    Raises:
        RuntimeError: Se houver erro ao executar a verificação.
    """
    if settings is None:
        logger.info("Carregando configurações...")
        try:
            settings = load_settings()
            logger.info("Configurações carregadas com sucesso")
        except Exception as e:
            logger.error(f"Erro ao carregar configurações: {e}", exc_info=True)
            raise RuntimeError(f"Falha ao carregar configurações: {e}") from e
    
    logger.info("Inicializando verificador...")
    try:
        checker = SiteChecker(settings)
        logger.info("Verificador inicializado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao inicializar verificador: {e}", exc_info=True)
        raise RuntimeError(f"Falha ao inicializar verificador: {e}") from e
    
    logger.info("Executando verificação...")
    try:
        result = checker.perform_check()
        logger.info("Verificação concluída")
        
        # Formata e exibe o resultado
        if output_format == "json":
            output = format_result_json(result)
        elif output_format == "text":
            output = format_result_text(result)
        else:
            raise ValueError(f"Formato não suportado: {output_format}")
        
        # Exibe no console
        print(output)
        
        # Salva em arquivo se especificado
        if output_file:
            save_result_to_file(result, output_file, output_format)
        
        return result
        
    except Exception as e:
        logger.error(f"Erro ao executar verificação: {e}", exc_info=True)
        raise RuntimeError(f"Falha ao executar verificação: {e}") from e


def get_exit_code(result: Dict[str, Any], fail_on_error: bool = False) -> int:
    """
    Determina o código de saída baseado no resultado.
    
    Args:
        result: Dicionário com o resultado da verificação.
        fail_on_error: Se True, retorna código de erro se a verificação falhar.
    
    Returns:
        Código de saída (0 para sucesso, 1 para falha, 2 para erro).
    """
    if fail_on_error:
        ok_ssl = result.get("ok_ssl", False)
        ok_http = result.get("ok_http", False)
        ok_playwright = result.get("ok_playwright", False)
        
        if not ok_ssl or not ok_http or not ok_playwright:
            return EXIT_CODE_CHECK_FAILED
    
    return EXIT_CODE_SUCCESS


def parse_arguments() -> argparse.Namespace:
    """
    Parse dos argumentos da linha de comando.
    
    Returns:
        Namespace com os argumentos parseados.
    """
    parser = argparse.ArgumentParser(
        description="Executa uma verificação única do sistema de monitoramento.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Executa verificação e exibe resultado em JSON
  python run_check.py
  
  # Executa verificação e exibe resultado formatado
  python run_check.py --format text
  
  # Salva resultado em arquivo
  python run_check.py --output resultado.json
  
  # Executa com logging verboso
  python run_check.py --verbose
  
  # Retorna código de erro se verificação falhar
  python run_check.py --fail-on-error
        """
    )
    
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Formato de saída (padrão: json)"
    )
    
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Caminho do arquivo para salvar o resultado"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Habilita logging verboso (DEBUG)"
    )
    
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Retorna código de erro se a verificação falhar"
    )
    
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Caminho do arquivo .env (padrão: .env no diretório atual)"
    )
    
    return parser.parse_args()


def main() -> int:
    """
    Função principal do script.
    
    Returns:
        Código de saída (0 para sucesso, não-zero para erro).
    """
    args = parse_arguments()
    
    # Configura logging
    setup_logging(verbose=args.verbose)
    
    try:
        # Carrega configurações
        if args.env_file:
            logger.info(f"Carregando configurações de {args.env_file}")
            settings = load_settings(env_file=str(args.env_file))
        else:
            settings = load_settings()
        
        # Executa verificação
        result = run_check(
            settings=settings,
            output_format=args.format,
            output_file=args.output,
            verbose=args.verbose
        )
        
        # Determina código de saída
        exit_code = get_exit_code(result, fail_on_error=args.fail_on_error)
        
        logger.info(f"Script finalizado com código de saída: {exit_code}")
        return exit_code
        
    except KeyboardInterrupt:
        logger.info("Interrupção do usuário recebida")
        return 130  # Código padrão para SIGINT
    except Exception as e:
        logger.error(f"Erro fatal: {e}", exc_info=True)
        print(f"ERRO: {e}", file=sys.stderr)
        return EXIT_CODE_ERROR


if __name__ == "__main__":
    sys.exit(main())
