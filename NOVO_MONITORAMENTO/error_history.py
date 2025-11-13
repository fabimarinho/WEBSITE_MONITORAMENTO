"""
Módulo de análise de histórico de erros e detecção de padrões.

Este módulo rastreia erros e falhas ao longo do tempo, detectando padrões
e tendências para alertas proativos sobre problemas recorrentes.
"""
import json
import logging
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from config import Settings

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Níveis de severidade de erro."""
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class ErrorType(Enum):
    """Tipos de erro detectáveis."""
    SSL_EXPIRED = "ssl_expired"
    SSL_INVALID = "ssl_invalid"
    SSL_EXPIRING_SOON = "ssl_expiring_soon"
    SSL_ERROR = "ssl_error"
    HTTP_TIMEOUT = "http_timeout"
    HTTP_ERROR = "http_error"
    HTTP_STATUS_ERROR = "http_status_error"
    HTTP_PERFORMANCE = "http_performance"
    PLAYWRIGHT_TIMEOUT = "playwright_timeout"
    PLAYWRIGHT_ERROR = "playwright_error"
    PLAYWRIGHT_ELEMENT_NOT_FOUND = "playwright_element_not_found"
    PLAYWRIGHT_INTERACTION_ERROR = "playwright_interaction_error"
    CONFIG_ERROR = "config_error"
    SLACK_ERROR = "slack_error"
    UNKNOWN = "unknown"


@dataclass
class ErrorRecord:
    """Registro de um erro detectado."""
    timestamp: str
    error_type: str
    severity: str
    message: str
    details: Dict[str, Any]
    ok_ssl: bool
    ok_http: bool
    ok_playwright: bool

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return asdict(self)


class ErrorHistory:
    """
    Gerenciador de histórico de erros e detecção de padrões.
    
    Responsabilidades:
    - Registrar erros em arquivo JSONL
    - Detectar padrões de falha recorrentes
    - Calcular estatísticas de confiabilidade
    - Gerar alertas para problemas detectados
    """

    def __init__(self, settings: Settings):
        """
        Inicializa o gerenciador de histórico.

        Args:
            settings: Configurações do sistema.
        """
        self.settings = settings
        self.history_file = settings.BASE_DIR / "error_history.jsonl"
        self.patterns_file = settings.BASE_DIR / "error_patterns.json"
        self.stats_file = settings.BASE_DIR / "error_stats.json"
        
        # Garante que os diretórios existem
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.debug(
            f"ErrorHistory inicializado: "
            f"history_file={self.history_file}, "
            f"patterns_file={self.patterns_file}"
        )

    def record_error(
        self,
        error_type: ErrorType,
        severity: ErrorSeverity,
        message: str,
        details: Dict[str, Any],
        ok_ssl: bool = True,
        ok_http: bool = True,
        ok_playwright: bool = True
    ) -> None:
        """
        Registra um erro no histórico.

        Args:
            error_type: Tipo do erro.
            severity: Nível de severidade.
            message: Mensagem do erro.
            details: Detalhes adicionais do erro.
            ok_ssl: Se verificação SSL passou.
            ok_http: Se verificação HTTP passou.
            ok_playwright: Se verificação Playwright passou.
        """
        try:
            record = ErrorRecord(
                timestamp=datetime.now(self.settings.tz).isoformat(),
                error_type=error_type.value,
                severity=severity.value,
                message=message,
                details=details,
                ok_ssl=ok_ssl,
                ok_http=ok_http,
                ok_playwright=ok_playwright
            )

            # Escreve no arquivo JSONL
            try:
                with open(self.history_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
                
                logger.debug(f"Erro registrado: {error_type.value}")
            except OSError as e:
                logger.error(f"Erro ao registrar erro no histórico: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Erro inesperado ao registrar erro: {e}", exc_info=True)

    def detect_patterns(self, days_lookback: int = 7) -> Dict[str, Any]:
        """
        Detecta padrões de falha nos últimos N dias.

        Args:
            days_lookback: Número de dias a analisar (padrão: 7).

        Returns:
            Dict com padrões detectados.
        """
        try:
            # Lê histórico
            records = self._read_history(days_lookback)
            
            if not records:
                logger.info("Nenhum erro nos últimos dias para análise de padrões")
                return {
                    "period_days": days_lookback,
                    "total_errors": 0,
                    "error_types": {},
                    "recurring_errors": [],
                    "time_patterns": {},
                    "severity_distribution": {},
                }

            # Análise de tipo de erro
            error_types = Counter([r["error_type"] for r in records])
            
            # Análise de severidade
            severity_dist = Counter([r["severity"] for r in records])
            
            # Identifica erros recorrentes (3+ ocorrências)
            recurring_errors = [
                {
                    "error_type": error_type,
                    "count": count,
                    "percentage": round((count / len(records)) * 100, 2)
                }
                for error_type, count in error_types.items()
                if count >= 3
            ]
            
            # Padrões de horário (agrupa por hora do dia)
            time_patterns = self._analyze_time_patterns(records)
            
            # Padrão SSL
            ssl_failures = sum(1 for r in records if not r["ok_ssl"])
            http_failures = sum(1 for r in records if not r["ok_http"])
            playwright_failures = sum(1 for r in records if not r["ok_playwright"])
            
            # Calcula confiabilidade
            reliability = {
                "ssl": round((1 - ssl_failures / len(records)) * 100, 2) if records else 100,
                "http": round((1 - http_failures / len(records)) * 100, 2) if records else 100,
                "playwright": round((1 - playwright_failures / len(records)) * 100, 2) if records else 100,
            }
            
            patterns = {
                "analysis_timestamp": datetime.now(self.settings.tz).isoformat(),
                "period_days": days_lookback,
                "total_errors": len(records),
                "error_types": dict(error_types),
                "recurring_errors": recurring_errors,
                "time_patterns": time_patterns,
                "severity_distribution": dict(severity_dist),
                "component_reliability": reliability,
                "last_error": records[-1] if records else None,
            }
            
            # Salva padrões em arquivo
            self._save_patterns(patterns)
            
            logger.info(f"Padrões detectados: {len(recurring_errors)} erros recorrentes")
            return patterns
            
        except Exception as e:
            logger.error(f"Erro ao detectar padrões: {e}", exc_info=True)
            return {"error": str(e)}

    def get_reliability_score(self, days_lookback: int = 30) -> float:
        """
        Calcula score de confiabilidade (0-100%).

        Args:
            days_lookback: Número de dias a considerar.

        Returns:
            Score de confiabilidade em percentual.
        """
        try:
            records = self._read_history(days_lookback)
            
            if not records:
                return 100.0  # Sem erros = 100% confiável
            
            # Contar sucessos (todos os componentes OK)
            successes = sum(
                1 for r in records
                if r["ok_ssl"] and r["ok_http"] and r["ok_playwright"]
            )
            
            reliability = (successes / len(records)) * 100
            return round(reliability, 2)
            
        except Exception as e:
            logger.error(f"Erro ao calcular score de confiabilidade: {e}")
            return 0.0

    def get_mttr(self, error_type: Optional[str] = None, days_lookback: int = 30) -> float:
        """
        Calcula MTTR (Mean Time To Recovery) em minutos.

        Args:
            error_type: Tipo de erro específico (optional).
            days_lookback: Número de dias a considerar.

        Returns:
            MTTR em minutos.
        """
        try:
            records = self._read_history(days_lookback)
            
            if error_type:
                records = [r for r in records if r["error_type"] == error_type]
            
            if not records or len(records) < 2:
                return 0.0  # Não há dados suficientes
            
            # Agrupa por tipo de erro, encontra períodos de falha
            failures: List[Tuple[datetime, datetime]] = []
            in_failure = False
            failure_start = None
            
            for record in sorted(records, key=lambda x: x["timestamp"]):
                has_error = not (record["ok_ssl"] and record["ok_http"] and record["ok_playwright"])
                
                if has_error and not in_failure:
                    failure_start = datetime.fromisoformat(record["timestamp"])
                    in_failure = True
                elif not has_error and in_failure:
                    failure_end = datetime.fromisoformat(record["timestamp"])
                    failures.append((failure_start, failure_end))
                    in_failure = False
            
            if not failures:
                return 0.0
            
            # Calcula média de tempo de recuperação
            recovery_times = [
                (end - start).total_seconds() / 60
                for start, end in failures
            ]
            
            mttr = sum(recovery_times) / len(recovery_times)
            return round(mttr, 2)
            
        except Exception as e:
            logger.error(f"Erro ao calcular MTTR: {e}")
            return 0.0

    def get_error_summary(self, hours_lookback: int = 24) -> Dict[str, Any]:
        """
        Retorna resumo de erros das últimas N horas.

        Args:
            hours_lookback: Número de horas a considerar.

        Returns:
            Dict com resumo de erros.
        """
        try:
            cutoff_time = datetime.now(self.settings.tz) - timedelta(hours=hours_lookback)
            records = self._read_history_from_file()
            
            recent_records = [
                r for r in records
                if datetime.fromisoformat(r["timestamp"]) >= cutoff_time
            ]
            
            if not recent_records:
                return {
                    "period_hours": hours_lookback,
                    "total_errors": 0,
                    "errors": [],
                    "most_common_error": None,
                }
            
            # Agrupa por tipo de erro
            error_groups = defaultdict(list)
            for record in recent_records:
                error_groups[record["error_type"]].append(record)
            
            # Encontra erro mais comum
            most_common = max(error_groups.items(), key=lambda x: len(x[1]))
            
            return {
                "period_hours": hours_lookback,
                "total_errors": len(recent_records),
                "errors_by_type": {k: len(v) for k, v in error_groups.items()},
                "most_common_error": {
                    "type": most_common[0],
                    "count": len(most_common[1]),
                },
                "recent_errors": recent_records[-5:],  # Últimos 5
            }
            
        except Exception as e:
            logger.error(f"Erro ao gerar resumo: {e}")
            return {"error": str(e)}

    def _read_history(self, days_lookback: int) -> List[Dict[str, Any]]:
        """Lê histórico dos últimos N dias."""
        cutoff_time = datetime.now(self.settings.tz) - timedelta(days=days_lookback)
        records = self._read_history_from_file()
        
        return [
            r for r in records
            if datetime.fromisoformat(r["timestamp"]) >= cutoff_time
        ]

    def _read_history_from_file(self) -> List[Dict[str, Any]]:
        """Lê todos os registros de erro do arquivo."""
        try:
            if not self.history_file.exists():
                return []
            
            records = []
            with open(self.history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            logger.warning(f"Linha JSON inválida: {line}")
            
            return records
        except Exception as e:
            logger.error(f"Erro ao ler histórico: {e}")
            return []

    def _analyze_time_patterns(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analisa padrões de falha por hora do dia."""
        hourly_errors = defaultdict(int)
        hourly_total = defaultdict(int)
        
        for record in records:
            try:
                ts = datetime.fromisoformat(record["timestamp"])
                hour = ts.hour
                hourly_total[hour] += 1
                
                if not (record["ok_ssl"] and record["ok_http"] and record["ok_playwright"]):
                    hourly_errors[hour] += 1
            except Exception:
                pass
        
        # Calcula taxa de erro por hora
        patterns = {}
        for hour in range(24):
            if hourly_total[hour] > 0:
                error_rate = (hourly_errors[hour] / hourly_total[hour]) * 100
                patterns[f"hour_{hour:02d}"] = {
                    "total_checks": hourly_total[hour],
                    "errors": hourly_errors[hour],
                    "error_rate": round(error_rate, 2),
                }
        
        # Identifica horas com mais erros
        if patterns:
            worst_hour = max(
                patterns.items(),
                key=lambda x: x[1]["error_rate"]
            )
            patterns["worst_hour"] = worst_hour[0]
        
        return patterns

    def _save_patterns(self, patterns: Dict[str, Any]) -> None:
        """Salva padrões em arquivo JSON."""
        try:
            with open(self.patterns_file, "w", encoding="utf-8") as f:
                json.dump(patterns, f, ensure_ascii=False, indent=2, default=str)
            
            logger.debug(f"Padrões salvos em {self.patterns_file}")
        except Exception as e:
            logger.error(f"Erro ao salvar padrões: {e}")

    def clear_old_records(self, days_to_keep: int = 90) -> int:
        """
        Remove registros mais antigos que N dias.

        Args:
            days_to_keep: Número de dias a manter.

        Returns:
            Número de registros removidos.
        """
        try:
            if not self.history_file.exists():
                return 0
            
            cutoff_time = datetime.now(self.settings.tz) - timedelta(days=days_to_keep)
            records = self._read_history_from_file()
            
            recent_records = [
                r for r in records
                if datetime.fromisoformat(r["timestamp"]) >= cutoff_time
            ]
            
            removed_count = len(records) - len(recent_records)
            
            # Reescreve arquivo com apenas registros recentes
            with open(self.history_file, "w", encoding="utf-8") as f:
                for record in recent_records:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            
            logger.info(f"Limpeza de histórico: {removed_count} registros removidos")
            return removed_count
            
        except Exception as e:
            logger.error(f"Erro ao limpar histórico: {e}")
            return 0
