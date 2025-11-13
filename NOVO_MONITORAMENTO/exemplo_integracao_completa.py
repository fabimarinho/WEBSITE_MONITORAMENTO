"""
Exemplo Integrado: Usando os 3 Novos Módulos Juntos

Este script demonstra como usar error_history, dashboard e load_tester
juntos em um exemplo completo e realista.
"""

import time
import logging
from pathlib import Path

from config import load_settings
from error_history import ErrorHistory, ErrorType, ErrorSeverity
from dashboard import HealthDashboard
from load_tester import LoadTester

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_1_basic_error_history():
    """
    Exemplo 1: Rastreamento de Erros e Detecção de Padrões
    
    Demonstra como registrar erros e detectar padrões.
    """
    print("\n" + "="*60)
    print("EXEMPLO 1: Histórico de Erros & Detecção de Padrões")
    print("="*60)
    
    settings = load_settings()
    history = ErrorHistory(settings)
    
    # Simular alguns erros
    print("\n✓ Registrando erros simulados...")
    
    errors = [
        (ErrorType.SSL_EXPIRING_SOON, "SSL vencendo em 14 dias"),
        (ErrorType.HTTP_TIMEOUT, "HTTP timeout após 30s"),
        (ErrorType.PLAYWRIGHT_TIMEOUT, "Playwright: elemento não encontrado"),
        (ErrorType.HTTP_PERFORMANCE, "HTTP muito lento: 5.2s"),
    ]
    
    for error_type, message in errors:
        history.record_error(
            error_type=error_type,
            severity=ErrorSeverity.WARNING,
            message=message,
            details={"test": "example", "recorded": True},
            ok_ssl=error_type != ErrorType.SSL_EXPIRING_SOON,
            ok_http=error_type != ErrorType.HTTP_TIMEOUT and error_type != ErrorType.HTTP_PERFORMANCE,
            ok_playwright=error_type != ErrorType.PLAYWRIGHT_TIMEOUT,
        )
        print(f"  • {error_type.value}: {message}")
    
    # Detectar padrões
    print("\n✓ Detectando padrões...")
    patterns = history.detect_patterns(days_lookback=7)
    
    print(f"\n  Período analisado: {patterns['period_days']} dias")
    print(f"  Total de erros: {patterns['total_errors']}")
    print(f"  Erros recorrentes (3+ ocorrências):")
    
    for recurring in patterns.get('recurring_errors', []):
        print(f"    • {recurring['error_type']}: {recurring['count']}x ({recurring['percentage']:.1f}%)")
    
    # Métricas por componente
    print(f"\n  Confiabilidade por componente:")
    reliability = patterns.get('component_reliability', {})
    for component, score in reliability.items():
        status = "✓" if score >= 95 else "⚠" if score >= 90 else "✗"
        print(f"    {status} {component.upper()}: {score:.1f}%")
    
    # Score de confiabilidade geral
    score = history.get_reliability_score(days_lookback=30)
    print(f"\n  Score geral de confiabilidade (30d): {score:.1f}%")
    
    # MTTR
    mttr = history.get_mttr(days_lookback=7)
    print(f"  MTTR (7d): {mttr:.2f} minutos")
    
    return history


def example_2_dashboard_preview():
    """
    Exemplo 2: Dashboard em Tempo Real
    
    Inicia o dashboard e mostra como acessá-lo.
    """
    print("\n" + "="*60)
    print("EXEMPLO 2: Dashboard em Tempo Real")
    print("="*60)
    
    settings = load_settings()
    dashboard = HealthDashboard(settings, port=8080)
    
    print("\n✓ Iniciando dashboard...")
    dashboard.start()
    
    print(f"\n  Dashboard disponível em: http://localhost:8080")
    print(f"  Porta: 8080 (customizável)")
    print(f"  Auto-atualização: a cada 30 segundos")
    
    print("\n  Abra o navegador e visite: http://localhost:8080")
    print("  O dashboard exibirá:")
    print("    • Confiabilidade (24h, 7d, 30d)")
    print("    • MTTR em tempo real")
    print("    • Gráfico de erros por hora do dia")
    print("    • Erros recentes com detalhes")
    print("    • Padrões detectados")
    
    # Manter rodando por um tempo (para demonstração)
    print("\n  Dashboard rodando (Ctrl+C para parar)...")
    try:
        time.sleep(10)  # Deixar rodando por 10 segundos
    except KeyboardInterrupt:
        pass
    
    dashboard.stop()
    print("  Dashboard parado.")
    
    return dashboard


