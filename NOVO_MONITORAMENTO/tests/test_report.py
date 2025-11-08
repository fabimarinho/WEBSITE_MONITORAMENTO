"""
Testes para o módulo report.py.

Testa geração de relatórios PDF diários e mensais.
"""
import json
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from fpdf import FPDF

from config import Settings
from report import ReportGenerator


class TestReportGenerator:
    """Testes para a classe ReportGenerator."""
    
    def test_report_generator_initialization(self, sample_settings: Settings):
        """Testa inicialização do ReportGenerator."""
        generator = ReportGenerator(sample_settings)
        
        assert generator.settings == sample_settings
    
    def test_read_all_logs_empty_file(self, sample_settings: Settings):
        """Testa leitura de arquivo de log vazio."""
        generator = ReportGenerator(sample_settings)
        
        # Garante que o arquivo existe mas está vazio
        sample_settings.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        sample_settings.LOG_FILE.write_text("", encoding="utf-8")
        
        logs = generator._read_all_logs()
        
        assert isinstance(logs, list)
        assert len(logs) == 0
    
    def test_read_all_logs_valid_entries(self, sample_settings: Settings, sample_log_entry: dict):
        """Testa leitura de entradas válidas de log."""
        generator = ReportGenerator(sample_settings)
        
        # Cria arquivo de log com entradas válidas
        sample_settings.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(sample_settings.LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(sample_log_entry, f, ensure_ascii=False)
            f.write("\n")
            json.dump(sample_log_entry, ensure_ascii=False)
            f.write("\n")
        
        logs = generator._read_all_logs()
        
        assert len(logs) == 2
        assert logs[0]["site_url"] == sample_log_entry["site_url"]
    
    def test_read_all_logs_invalid_json(self, sample_settings: Settings):
        """Testa leitura de log com JSON inválido."""
        generator = ReportGenerator(sample_settings)
        
        sample_settings.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        sample_settings.LOG_FILE.write_text("invalid json\n", encoding="utf-8")
        
        # Não deve lançar exceção, apenas ignorar linha inválida
        logs = generator._read_all_logs()
        
        assert isinstance(logs, list)
        assert len(logs) == 0
    
    def test_calculate_daily_stats(self, sample_settings: Settings, sample_logs: list):
        """Testa cálculo de estatísticas diárias."""
        generator = ReportGenerator(sample_settings)
        
        stats = generator._calculate_daily_stats(sample_logs)
        
        assert isinstance(stats, dict)
        # Verifica estrutura
        for date_str, date_stats in stats.items():
            assert "total" in date_stats
            assert "ok" in date_stats
            assert "failures" in date_stats
    
    def test_group_incidents_by_date(self, sample_settings: Settings, sample_logs: list):
        """Testa agrupamento de incidentes por data."""
        generator = ReportGenerator(sample_settings)
        
        # Adiciona alguns incidentes (falhas)
        incident_logs = sample_logs.copy()
        incident_logs[0]["ok_http"] = False
        
        incidents = [
            log for log in incident_logs
            if not (log.get("ok_ssl", True) and log.get("ok_http") and log.get("ok_playwright"))
        ]
        
        grouped = generator._group_incidents_by_date(incidents)
        
        assert isinstance(grouped, dict)
    
    @patch('report.FPDF')
    def test_generate_daily_report(self, mock_fpdf, sample_settings: Settings, sample_logs: list):
        """Testa geração de relatório diário."""
        mock_pdf = Mock()
        mock_fpdf.return_value = mock_pdf
        
        generator = ReportGenerator(sample_settings)
        
        # Cria logs no arquivo
        sample_settings.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(sample_settings.LOG_FILE, "w", encoding="utf-8") as f:
            for log in sample_logs:
                json.dump(log, f, ensure_ascii=False)
                f.write("\n")
        
        report_path = generator.generate_daily_report(date.today())
        
        assert report_path is not None
        assert isinstance(report_path, Path)
        mock_pdf.add_page.assert_called()
        mock_pdf.output.assert_called()
    
    @patch('report.FPDF')
    def test_generate_monthly_report(self, mock_fpdf, sample_settings: Settings, sample_logs: list):
        """Testa geração de relatório mensal."""
        mock_pdf = Mock()
        mock_fpdf.return_value = mock_pdf
        
        generator = ReportGenerator(sample_settings)
        
        # Cria logs no arquivo com timestamps dos últimos 30 dias
        sample_settings.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        today = date.today()
        for i, log in enumerate(sample_logs):
            log_date = today - timedelta(days=i)
            log["timestamp"] = f"{log_date.isoformat()} 10:30:00"
        
        with open(sample_settings.LOG_FILE, "w", encoding="utf-8") as f:
            for log in sample_logs:
                json.dump(log, f, ensure_ascii=False)
                f.write("\n")
        
        report_path = generator.generate_monthly_report(today)
        
        assert report_path is not None
        assert isinstance(report_path, str)  # generate_monthly_report retorna string
        mock_pdf.add_page.assert_called()
        mock_pdf.output.assert_called()
    
    def test_write_performance_stats(self, sample_settings: Settings, sample_logs: list):
        """Testa escrita de estatísticas de performance."""
        generator = ReportGenerator(sample_settings)
        mock_pdf = Mock()
        
        generator._write_performance_stats(mock_pdf, sample_logs)
        
        # Verifica que métodos do PDF foram chamados
        assert mock_pdf.cell.called or mock_pdf.set_font.called
    
    def test_write_incident(self, sample_settings: Settings, sample_log_entry: dict):
        """Testa escrita de incidente no PDF."""
        generator = ReportGenerator(sample_settings)
        mock_pdf = Mock()
        
        # Cria um incidente (falha)
        incident = sample_log_entry.copy()
        incident["ok_http"] = False
        
        generator._write_incident(mock_pdf, 1, incident)
        
        assert mock_pdf.cell.called or mock_pdf.multi_cell.called

