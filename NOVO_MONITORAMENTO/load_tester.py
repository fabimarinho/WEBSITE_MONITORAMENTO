"""
Módulo de testes de carga para simular múltiplos usuários.

Simula múltiplos usuários acessando o site concorrentemente, gerando
padrões realistas de carga e coletando métricas de latência.
"""
import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError as RequestsConnectionError

from config import Settings
from check import SiteChecker

logger = logging.getLogger(__name__)


@dataclass
class LoadTestResult:
    """Resultado de um teste de carga."""
    user_id: int
    request_number: int
    timestamp: str
    url: str
    status_code: Optional[int]
    response_time_ms: float
    ttfb_ms: float
    error: Optional[str]
    success: bool

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return asdict(self)


class LoadTester:
    """
    Executor de testes de carga e testes de stress.
    
    Simula múltiplos usuários (threads) fazendo requisições concorrentes
    ao site, coletando métricas de latência, erro e performance.
    """

    def __init__(self, settings: Settings, results_dir: Optional[Path] = None):
        """
        Inicializa o testador de carga.

        Args:
            settings: Configurações do sistema.
            results_dir: Diretório para salvar resultados (padrão: BASE_DIR/load_tests).
        """
        self.settings = settings
        self.results_dir = results_dir or (settings.BASE_DIR / "load_tests")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"LoadTester inicializado: results_dir={self.results_dir}")

    def run_load_test(
        self,
        num_users: int = 10,
        requests_per_user: int = 10,
        ramp_up_seconds: int = 30,
        think_time_ms: int = 500,
        timeout_seconds: int = 30,
    ) -> Dict[str, Any]:
        """
        Executa um teste de carga com múltiplos usuários simulados.

        Args:
            num_users: Número de usuários simultâneos (padrão: 10).
            requests_per_user: Requisições por usuário (padrão: 10).
            ramp_up_seconds: Tempo para ramp-up dos usuários (padrão: 30s).
            think_time_ms: Tempo de espera entre requisições por usuário (padrão: 500ms).
            timeout_seconds: Timeout para cada requisição (padrão: 30s).

        Returns:
            Dict com resultados agregados do teste.
        """
        logger.info(
            f"Iniciando teste de carga: "
            f"users={num_users}, requests={requests_per_user}, "
            f"ramp_up={ramp_up_seconds}s"
        )

        start_time = datetime.now(self.settings.tz)
        results: List[LoadTestResult] = []
        
        # Calcula intervalo de ramp-up entre usuários
        ramp_up_interval = ramp_up_seconds / num_users if num_users > 0 else 0
        
        with ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = []
            
            # Submete tasks para cada usuário
            for user_id in range(num_users):
                delay = user_id * ramp_up_interval
                future = executor.submit(
                    self._user_session,
                    user_id,
                    requests_per_user,
                    delay,
                    think_time_ms,
                    timeout_seconds,
                )
                futures.append(future)
            
            # Coleta resultados
            for future in as_completed(futures):
                user_results = future.result()
                results.extend(user_results)
        
        # Calcula estatísticas
        end_time = datetime.now(self.settings.tz)
        stats = self._calculate_stats(results, start_time, end_time)
        
        # Salva resultados
        self._save_results(results, stats)
        
        logger.info(
            f"Teste de carga concluído: "
            f"total_requests={len(results)}, "
            f"success_rate={stats['success_rate']:.2f}%, "
            f"avg_latency={stats['avg_latency_ms']:.2f}ms"
        )
        
        return stats

    def run_stress_test(
        self,
        max_users: int = 100,
        increment_users: int = 10,
        requests_per_increment: int = 5,
        timeout_seconds: int = 30,
    ) -> Dict[str, Any]:
        """
        Executa um teste de stress aumentando gradualmente a carga.

        Args:
            max_users: Número máximo de usuários a atingir.
            increment_users: Incremento de usuários por rodada.
            requests_per_increment: Requisições por rodada.
            timeout_seconds: Timeout para cada requisição.

        Returns:
            Dict com resultados por nível de carga.
        """
        logger.info(
            f"Iniciando teste de stress: "
            f"max_users={max_users}, increment={increment_users}"
        )

        stress_results = {
            "test_type": "stress",
            "start_time": datetime.now(self.settings.tz).isoformat(),
            "levels": [],
        }
        
        current_users = increment_users
        
        while current_users <= max_users:
            logger.info(f"Teste de stress com {current_users} usuários")
            
            level_result = self.run_load_test(
                num_users=current_users,
                requests_per_user=requests_per_increment,
                ramp_up_seconds=10,
                think_time_ms=200,
                timeout_seconds=timeout_seconds,
            )
            
            level_result["user_count"] = current_users
            stress_results["levels"].append(level_result)
            
            # Para se a taxa de erro ficar muito alta
            if level_result["error_rate"] > 50:
                logger.warning(
                    f"Teste de stress parado: "
                    f"taxa de erro {level_result['error_rate']:.2f}% com {current_users} usuários"
                )
                break
            
            current_users += increment_users
        
        stress_results["end_time"] = datetime.now(self.settings.tz).isoformat()
        
        # Salva resultados
        stress_file = self.results_dir / f"stress_test_{datetime.now(self.settings.tz).strftime('%Y%m%d_%H%M%S')}.json"
        with open(stress_file, "w", encoding="utf-8") as f:
            json.dump(stress_results, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"Resultados de stress test salvos em {stress_file}")
        return stress_results

    def _user_session(
        self,
        user_id: int,
        num_requests: int,
        initial_delay_seconds: float,
        think_time_ms: int,
        timeout_seconds: int,
    ) -> List[LoadTestResult]:
        """
        Simula uma sessão de usuário com múltiplas requisições.

        Args:
            user_id: ID do usuário.
            num_requests: Número de requisições a fazer.
            initial_delay_seconds: Delay inicial (ramp-up).
            think_time_ms: Tempo de espera entre requisições.
            timeout_seconds: Timeout para requisições.

        Returns:
            Lista de resultados das requisições.
        """
        # Aguarda ramp-up
        if initial_delay_seconds > 0:
            time.sleep(initial_delay_seconds)
        
        results: List[LoadTestResult] = []
        think_time_s = think_time_ms / 1000
        
        for request_num in range(num_requests):
            result = self._make_request(
                user_id,
                request_num,
                timeout_seconds,
            )
            results.append(result)
            
            # Think time (espera entre requisições)
            if request_num < num_requests - 1:
                time.sleep(think_time_s)
        
        return results

    def _make_request(
        self,
        user_id: int,
        request_number: int,
        timeout_seconds: int,
    ) -> LoadTestResult:
        """
        Faz uma requisição HTTP e coleta métricas.

        Args:
            user_id: ID do usuário.
            request_number: Número da requisição.
            timeout_seconds: Timeout.

        Returns:
            Resultado da requisição.
        """
        result = LoadTestResult(
            user_id=user_id,
            request_number=request_number,
            timestamp=datetime.now(self.settings.tz).isoformat(),
            url=self.settings.SITE_URL,
            status_code=None,
            response_time_ms=0.0,
            ttfb_ms=0.0,
            error=None,
            success=False,
        )
        
        try:
            start_time = time.time()
            
            response = requests.get(
                self.settings.SITE_URL,
                timeout=timeout_seconds,
                allow_redirects=True,
                stream=True,
            )
            
            # TTFB (Time To First Byte)
            ttfb_start = time.time()
            first_byte = False
            ttfb_ms = 0.0
            
            for chunk in response.iter_content(chunk_size=1):
                if not first_byte:
                    ttfb_ms = (time.time() - ttfb_start) * 1000
                    first_byte = True
                break
            
            # Lê resto da resposta
            for chunk in response.iter_content(chunk_size=8192):
                pass
            
            elapsed_time = (time.time() - start_time) * 1000
            
            result.status_code = response.status_code
            result.response_time_ms = elapsed_time
            result.ttfb_ms = ttfb_ms
            result.success = response.status_code == 200
            
        except Timeout as e:
            result.error = f"Timeout ({self.settings.SITE_URL})"
            result.response_time_ms = timeout_seconds * 1000
            
        except RequestsConnectionError as e:
            result.error = f"Connection error: {str(e)[:50]}"
            result.response_time_ms = (time.time() - start_time) * 1000
            
        except RequestException as e:
            result.error = f"Request error: {str(e)[:50]}"
            result.response_time_ms = (time.time() - start_time) * 1000
            
        except Exception as e:
            result.error = f"Unexpected error: {str(e)[:50]}"
            result.response_time_ms = (time.time() - start_time) * 1000
        
        return result

    def _calculate_stats(
        self,
        results: List[LoadTestResult],
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Any]:
        """Calcula estatísticas dos resultados."""
        if not results:
            return {"error": "No results"}
        
        # Separar sucessos e erros
        successes = [r for r in results if r.success]
        errors = [r for r in results if not r.success]
        
        # Calcular latências
        response_times = [r.response_time_ms for r in results]
        ttfb_times = [r.ttfb_ms for r in successes] if successes else [0]
        
        # Ordena para percentis
        response_times_sorted = sorted(response_times)
        
        success_rate = (len(successes) / len(results)) * 100 if results else 0
        error_rate = (len(errors) / len(results)) * 100 if results else 0
        
        # Calcula throughput (requisições por segundo)
        duration_seconds = (end_time - start_time).total_seconds()
        throughput = len(results) / duration_seconds if duration_seconds > 0 else 0
        
        # Agrupados por tipo de erro
        error_types = {}
        for error in errors:
            error_msg = error.error or "Unknown"
            error_types[error_msg] = error_types.get(error_msg, 0) + 1
        
        stats = {
            "test_type": "load",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": round(duration_seconds, 2),
            "total_requests": len(results),
            "successful_requests": len(successes),
            "failed_requests": len(errors),
            "success_rate": round(success_rate, 2),
            "error_rate": round(error_rate, 2),
            "throughput_rps": round(throughput, 2),
            "latency": {
                "min_ms": round(min(response_times), 2),
                "max_ms": round(max(response_times), 2),
                "avg_ms": round(sum(response_times) / len(response_times), 2),
                "p50_ms": round(response_times_sorted[len(response_times_sorted) // 2], 2),
                "p95_ms": round(
                    response_times_sorted[int(len(response_times_sorted) * 0.95)], 2
                ),
                "p99_ms": round(
                    response_times_sorted[int(len(response_times_sorted) * 0.99)], 2
                ),
            },
            "ttfb": {
                "avg_ms": round(sum(ttfb_times) / len(ttfb_times), 2) if ttfb_times else 0,
                "min_ms": round(min(ttfb_times), 2) if ttfb_times else 0,
                "max_ms": round(max(ttfb_times), 2) if ttfb_times else 0,
            },
            "error_breakdown": error_types,
        }
        
        return stats

    def _save_results(
        self,
        results: List[LoadTestResult],
        stats: Dict[str, Any],
    ) -> None:
        """Salva resultados em arquivo JSON."""
        try:
            timestamp = datetime.now(self.settings.tz).strftime("%Y%m%d_%H%M%S")
            
            # Arquivo de resultados detalhados
            results_file = self.results_dir / f"load_test_{timestamp}_results.jsonl"
            with open(results_file, "w", encoding="utf-8") as f:
                for result in results:
                    f.write(json.dumps(result.to_dict(), ensure_ascii=False, default=str) + "\n")
            
            # Arquivo de estatísticas
            stats_file = self.results_dir / f"load_test_{timestamp}_stats.json"
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(stats, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(
                f"Resultados salvos: {results_file} e {stats_file}"
            )
            
        except Exception as e:
            logger.error(f"Erro ao salvar resultados: {e}")

    def generate_load_report(self) -> str:
        """
        Gera um relatório HTML dos testes de carga recentes.

        Returns:
            HTML do relatório.
        """
        html = """
        <html>
        <head>
            <title>Relatório de Teste de Carga</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                .good { color: green; }
                .warning { color: orange; }
                .critical { color: red; }
            </style>
        </head>
        <body>
            <h1>Relatório de Teste de Carga</h1>
            <p>Gerado em: {timestamp}</p>
            
            <h2>Testes Realizados</h2>
            <table>
                <tr>
                    <th>Arquivo</th>
                    <th>Requisições</th>
                    <th>Taxa de Sucesso</th>
                    <th>Latência Média</th>
                    <th>Throughput</th>
                </tr>
                {rows}
            </table>
        </body>
        </html>
        """
        
        rows = []
        for stats_file in sorted(self.results_dir.glob("*_stats.json")):
            try:
                with open(stats_file, "r") as f:
                    stats = json.load(f)
                
                success_rate = stats.get("success_rate", 0)
                status_class = "good" if success_rate >= 95 else "warning" if success_rate >= 80 else "critical"
                
                row = f"""
                <tr>
                    <td>{stats_file.name}</td>
                    <td>{stats.get('total_requests', 'N/A')}</td>
                    <td class="{status_class}">{success_rate:.1f}%</td>
                    <td>{stats.get('latency', {}).get('avg_ms', 'N/A'):.2f}ms</td>
                    <td>{stats.get('throughput_rps', 'N/A'):.2f} req/s</td>
                </tr>
                """
                rows.append(row)
            except Exception as e:
                logger.warning(f"Erro ao ler {stats_file}: {e}")
        
        return html.format(
            timestamp=datetime.now(self.settings.tz).isoformat(),
            rows="\n".join(rows) if rows else "<tr><td colspan='5'>Nenhum teste encontrado</td></tr>",
        )