def example_3_load_test():
    """
    Exemplo 3: Teste de Carga
    
    Executa um teste de carga simples.
    """
    print("\n" + "="*60)
    print("EXEMPLO 3: Teste de Carga")
    print("="*60)
    
    settings = load_settings()
    tester = LoadTester(settings)
    
    print("\n✓ Executando teste de carga...")
    print("  Configuração:")
    print("    • Usuários simultâneos: 5")
    print("    • Requisições por usuário: 5")
    print("    • Total de requisições: 25")
    print("    • Ramp-up: 15 segundos")
    print("    • Timeout: 30 segundos")
    
    results = tester.run_load_test(
        num_users=5,
        requests_per_user=5,
        ramp_up_seconds=15,
        think_time_ms=500,
        timeout_seconds=30,
    )
    
    print("\n✓ Teste concluído! Resultados:")
    print(f"\n  Requisições:")
    print(f"    • Total: {results['total_requests']}")
    print(f"    • Sucesso: {results['successful_requests']}")
    print(f"    • Falhas: {results['failed_requests']}")
    print(f"    • Taxa de sucesso: {results['success_rate']:.1f}%")
    
    print(f"\n  Performance:")
    latency = results['latency']
    print(f"    • Latência mín: {latency['min_ms']:.2f}ms")
    print(f"    • Latência máx: {latency['max_ms']:.2f}ms")
    print(f"    • Latência média: {latency['avg_ms']:.2f}ms")
    print(f"    • P50: {latency['p50_ms']:.2f}ms (mediana)")
    print(f"    • P95: {latency['p95_ms']:.2f}ms (95% das requisições)")
    print(f"    • P99: {latency['p99_ms']:.2f}ms (99% das requisições)")
    
    print(f"\n  TTFB (Time To First Byte):")
    ttfb = results['ttfb']
    print(f"    • Média: {ttfb['avg_ms']:.2f}ms")
    print(f"    • Mín: {ttfb['min_ms']:.2f}ms")
    print(f"    • Máx: {ttfb['max_ms']:.2f}ms")
    
    print(f"\n  Throughput: {results['throughput_rps']:.2f} requisições/segundo")
    print(f"  Duração: {results['duration_seconds']:.2f} segundos")
    
    # Análise de erros
    if results.get('error_breakdown'):
        print(f"\n  Detalhes de erros:")
        for error_type, count in results['error_breakdown'].items():
            print(f"    • {error_type}: {count}")
    
    # Arquivos gerados
    print(f"\n  Arquivos gerados:")
    print(f"    • {tester.results_dir}/load_test_*_results.jsonl")
    print(f"    • {tester.results_dir}/load_test_*_stats.json")
    
    return results


def example_4_stress_test():
    """
    Exemplo 4: Teste de Stress
    
    Executa teste de stress aumentando carga gradualmente.
    """
    print("\n" + "="*60)
    print("EXEMPLO 4: Teste de Stress (Aumenta Carga)")
    print("="*60)
    
    settings = load_settings()
    tester = LoadTester(settings)
    
    print("\n✓ Executando teste de stress...")
    print("  Configuração:")
    print("    • Usuários iniciais: 5")
    print("    • Incremento: 5 usuários por rodada")
    print("    • Máximo: 15 usuários")
    print("    • Requisições por rodada: 3")
    
    stress_results = tester.run_stress_test(
        max_users=15,
        increment_users=5,
        requests_per_increment=3,
    )
    
    print("\n✓ Teste de stress concluído!")
    print(f"\n  Níveis testados: {len(stress_results['levels'])}")
    
    for level in stress_results['levels']:
        users = level['user_count']
        success_rate = level['success_rate']
        latency = level['latency']['avg_ms']
        
        # Cor baseada na taxa de sucesso
        status = "✓" if success_rate >= 95 else "⚠" if success_rate >= 80 else "✗"
        
        print(f"\n  {status} Nível {users} usuários:")
        print(f"      Taxa de sucesso: {success_rate:.1f}%")
        print(f"      Latência média: {latency:.2f}ms")
        print(f"      Throughput: {level['throughput_rps']:.2f} req/s")


