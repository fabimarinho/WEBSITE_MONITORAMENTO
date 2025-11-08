"""
Módulo de geração de relatórios em PDF.

Este módulo implementa a geração de relatórios diários e mensais em formato PDF
a partir dos logs de monitoramento do sistema.
"""
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fpdf import FPDF

from config import Settings
from utils import now_str

# Configuração de logging
logger = logging.getLogger(__name__)

# Constantes de formatação PDF
PDF_FONT_FAMILY = "Arial"
PDF_HEADER_FONT_SIZE = 14
PDF_SUBHEADER_FONT_SIZE = 12
PDF_TITLE_FONT_SIZE = 11
PDF_BODY_FONT_SIZE = 10
PDF_PAGE_MARGIN = 15
PDF_LINE_HEIGHT_SMALL = 5
PDF_LINE_HEIGHT_MEDIUM = 6
PDF_LINE_HEIGHT_LARGE = 7
PDF_LINE_HEIGHT_HEADER = 8
PDF_SPACING_SMALL = 2
PDF_SPACING_MEDIUM = 4
PDF_SPACING_LARGE = 6
PDF_IMAGE_WIDTH = 180

# Constantes de relatórios
MONTHLY_REPORT_DAYS = 30
DATE_FORMAT = "%Y-%m-%d"
REPORT_DATE_FORMAT = "%Y-%m-%d"


