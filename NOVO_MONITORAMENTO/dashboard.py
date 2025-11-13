"""
Módulo de dashboard em tempo real para monitoramento de saúde do sistema.

Fornece uma interface web (Flask) para visualizar status, métricas e histórico
de erros em tempo real, com charts e atualizações automáticas.
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from threading import Thread
from typing import Dict, Any

from flask import Flask, render_template_string, jsonify, send_from_directory
from werkzeug.serving import make_server

from config import Settings
from error_history import ErrorHistory

logger = logging.getLogger(__name__)

# Configuração Flask
STATIC_DIR = Path(__file__).parent / "dashboard_static"


class HealthDashboard:
    """
    Dashboard em tempo real para monitoramento de saúde do sistema.
    
    Fornece:
    - Status atual dos componentes (SSL, HTTP, Playwright)
    - Gráficos de confiabilidade (últimas 24h, 7d, 30d)
    - Histórico de erros recentes
    - Padrões de falha detectados
    - Métricas de performance
    """

    def __init__(self, settings: Settings, port: int = 8080):
        """
        Inicializa o dashboard.

        Args:
            settings: Configurações do sistema.
            port: Porta para o servidor Flask (padrão: 8080).
        """
        self.settings = settings
        self.port = port
        self.error_history = ErrorHistory(settings)
        
        # Cria aplicação Flask
        self.app = Flask(__name__)
        self.server = None
        self.thread = None
        
        # Registra rotas
        self._register_routes()
        
        logger.info(f"HealthDashboard inicializado na porta {port}")

    def start(self) -> None:
        """Inicia o servidor Flask em thread separada."""
        if self.server is not None:
            logger.warning("Dashboard já está rodando")
            return
        
        self.server = make_server("0.0.0.0", self.port, self.app)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        
        logger.info(f"Dashboard iniciado em http://0.0.0.0:{self.port}")

    def stop(self) -> None:
        """Para o servidor Flask."""
        if self.server is None:
            return
        
        self.server.shutdown()
        self.server = None
        
        logger.info("Dashboard parado")

    def _register_routes(self) -> None:
        """Registra as rotas do Flask."""
        
        @self.app.route("/")
        def index() -> str:
            """Página principal do dashboard."""
            return render_template_string(self._get_html_template())

        @self.app.route("/api/health")
        def api_health() -> Dict[str, Any]:
            """API: Status de saúde atual."""
            try:
                reliability = {
                    "24h": self.error_history.get_reliability_score(days_lookback=1),
                    "7d": self.error_history.get_reliability_score(days_lookback=7),
                    "30d": self.error_history.get_reliability_score(days_lookback=30),
                }
                
                mttr = {
                    "24h": self.error_history.get_mttr(days_lookback=1),
                    "7d": self.error_history.get_mttr(days_lookback=7),
                }
                
                error_summary = self.error_history.get_error_summary(hours_lookback=24)
                
                return jsonify({
                    "timestamp": datetime.now(self.settings.tz).isoformat(),
                    "reliability": reliability,
                    "mttr_minutes": mttr,
                    "recent_errors": error_summary.get("total_errors", 0),
                    "error_summary": error_summary,
                })
            except Exception as e:
                logger.error(f"Erro na API /health: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/patterns")
        def api_patterns() -> Dict[str, Any]:
            """API: Padrões de falha detectados."""
            try:
                patterns = self.error_history.detect_patterns(days_lookback=7)
                return jsonify(patterns)
            except Exception as e:
                logger.error(f"Erro na API /patterns: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/history")
        def api_history() -> Dict[str, Any]:
            """API: Histórico recente de erros."""
            try:
                error_summary = self.error_history.get_error_summary(hours_lookback=24)
                return jsonify(error_summary)
            except Exception as e:
                logger.error(f"Erro na API /history: {e}")
                return jsonify({"error": str(e)}), 500

    def _get_html_template(self) -> str:
        """Retorna template HTML do dashboard."""
        return """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Health Dashboard - Sistema de Monitoramento</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        header {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        h1 {
            color: #333;
            font-size: 28px;
            margin-bottom: 10px;
        }

        .last-update {
            color: #666;
            font-size: 14px;
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        .card-title {
            color: #666;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }

        .card-value {
            color: #333;
            font-size: 32px;
            font-weight: bold;
            margin-bottom: 5px;
        }

        .card-subtitle {
            color: #999;
            font-size: 13px;
        }

        .status-good {
            color: #10b981;
        }

        .status-warning {
            color: #f59e0b;
        }

        .status-critical {
            color: #ef4444;
        }

        .chart-container {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            position: relative;
            height: 400px;
        }

        .chart-title {
            color: #333;
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 15px;
        }

        .chart-area {
            position: relative;
            height: calc(100% - 35px);
        }

        .error-list {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .error-item {
            border-left: 4px solid #ef4444;
            padding: 12px;
            margin-bottom: 10px;
            background: #f9fafb;
            border-radius: 4px;
        }

        .error-item.warning {
            border-left-color: #f59e0b;
        }

        .error-item.info {
            border-left-color: #3b82f6;
        }

        .error-type {
            color: #333;
            font-weight: 600;
            font-size: 14px;
            margin-bottom: 4px;
        }

        .error-message {
            color: #666;
            font-size: 13px;
            margin-bottom: 4px;
        }

        .error-time {
            color: #999;
            font-size: 12px;
        }

        .patterns-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }

        .pattern-item {
            background: #f3f4f6;
            padding: 12px;
            border-radius: 6px;
            border: 1px solid #e5e7eb;
        }

        .pattern-label {
            color: #666;
            font-size: 12px;
            font-weight: 600;
        }

        .pattern-value {
            color: #333;
            font-size: 18px;
            font-weight: 700;
            margin-top: 5px;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: #999;
        }

        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        @media (max-width: 768px) {
            .dashboard-grid {
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            }

            .card-value {
                font-size: 24px;
            }

            h1 {
                font-size: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🏥 Health Dashboard</h1>
            <div class="last-update">
                Última atualização: <span id="last-update">-</span>
            </div>
        </header>

        <!-- Métricas principais -->
        <div class="dashboard-grid" id="metrics">
            <div class="card">
                <div class="card-title">Confiabilidade (24h)</div>
                <div class="card-value" id="reliability-24h">-</div>
                <div class="card-subtitle">Taxa de sucesso</div>
            </div>

            <div class="card">
                <div class="card-title">Confiabilidade (7d)</div>
                <div class="card-value" id="reliability-7d">-</div>
                <div class="card-subtitle">Taxa de sucesso</div>
            </div>

            <div class="card">
                <div class="card-title">MTTR (24h)</div>
                <div class="card-value" id="mttr-24h">-</div>
                <div class="card-subtitle">Tempo médio de recuperação</div>
            </div>

            <div class="card">
                <div class="card-title">Erros Recentes (24h)</div>
                <div class="card-value" id="recent-errors">-</div>
                <div class="card-subtitle">Número de erros</div>
            </div>
        </div>

        <!-- Gráficos -->
        <div class="chart-container">
            <div class="chart-title">Padrão de Erros por Hora (7 dias)</div>
            <div class="chart-area">
                <canvas id="hourly-errors-chart"></canvas>
            </div>
        </div>

        <!-- Erros recentes -->
        <div class="error-list">
            <div class="chart-title">Erros Recentes</div>
            <div id="recent-error-list" class="loading">
                <div class="spinner"></div>
                Carregando...
            </div>
        </div>

        <!-- Padrões detectados -->
        <div style="background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-top: 20px;">
            <div class="chart-title">Padrões de Falha Detectados (7 dias)</div>
            <div id="patterns-container" class="patterns-grid">
                <div class="loading">
                    <div class="spinner"></div>
                    Analisando padrões...
                </div>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = '/api';
        let hourlyErrorsChart = null;

        // Atualiza dados a cada 30 segundos
        setInterval(updateDashboard, 30000);

        // Carrega dados iniciais
        document.addEventListener('DOMContentLoaded', updateDashboard);

        async function updateDashboard() {
            try {
                const [health, history, patterns] = await Promise.all([
                    fetch(API_BASE + '/health').then(r => r.json()),
                    fetch(API_BASE + '/history').then(r => r.json()),
                    fetch(API_BASE + '/patterns').then(r => r.json()),
                ]);

                updateMetrics(health);
                updateRecentErrors(history);
                updatePatterns(patterns);
                updateCharts(patterns);

                document.getElementById('last-update').textContent = new Date().toLocaleTimeString('pt-BR');
            } catch (error) {
                console.error('Erro ao atualizar dashboard:', error);
            }
        }

        function updateMetrics(health) {
            const setMetric = (id, value, unit = '') => {
                const elem = document.getElementById(id);
                if (elem) {
                    if (typeof value === 'number') {
                        elem.textContent = value.toFixed(1) + unit;
                    } else {
                        elem.textContent = value;
                    }
                    
                    // Define classe de cor
                    if (value >= 99) elem.classList.add('status-good');
                    else if (value >= 95) elem.classList.add('status-warning');
                    else elem.classList.add('status-critical');
                }
            };

            if (health.reliability) {
                setMetric('reliability-24h', health.reliability['24h'], '%');
                setMetric('reliability-7d', health.reliability['7d'], '%');
            }

            if (health.mttr_minutes) {
                const mttr24h = health.mttr_minutes['24h'];
                setMetric('mttr-24h', mttr24h > 0 ? mttr24h.toFixed(2) + ' min' : 'N/A');
            }

            if (health.recent_errors !== undefined) {
                setMetric('recent-errors', health.recent_errors);
            }
        }

        function updateRecentErrors(history) {
            const container = document.getElementById('recent-error-list');
            
            if (!history.recent_errors || history.recent_errors.length === 0) {
                container.innerHTML = '<p style="color: #10b981; text-align: center;">✓ Nenhum erro recente</p>';
                return;
            }

            container.innerHTML = history.recent_errors.map(error => `
                <div class="error-item ${getSeverityClass(error.severity)}">
                    <div class="error-type">${error.error_type}</div>
                    <div class="error-message">${error.message}</div>
                    <div class="error-time">${new Date(error.timestamp).toLocaleString('pt-BR')}</div>
                </div>
            `).join('');
        }

        function updatePatterns(patterns) {
            const container = document.getElementById('patterns-container');
            
            if (!patterns.recurring_errors || patterns.recurring_errors.length === 0) {
                container.innerHTML = '<p style="grid-column: 1/-1; color: #666;">Nenhum padrão recorrente detectado</p>';
                return;
            }

            container.innerHTML = patterns.recurring_errors.map(error => `
                <div class="pattern-item">
                    <div class="pattern-label">${error.error_type}</div>
                    <div class="pattern-value">${error.count}x</div>
                    <div class="pattern-label" style="margin-top: 8px; color: #999;">
                        ${error.percentage}% dos erros
                    </div>
                </div>
            `).join('');

            // Adiciona confiabilidade por componente
            if (patterns.component_reliability) {
                const reliability = patterns.component_reliability;
                const reliabilityHtml = `
                    <div class="pattern-item">
                        <div class="pattern-label">SSL</div>
                        <div class="pattern-value">${reliability.ssl.toFixed(1)}%</div>
                    </div>
                    <div class="pattern-item">
                        <div class="pattern-label">HTTP</div>
                        <div class="pattern-value">${reliability.http.toFixed(1)}%</div>
                    </div>
                    <div class="pattern-item">
                        <div class="pattern-label">Playwright</div>
                        <div class="pattern-value">${reliability.playwright.toFixed(1)}%</div>
                    </div>
                `;
                container.innerHTML += reliabilityHtml;
            }
        }

        function updateCharts(patterns) {
            const ctx = document.getElementById('hourly-errors-chart');
            if (!ctx) return;

            const timePatterns = patterns.time_patterns || {};
            
            // Extrai dados por hora
            const hours = [];
            const errorRates = [];
            
            for (let h = 0; h < 24; h++) {
                const hourKey = `hour_${String(h).padStart(2, '0')}`;
                const pattern = timePatterns[hourKey];
                hours.push(String(h).padStart(2, '0') + ':00');
                errorRates.push(pattern ? pattern.error_rate : 0);
            }

            if (hourlyErrorsChart) {
                hourlyErrorsChart.destroy();
            }

            hourlyErrorsChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: hours,
                    datasets: [{
                        label: 'Taxa de Erro (%)',
                        data: errorRates,
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        tension: 0.4,
                        fill: true,
                        pointRadius: 4,
                        pointBackgroundColor: '#667eea',
                        pointBorderColor: 'white',
                        pointBorderWidth: 2,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top',
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100,
                            ticks: {
                                callback: function(value) {
                                    return value + '%';
                                }
                            }
                        }
                    }
                }
            });
        }

        function getSeverityClass(severity) {
            if (severity === 'CRITICAL') return 'critical';
            if (severity === 'WARNING') return 'warning';
            return 'info';
        }
    </script>
</body>
</html>
        """