def example_5_integration():
    """
    Exemplo 5: Integração Completa
    
    Demonstra como os três módulos funcionam juntos.
    """
    print("\n" + "="*60)
    print("EXEMPLO 5: Integração Completa")
    print("="*60)
    
    settings = load_settings()
    
    print("\n✓ Cenário: Monitoramento Contínuo")
    print("\n  1. Verificação normal do site (check.py)")
    print("     └→ Registra resultado em error_history")
    
    print("\n  2. Error History analisa padrões")
    print("     ├→ Detecta erros recorrentes")
    print("     ├→ Calcula MTTR")
    print("     └→ Identifica horas com mais falhas")
    
    print("\n  3. Dashboard exibe em tempo real")
    print("     ├→ Gráficos de confiabilidade")
    print("     ├→ Histórico de erros")
    print("     └→ Padrões detectados")
    
    print("\n  4. Teste de carga (antes de deploy)")
    print("     ├→ Verifica capacidade")
    print("     ├→ Mede latência P95/P99")
    print("     └→ Identifica limite máximo")
    
    print("\n  Fluxo de dados:")
    print("     check.py")
    print("       ↓")
    print("     error_history.py  ←→  dashboard.py  (tempo real)")
    print("       ↓")
    print("     Padrões & Alertas")
    print("       ↓")
    print("     Usuário via http://localhost:8080")
    
    # Demonstrar os dados
    print("\n✓ Demonstração com dados reais:")
    
    # Criar dados
    history = ErrorHistory(settings)
    
    # Registrar alguns erros
    for i in range(5):
        history.record_error(
            error_type=ErrorType.PLAYWRIGHT_TIMEOUT,
            severity=ErrorSeverity.WARNING,
            message=f"Teste {i+1}",
            details={"index": i},
        )
    
    # Mostrar padrões
    patterns = history.detect_patterns(days_lookback=7)
    print(f"\n  • Total de erros registrados: {patterns['total_errors']}")
    print(f"  • Confiabilidade: {patterns['component_reliability']['playwright']:.1f}%")
    
    # Dashboard
    dashboard = HealthDashboard(settings)
    dashboard.start()
    print(f"\n  • Dashboard em: http://localhost:8080")
    time.sleep(2)
    dashboard.stop()
    
    # Load test
    tester = LoadTester(settings)
    print(f"\n  • Load tests salvos em: {tester.results_dir}")


if __name__ == "__main__":
    """
    Executa exemplos de uso dos três novos módulos.
    """
    
    print("\n" + "="*60)
    print("EXEMPLOS DE USO: Error History, Dashboard & Load Tester")
    print("="*60)
    
    try:
        # Exemplo 1: Error History
        history = example_1_basic_error_history()
        
        # Exemplo 2: Dashboard
        # (comentado por padrão para não ficar bloquado)
        # dashboard = example_2_dashboard_preview()
        
        # Exemplo 3: Load Test
        print("\nDescomenta para testar load test (pode levar um tempo)")
        # results = example_3_load_test()
        
        # Exemplo 4: Stress Test
        print("\nDescomenta para testar stress test (teste mais longo)")
        # example_4_stress_test()
        
        # Exemplo 5: Integração
        print("\nDescomenta para ver integração completa")
        # example_5_integration()
        
        print("\n" + "="*60)
        print("Exemplos concluídos!")
        print("="*60)
        print("\nPróximos passos:")
        print("1. Integre error_history com check.py")
        print("2. Inicie dashboard na sua aplicação")
        print("3. Execute load tests antes de fazer deploy")
        print("\nVeja GUIA_NOVAS_FUNCIONALIDADES.md para mais detalhes.")
        
    except Exception as e:
        logger.error(f"Erro durante execução: {e}", exc_info=True)