class ReportGenerator:
    """
    Gerador de relatórios em PDF.
    
    Esta classe é responsável por gerar relatórios diários e mensais
    em formato PDF a partir dos logs de monitoramento.
    """
    
    def __init__(self, settings: Settings):
        """
        Inicializa o gerador de relatórios.
        
        Args:
            settings: Configurações do sistema.
            
        Raises:
            ValueError: Se as configurações forem inválidas.
        """
        self.settings = settings
        self._validate_settings()
        logger.info("ReportGenerator inicializado")
    
    def _validate_settings(self) -> None:
        """Valida as configurações necessárias para gerar relatórios."""
        if not self.settings.DAILY_DIR:
            raise ValueError("DAILY_DIR não pode estar vazio")
        if not self.settings.MONTHLY_DIR:
            raise ValueError("MONTHLY_DIR não pode estar vazio")
        if not self.settings.LOG_FILE:
            raise ValueError("LOG_FILE não pode estar vazio")
    
    def generate_daily_report(self, for_date: Optional[date] = None) -> str:
        """
        Gera relatório diário em PDF.
        
        Args:
            for_date: Data para o qual gerar o relatório. Se None, usa a data atual.
        
        Returns:
            Caminho do arquivo PDF gerado.
            
        Raises:
            OSError: Se não for possível criar ou escrever o arquivo PDF.
            ValueError: Se a data for inválida ou não houver logs para processar.
        """
        if for_date is None:
            for_date = datetime.now(self.settings.tz).date()
        
        logger.info(f"Gerando relatório diário para {for_date.isoformat()}")
        
        try:
            # Obtém logs para a data
            logs = self._get_logs_for_date(for_date)
            logger.debug(f"Encontrados {len(logs)} logs para {for_date.isoformat()}")
            
            # Cria PDF
            pdf = self._create_pdf()
            
            # Escreve conteúdo
            self._write_daily_header(pdf, for_date)
            self._write_daily_summary(pdf, logs)
            self._write_daily_incidents(pdf, logs)
            
            # Salva arquivo
            out_path = self.settings.DAILY_DIR / f"{for_date.isoformat()}_report.pdf"
            self._save_pdf(pdf, out_path)
            
            logger.info(f"Relatório diário gerado com sucesso: {out_path}")
            return str(out_path)
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório diário para {for_date}: {e}", exc_info=True)
            raise
    
    def generate_monthly_report(self, reference_date: Optional[date] = None) -> str:
        """
        Gera relatório mensal (últimos 30 dias) em PDF.
        
        Args:
            reference_date: Data de referência para o relatório. Se None, usa a data atual.
        
        Returns:
            Caminho do arquivo PDF gerado.
            
        Raises:
            OSError: Se não for possível criar ou escrever o arquivo PDF.
            ValueError: Se a data for inválida.
        """
        if reference_date is None:
            reference_date = datetime.now(self.settings.tz).date()
        
        logger.info(f"Gerando relatório mensal para {reference_date.isoformat()}")
        
        try:
            # Obtém logs dos últimos 30 dias
            logs = self._get_logs_for_last_30_days(reference_date)
            start_date = reference_date - timedelta(days=MONTHLY_REPORT_DAYS - 1)
            logger.debug(
                f"Encontrados {len(logs)} logs entre {start_date.isoformat()} "
                f"e {reference_date.isoformat()}"
            )
            
            # Cria PDF
            pdf = self._create_pdf()
            
            # Escreve conteúdo
            self._write_monthly_header(pdf, reference_date, start_date)
            self._write_monthly_summary(pdf, logs)
            self._write_monthly_incidents(pdf, logs)
            
            # Salva arquivo
            out_path = (
                self.settings.MONTHLY_DIR / 
                f"{reference_date.isoformat()}_monthly_report.pdf"
            )
            self._save_pdf(pdf, out_path)
            
            logger.info(f"Relatório mensal gerado com sucesso: {out_path}")
            return str(out_path)
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório mensal para {reference_date}: {e}", exc_info=True)
            raise
    
    def _create_pdf(self) -> FPDF:
        """
        Cria uma instância configurada do FPDF.
        
        Returns:
            Instância do FPDF configurada.
        """
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=PDF_PAGE_MARGIN)
        pdf.add_page()
        return pdf
    
    def _save_pdf(self, pdf: FPDF, output_path: Path) -> None:
        """
        Salva o PDF no caminho especificado.
        
        Args:
            pdf: Instância do FPDF a ser salva.
            output_path: Caminho onde salvar o PDF.
            
        Raises:
            OSError: Se não for possível criar ou escrever o arquivo.
        """
        try:
            # Garante que o diretório existe
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Salva o PDF
            pdf.output(str(output_path))
            logger.debug(f"PDF salvo em: {output_path}")
            
        except OSError as e:
            logger.error(f"Erro ao salvar PDF em {output_path}: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao salvar PDF: {e}", exc_info=True)
            raise OSError(f"Erro ao salvar PDF: {e}") from e
    
    def _get_logs_for_date(self, for_date: date) -> List[Dict[str, Any]]:
        """
        Obtém todos os logs para uma data específica.
        
        Args:
            for_date: Data para filtrar os logs.
        
        Returns:
            Lista de logs para a data especificada.
        """
        day_prefix = for_date.strftime(DATE_FORMAT)
        all_logs = self._read_all_logs()
        
        filtered_logs = [
            log for log in all_logs
            if log.get("timestamp", "").startswith(day_prefix)
        ]
        
        logger.debug(f"Filtrados {len(filtered_logs)} logs para {day_prefix}")
        return filtered_logs
    
    def _get_logs_for_last_30_days(self, reference_date: date) -> List[Dict[str, Any]]:
        """
        Obtém todos os logs dos últimos 30 dias a partir da data de referência.
        
        Args:
            reference_date: Data de referência.
        
        Returns:
            Lista de logs dos últimos 30 dias.
        """
        start_date = reference_date - timedelta(days=MONTHLY_REPORT_DAYS - 1)
        date_prefixes = [
            (start_date + timedelta(days=i)).strftime(DATE_FORMAT)
            for i in range(MONTHLY_REPORT_DAYS)
        ]
        
        all_logs = self._read_all_logs()
        
        filtered_logs = [
            log for log in all_logs
            if log.get("timestamp", "").startswith(tuple(date_prefixes))
        ]
        
        logger.debug(
            f"Filtrados {len(filtered_logs)} logs entre "
            f"{start_date.isoformat()} e {reference_date.isoformat()}"
        )
        return filtered_logs
    
    def _read_all_logs(self) -> List[Dict[str, Any]]:
        """
        Lê todos os logs do arquivo de log.
        
        Returns:
            Lista de logs lidos do arquivo.
            
        Note:
            Linhas inválidas são ignoradas silenciosamente com logging de aviso.
        """
        logs: List[Dict[str, Any]] = []
        
        if not self.settings.LOG_FILE.exists():
            logger.warning(f"Arquivo de log não encontrado: {self.settings.LOG_FILE}")
            return logs
        
        try:
            with open(self.settings.LOG_FILE, "r", encoding="utf-8") as f:
                line_number = 0
                for line in f:
                    line_number += 1
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    try:
                        log_entry = json.loads(line)
                        if isinstance(log_entry, dict):
                            logs.append(log_entry)
                        else:
                            logger.warning(
                                f"Linha {line_number}: entrada de log não é um dicionário"
                            )
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Linha {line_number}: erro ao decodificar JSON: {e}. "
                            f"Linha ignorada."
                        )
                        continue
                    except Exception as e:
                        logger.warning(
                            f"Linha {line_number}: erro inesperado: {e}. Linha ignorada."
                        )
                        continue
            
            logger.debug(f"Lidos {len(logs)} logs do arquivo {self.settings.LOG_FILE}")
            return logs
            
        except OSError as e:
            logger.error(f"Erro ao ler arquivo de log {self.settings.LOG_FILE}: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao ler logs: {e}", exc_info=True)
            raise
    
    def _write_daily_header(self, pdf: FPDF, for_date: date) -> None:
        """
        Escreve o cabeçalho do relatório diário.
        
        Args:
            pdf: Instância do FPDF.
            for_date: Data do relatório.
        """
        pdf.set_font(PDF_FONT_FAMILY, "B", PDF_HEADER_FONT_SIZE)
        pdf.cell(0, PDF_LINE_HEIGHT_HEADER, f"Relatório Diário - {for_date.isoformat()}", ln=True)
        pdf.set_font(PDF_FONT_FAMILY, size=PDF_TITLE_FONT_SIZE)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"Gerado em: {now_str(self.settings)}", ln=True)
        pdf.ln(PDF_SPACING_MEDIUM)
    
    def _write_daily_summary(self, pdf: FPDF, logs: List[Dict[str, Any]]) -> None:
        """
        Escreve o resumo do relatório diário.
        
        Args:
            pdf: Instância do FPDF.
            logs: Lista de logs do dia.
        """
        total = len(logs)
        ok_count = sum(
            1 for log in logs
            if log.get("ok_ssl", True) and log.get("ok_http") and log.get("ok_playwright")
        )
        failure_count = total - ok_count
        
        # Estatísticas por tipo de verificação
        ssl_ok_count = sum(1 for log in logs if log.get("ok_ssl", True))
        http_ok_count = sum(1 for log in logs if log.get("ok_http", False))
        playwright_ok_count = sum(1 for log in logs if log.get("ok_playwright", False))
        
        success_rate = (ok_count / total * 100) if total > 0 else 0.0
        
        pdf.set_font(PDF_FONT_FAMILY, "B", PDF_SUBHEADER_FONT_SIZE)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, "Resumo", ln=True)
        pdf.set_font(PDF_FONT_FAMILY, size=PDF_BODY_FONT_SIZE)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"Total de checagens: {total}", ln=True)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"Checagens bem-sucedidas: {ok_count}", ln=True)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"Falhas: {failure_count}", ln=True)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"Taxa de sucesso: {success_rate:.1f}%", ln=True)
        pdf.ln(PDF_SPACING_MEDIUM)
        pdf.set_font(PDF_FONT_FAMILY, "B", PDF_BODY_FONT_SIZE)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, "Por Tipo de Verificação:", ln=True)
        pdf.set_font(PDF_FONT_FAMILY, size=PDF_BODY_FONT_SIZE)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"  SSL/TLS: {ssl_ok_count}/{total} ({ssl_ok_count/total*100:.1f}%)" if total > 0 else "  SSL/TLS: N/A", ln=True)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"  HTTP: {http_ok_count}/{total} ({http_ok_count/total*100:.1f}%)" if total > 0 else "  HTTP: N/A", ln=True)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"  Playwright: {playwright_ok_count}/{total} ({playwright_ok_count/total*100:.1f}%)" if total > 0 else "  Playwright: N/A", ln=True)
        pdf.ln(PDF_SPACING_MEDIUM)
        
        # Estatísticas de performance
        self._write_performance_stats(pdf, logs)
        pdf.ln(PDF_SPACING_LARGE)
    
    def _write_performance_stats(self, pdf: FPDF, logs: List[Dict[str, Any]]) -> None:
        """
        Escreve estatísticas de performance no relatório.
        
        Args:
            pdf: Instância do FPDF.
            logs: Lista de logs.
        """
        # Coleta métricas HTTP
        http_ttfbs: List[float] = []
        http_times: List[float] = []
        http_speeds: List[float] = []
        
        # Coleta métricas Playwright
        playwright_nav_times: List[float] = []
        playwright_load_times: List[float] = []
        playwright_total_times: List[float] = []
        
        for log in logs:
            # Métricas HTTP
            http_detail = log.get("http_detail", {})
            if isinstance(http_detail, dict):
                perf = http_detail.get("performance", {})
                if perf:
                    ttfb = perf.get("ttfb")
                    if ttfb and ttfb > 0:
                        http_ttfbs.append(ttfb)
                    elapsed = http_detail.get("elapsed")
                    if elapsed and elapsed > 0:
                        http_times.append(elapsed)
                    speed = perf.get("download_speed_mbps")
                    if speed and speed > 0:
                        http_speeds.append(speed)
            
            # Métricas Playwright
            playwright_detail = log.get("playwright_detail", {})
            if isinstance(playwright_detail, dict):
                perf = playwright_detail.get("performance", {})
                if perf and "error" not in perf:
                    nav_time = perf.get("navigation_time")
                    if nav_time and nav_time > 0:
                        playwright_nav_times.append(nav_time)
                    load_complete = perf.get("load_complete_ms")
                    if load_complete and load_complete > 0:
                        playwright_load_times.append(load_complete / 1000)  # Converte para segundos
                    total_time = perf.get("total_time")
                    if total_time and total_time > 0:
                        playwright_total_times.append(total_time)
        
        # Calcula estatísticas
        def calc_stats(values: List[float]) -> Dict[str, float]:
            if not values:
                return {}
            return {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "count": len(values)
            }
        
        http_ttfb_stats = calc_stats(http_ttfbs)
        http_time_stats = calc_stats(http_times)
        http_speed_stats = calc_stats(http_speeds)
        playwright_nav_stats = calc_stats(playwright_nav_times)
        playwright_load_stats = calc_stats(playwright_load_times)
        playwright_total_stats = calc_stats(playwright_total_times)
        
        # Escreve estatísticas se houver dados
        has_stats = any([
            http_ttfb_stats, http_time_stats, http_speed_stats,
            playwright_nav_stats, playwright_load_stats, playwright_total_stats
        ])
        
        if has_stats:
            pdf.set_font(PDF_FONT_FAMILY, "B", PDF_BODY_FONT_SIZE)
            pdf.cell(0, PDF_LINE_HEIGHT_LARGE, "Estatísticas de Performance:", ln=True)
            pdf.set_font(PDF_FONT_FAMILY, size=PDF_BODY_FONT_SIZE)
            
            # HTTP Stats
            if http_ttfb_stats or http_time_stats:
                pdf.cell(0, PDF_LINE_HEIGHT_MEDIUM, "HTTP:", ln=True)
                if http_ttfb_stats:
                    pdf.cell(0, PDF_LINE_HEIGHT_SMALL, 
                        f"  TTFB: min={http_ttfb_stats['min']:.3f}s, "
                        f"max={http_ttfb_stats['max']:.3f}s, "
                        f"média={http_ttfb_stats['avg']:.3f}s ({http_ttfb_stats['count']} medições)",
                        ln=True)
                if http_time_stats:
                    pdf.cell(0, PDF_LINE_HEIGHT_SMALL,
                        f"  Tempo: min={http_time_stats['min']:.2f}s, "
                        f"max={http_time_stats['max']:.2f}s, "
                        f"média={http_time_stats['avg']:.2f}s ({http_time_stats['count']} medições)",
                        ln=True)
                if http_speed_stats:
                    pdf.cell(0, PDF_LINE_HEIGHT_SMALL,
                        f"  Velocidade: min={http_speed_stats['min']:.2f}Mbps, "
                        f"max={http_speed_stats['max']:.2f}Mbps, "
                        f"média={http_speed_stats['avg']:.2f}Mbps ({http_speed_stats['count']} medições)",
                        ln=True)
            
            # Playwright Stats
            if playwright_nav_stats or playwright_load_stats:
                pdf.cell(0, PDF_LINE_HEIGHT_MEDIUM, "Playwright:", ln=True)
                if playwright_nav_stats:
                    pdf.cell(0, PDF_LINE_HEIGHT_SMALL,
                        f"  Navegação: min={playwright_nav_stats['min']:.3f}s, "
                        f"max={playwright_nav_stats['max']:.3f}s, "
                        f"média={playwright_nav_stats['avg']:.3f}s ({playwright_nav_stats['count']} medições)",
                        ln=True)
                if playwright_load_stats:
                    pdf.cell(0, PDF_LINE_HEIGHT_SMALL,
                        f"  Load Complete: min={playwright_load_stats['min']:.3f}s, "
                        f"max={playwright_load_stats['max']:.3f}s, "
                        f"média={playwright_load_stats['avg']:.3f}s ({playwright_load_stats['count']} medições)",
                        ln=True)
                if playwright_total_stats:
                    pdf.cell(0, PDF_LINE_HEIGHT_SMALL,
                        f"  Tempo Total: min={playwright_total_stats['min']:.3f}s, "
                        f"max={playwright_total_stats['max']:.3f}s, "
                        f"média={playwright_total_stats['avg']:.3f}s ({playwright_total_stats['count']} medições)",
                        ln=True)
    
    def _write_daily_incidents(self, pdf: FPDF, logs: List[Dict[str, Any]]) -> None:
        """
        Escreve a seção de incidentes do relatório diário.
        
        Args:
            pdf: Instância do FPDF.
            logs: Lista de logs do dia.
        """
        incidents = [
            log for log in logs
            if not (log.get("ok_ssl", True) and log.get("ok_http") and log.get("ok_playwright"))
        ]
        
        if not incidents:
            pdf.set_font(PDF_FONT_FAMILY, size=PDF_BODY_FONT_SIZE)
            pdf.cell(0, PDF_LINE_HEIGHT_MEDIUM, "Nenhum incidente registrado no período.", ln=True)
            return
        
        pdf.set_font(PDF_FONT_FAMILY, "B", PDF_SUBHEADER_FONT_SIZE)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"Incidentes ({len(incidents)}):", ln=True)
        pdf.set_font(PDF_FONT_FAMILY, size=PDF_BODY_FONT_SIZE)
        pdf.ln(PDF_SPACING_SMALL)
        
        for idx, incident in enumerate(incidents, 1):
            self._write_incident(pdf, idx, incident)
    
    def _write_monthly_header(
        self,
        pdf: FPDF,
        reference_date: date,
        start_date: date
    ) -> None:
        """
        Escreve o cabeçalho do relatório mensal.
        
        Args:
            pdf: Instância do FPDF.
            reference_date: Data de referência do relatório.
            start_date: Data de início do período.
        """
        pdf.set_font(PDF_FONT_FAMILY, "B", PDF_HEADER_FONT_SIZE)
        pdf.cell(
            0,
            PDF_LINE_HEIGHT_HEADER,
            f"Relatório Mensal - {start_date.isoformat()} a {reference_date.isoformat()}",
            ln=True
        )
        pdf.set_font(PDF_FONT_FAMILY, size=PDF_TITLE_FONT_SIZE)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"Gerado em: {now_str(self.settings)}", ln=True)
        pdf.ln(PDF_SPACING_MEDIUM)
    
    def _write_monthly_summary(self, pdf: FPDF, logs: List[Dict[str, Any]]) -> None:
        """
        Escreve o resumo do relatório mensal.
        
        Args:
            pdf: Instância do FPDF.
            logs: Lista de logs dos últimos 30 dias.
        """
        total = len(logs)
        ok_count = sum(
            1 for log in logs
            if log.get("ok_ssl", True) and log.get("ok_http") and log.get("ok_playwright")
        )
        failure_count = total - ok_count
        
        # Estatísticas por tipo de verificação
        ssl_ok_count = sum(1 for log in logs if log.get("ok_ssl", True))
        http_ok_count = sum(1 for log in logs if log.get("ok_http", False))
        playwright_ok_count = sum(1 for log in logs if log.get("ok_playwright", False))
        
        success_rate = (ok_count / total * 100) if total > 0 else 0.0
        
        # Estatísticas por dia
        daily_stats = self._calculate_daily_stats(logs)
        days_with_incidents = sum(1 for stats in daily_stats.values() if stats["failures"] > 0)
        
        pdf.set_font(PDF_FONT_FAMILY, "B", PDF_SUBHEADER_FONT_SIZE)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, "Resumo do Período", ln=True)
        pdf.set_font(PDF_FONT_FAMILY, size=PDF_BODY_FONT_SIZE)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"Período: {MONTHLY_REPORT_DAYS} dias", ln=True)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"Total de checagens: {total}", ln=True)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"Checagens bem-sucedidas: {ok_count}", ln=True)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"Falhas: {failure_count}", ln=True)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"Taxa de sucesso: {success_rate:.1f}%", ln=True)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"Dias com incidentes: {days_with_incidents}", ln=True)
        pdf.ln(PDF_SPACING_MEDIUM)
        pdf.set_font(PDF_FONT_FAMILY, "B", PDF_BODY_FONT_SIZE)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, "Por Tipo de Verificação:", ln=True)
        pdf.set_font(PDF_FONT_FAMILY, size=PDF_BODY_FONT_SIZE)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"  SSL/TLS: {ssl_ok_count}/{total} ({ssl_ok_count/total*100:.1f}%)" if total > 0 else "  SSL/TLS: N/A", ln=True)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"  HTTP: {http_ok_count}/{total} ({http_ok_count/total*100:.1f}%)" if total > 0 else "  HTTP: N/A", ln=True)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"  Playwright: {playwright_ok_count}/{total} ({playwright_ok_count/total*100:.1f}%)" if total > 0 else "  Playwright: N/A", ln=True)
        pdf.ln(PDF_SPACING_LARGE)
    
    def _write_monthly_incidents(self, pdf: FPDF, logs: List[Dict[str, Any]]) -> None:
        """
        Escreve a seção de incidentes do relatório mensal.
        
        Args:
            pdf: Instância do FPDF.
            logs: Lista de logs dos últimos 30 dias.
        """
        incidents = [
            log for log in logs
            if not (log.get("ok_ssl", True) and log.get("ok_http") and log.get("ok_playwright"))
        ]
        
        if not incidents:
            pdf.set_font(PDF_FONT_FAMILY, size=PDF_BODY_FONT_SIZE)
            pdf.cell(0, PDF_LINE_HEIGHT_MEDIUM, "Nenhum incidente registrado no período.", ln=True)
            return
        
        pdf.set_font(PDF_FONT_FAMILY, "B", PDF_SUBHEADER_FONT_SIZE)
        pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"Incidentes ({len(incidents)}):", ln=True)
        pdf.set_font(PDF_FONT_FAMILY, size=PDF_BODY_FONT_SIZE)
        pdf.ln(PDF_SPACING_SMALL)
        
        # Agrupa incidentes por dia para melhor organização
        incidents_by_date = self._group_incidents_by_date(incidents)
        
        for date_str, date_incidents in sorted(incidents_by_date.items()):
            pdf.set_font(PDF_FONT_FAMILY, "B", PDF_TITLE_FONT_SIZE)
            pdf.cell(0, PDF_LINE_HEIGHT_LARGE, f"Data: {date_str} ({len(date_incidents)} incidente(s))", ln=True)
            pdf.set_font(PDF_FONT_FAMILY, size=PDF_BODY_FONT_SIZE)
            pdf.ln(PDF_SPACING_SMALL)
            
            for idx, incident in enumerate(date_incidents, 1):
                self._write_incident(pdf, idx, incident, show_date=False)
                pdf.ln(PDF_SPACING_SMALL)
    
    def _calculate_daily_stats(self, logs: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
        """
        Calcula estatísticas diárias dos logs.
        
        Args:
            logs: Lista de logs.
        
        Returns:
            Dicionário com estatísticas por dia.
        """
        stats: Dict[str, Dict[str, int]] = {}
        
        for log in logs:
            timestamp = log.get("timestamp", "")
            if not timestamp:
                continue
            
            # Extrai a data do timestamp (primeiros 10 caracteres: YYYY-MM-DD)
            date_str = timestamp[:10] if len(timestamp) >= 10 else ""
            if not date_str:
                continue
            
            if date_str not in stats:
                stats[date_str] = {"total": 0, "ok": 0, "failures": 0}
            
            stats[date_str]["total"] += 1
            if log.get("ok_ssl", True) and log.get("ok_http") and log.get("ok_playwright"):
                stats[date_str]["ok"] += 1
            else:
                stats[date_str]["failures"] += 1
        
        return stats
    
    def _group_incidents_by_date(self, incidents: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Agrupa incidentes por data.
        
        Args:
            incidents: Lista de incidentes.
        
        Returns:
            Dicionário com incidentes agrupados por data.
        """
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        
        for incident in incidents:
            timestamp = incident.get("timestamp", "")
            if not timestamp:
                continue
            
            # Extrai a data do timestamp (primeiros 10 caracteres: YYYY-MM-DD)
            date_str = timestamp[:10] if len(timestamp) >= 10 else ""
            if not date_str:
                continue
            
            if date_str not in grouped:
                grouped[date_str] = []
            
            grouped[date_str].append(incident)
        
        return grouped
    
    def _write_incident(
        self,
        pdf: FPDF,
        idx: int,
        incident: Dict[str, Any],
        show_date: bool = True
    ) -> None:
        """
        Escreve um incidente no PDF.
        
        Args:
            pdf: Instância do FPDF.
            idx: Índice do incidente.
            incident: Dados do incidente.
            show_date: Se True, mostra a data no cabeçalho do incidente.
        """
        pdf.ln(PDF_SPACING_SMALL)
        pdf.set_font(PDF_FONT_FAMILY, "B", PDF_TITLE_FONT_SIZE)
        
        timestamp = incident.get("timestamp", "Timestamp não disponível")
        pdf.cell(0, PDF_LINE_HEIGHT_MEDIUM, f"{idx}. {timestamp}", ln=True)
        
        pdf.set_font(PDF_FONT_FAMILY, size=PDF_BODY_FONT_SIZE)
        
        # Extrai detalhes relevantes
        details = {
            "SSL/TLS OK": incident.get("ok_ssl", False),
            "HTTP OK": incident.get("ok_http", False),
            "Playwright OK": incident.get("ok_playwright", False),
        }
        
        # Adiciona detalhes SSL se disponíveis
        ssl_detail = incident.get("ssl_detail")
        if ssl_detail:
            if isinstance(ssl_detail, dict):
                if "expiration" in ssl_detail:
                    exp = ssl_detail["expiration"]
                    if exp.get("is_expired"):
                        details["SSL Status"] = f"EXPIRADO (há {abs(exp.get('days_until_expiration', 0))} dias)"
                    elif exp.get("is_expiring_soon"):
                        details["SSL Status"] = f"Expira em {exp.get('days_until_expiration', 0)} dias"
                    elif "days_until_expiration" in exp:
                        details["SSL Expira em"] = f"{exp['days_until_expiration']} dias"
                if "certificate" in ssl_detail:
                    cert = ssl_detail["certificate"]
                    if "subject" in cert and "CN" in cert["subject"]:
                        details["SSL CN"] = cert["subject"]["CN"]
                if "error" in ssl_detail:
                    details["SSL Erro"] = ssl_detail["error"]
        
        # Adiciona detalhes HTTP se disponíveis
        http_detail = incident.get("http_detail")
        if http_detail:
            if isinstance(http_detail, dict):
                if "status_code" in http_detail:
                    details["HTTP Status"] = http_detail["status_code"]
                if "elapsed" in http_detail:
                    details["HTTP Tempo"] = f"{http_detail['elapsed']:.2f}s"
                
                # Métricas de performance HTTP
                perf = http_detail.get("performance", {})
                if perf:
                    ttfb = perf.get("ttfb", 0)
                    if ttfb > 0:
                        details["HTTP TTFB"] = f"{ttfb:.3f}s"
                    download_speed = perf.get("download_speed_mbps", 0)
                    if download_speed > 0:
                        details["HTTP Velocidade"] = f"{download_speed:.2f} Mbps"
                    content_length = perf.get("content_length", 0)
                    if content_length > 0:
                        size_mb = content_length / 1024 / 1024
                        details["HTTP Tamanho"] = f"{size_mb:.2f} MB"
                
                if "error" in http_detail:
                    details["HTTP Erro"] = http_detail["error"]
        
        # Adiciona detalhes Playwright se disponíveis
        playwright_detail = incident.get("playwright_detail")
        if playwright_detail:
            if isinstance(playwright_detail, dict):
                if "messages" in playwright_detail:
                    details["Playwright Mensagens"] = playwright_detail["messages"]
                
                # Métricas de performance Playwright
                perf = playwright_detail.get("performance", {})
                if perf and "error" not in perf:
                    nav_time = perf.get("navigation_time", 0)
                    load_complete = perf.get("load_complete_ms", 0)
                    total_time = perf.get("total_time", 0)
                    
                    if nav_time > 0:
                        details["Playwright Navegação"] = f"{nav_time:.3f}s"
                    if load_complete > 0:
                        details["Playwright Load Complete"] = f"{load_complete/1000:.3f}s"
                    if total_time > 0:
                        details["Playwright Tempo Total"] = f"{total_time:.3f}s"
                    
                    ttfb_ms = perf.get("ttfb_ms", 0)
                    if ttfb_ms > 0:
                        details["Playwright TTFB"] = f"{ttfb_ms:.2f}ms"
                    
                    total_resources = perf.get("total_resources", 0)
                    if total_resources > 0:
                        details["Playwright Recursos"] = total_resources
                
                if "error" in playwright_detail:
                    details["Playwright Erro"] = playwright_detail["error"]
        
        # Formata detalhes de forma mais legível
        details_text = "\n".join([f"{k}: {v}" for k, v in details.items()])
        pdf.multi_cell(0, PDF_LINE_HEIGHT_SMALL, details_text)
        
        # Adiciona screenshot se disponível
        screenshot_path = incident.get("screenshot")
        if screenshot_path:
            self._add_screenshot(pdf, screenshot_path)
    
    def _add_screenshot(self, pdf: FPDF, screenshot_path: str) -> None:
        """
        Adiciona um screenshot ao PDF.
        
        Args:
            pdf: Instância do FPDF.
            screenshot_path: Caminho do arquivo de screenshot.
        """
        screenshot = Path(screenshot_path)
        
        if not screenshot.exists():
            logger.warning(f"Screenshot não encontrado: {screenshot_path}")
            pdf.set_font(PDF_FONT_FAMILY, size=PDF_BODY_FONT_SIZE)
            pdf.cell(0, PDF_LINE_HEIGHT_MEDIUM, f"Screenshot não disponível: {screenshot_path}", ln=True)
            return
        
        try:
            pdf.add_page()
            pdf.set_font(PDF_FONT_FAMILY, "B", PDF_TITLE_FONT_SIZE)
            pdf.cell(0, PDF_LINE_HEIGHT_MEDIUM, "Screenshot do Incidente", ln=True)
            pdf.set_font(PDF_FONT_FAMILY, size=PDF_BODY_FONT_SIZE)
            pdf.ln(PDF_SPACING_SMALL)
            
            # Tenta adicionar a imagem
            pdf.image(str(screenshot), w=PDF_IMAGE_WIDTH)
            pdf.ln(PDF_SPACING_MEDIUM)
            logger.debug(f"Screenshot adicionado ao PDF: {screenshot_path}")
            
        except Exception as e:
            logger.error(f"Erro ao adicionar screenshot {screenshot_path}: {e}", exc_info=True)
            pdf.set_font(PDF_FONT_FAMILY, size=PDF_BODY_FONT_SIZE)
            pdf.cell(0, PDF_LINE_HEIGHT_MEDIUM, f"Erro ao adicionar imagem: {e}", ln=True)