#!/usr/bin/env python
"""
Script de teste rápido da integração completa.

Verifica se todos os módulos estão funcionando corretamente.
"""
import sys
from pathlib import Path

# Adiciona diretório atual ao path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("TESTE DE INTEGRAÇÃO COMPLETA")
print("=" * 60)

# Teste 1: Importar config
print("\n✓ Teste 1: Importando config...")
try:
    from config import load_settings, Settings
    print("  ✓ Config importado com sucesso")
except Exception as e:
    print(f"  ✗ Erro ao importar config: {e}")
    sys.exit(1)

# Teste 2: Carregar configurações
print("\n✓ Teste 2: Carregando configurações...")
try:
    settings = load_settings()
    print(f"  ✓ Configurações carregadas")
    print(f"    - SITE_URL: {settings.SITE_URL}")
    print(f"    - PORTAL_URL: {settings.PORTAL_URL}")
    print(f"    - DASHBOARD_PORT: {settings.DASHBOARD_PORT}")
except Exception as e:
    print(f"  ✗ Erro ao carregar config: {e}")
    sys.exit(1)

# Teste 3: Importar check
print("\n✓ Teste 3: Importando check...")
try:
    from check import SiteChecker
    print("  ✓ Check importado com sucesso")
except Exception as e:
    print(f"  ✗ Erro ao importar check: {e}")
    sys.exit(1)

# Teste 4: Criar SiteChecker
print("\n✓ Teste 4: Criando SiteChecker...")
try:
    checker = SiteChecker(settings)
    print("  ✓ SiteChecker criado com sucesso")
    print(f"    - Tem error_history: {hasattr(checker, 'error_history')}")
except Exception as e:
    print(f"  ✗ Erro ao criar SiteChecker: {e}")
    sys.exit(1)

# Teste 5: Importar dashboard
print("\n✓ Teste 5: Importando dashboard...")
try:
    from dashboard import HealthDashboard
    print("  ✓ Dashboard importado com sucesso")
except Exception as e:
    print(f"  ✗ Erro ao importar dashboard: {e}")
    sys.exit(1)

# Teste 6: Criar dashboard
print("\n✓ Teste 6: Criando HealthDashboard...")
try:
    dashboard = HealthDashboard(settings)
    print("  ✓ Dashboard criado com sucesso")
    print(f"    - Porta: {dashboard.port}")
    print(f"    - Tem error_history: {hasattr(dashboard, 'error_history')}")
except Exception as e:
    print(f"  ✗ Erro ao criar dashboard: {e}")
    sys.exit(1)

# Teste 7: Importar error_history
print("\n✓ Teste 7: Importando error_history...")
try:
    from error_history import ErrorHistory, ErrorType, ErrorSeverity
    print("  ✓ Error_history importado com sucesso")
except Exception as e:
    print(f"  ✗ Erro ao importar error_history: {e}")
    sys.exit(1)

# Teste 8: Criar error_history
print("\n✓ Teste 8: Criando ErrorHistory...")
try:
    history = ErrorHistory(settings)
    print("  ✓ ErrorHistory criado com sucesso")
except Exception as e:
    print(f"  ✗ Erro ao criar ErrorHistory: {e}")
    sys.exit(1)

# Teste 9: Importar load_tester
print("\n✓ Teste 9: Importando load_tester...")
try:
    from load_tester import LoadTester
    print("  ✓ Load_tester importado com sucesso")
except Exception as e:
    print(f"  ✗ Erro ao importar load_tester: {e}")
    sys.exit(1)

# Teste 10: Importar main
print("\n✓ Teste 10: Importando main...")
try:
    from main import MonitoringService
    print("  ✓ Main importado com sucesso")
except Exception as e:
    print(f"  ✗ Erro ao importar main: {e}")
    sys.exit(1)

# Teste 11: Criar MonitoringService
print("\n✓ Teste 11: Criando MonitoringService...")
try:
    service = MonitoringService(settings)
    print("  ✓ MonitoringService criado com sucesso")
    print(f"    - Tem scheduler: {service.scheduler is not None}")
    print(f"    - Tem checker: {service.checker is not None}")
    print(f"    - Tem dashboard: {service.dashboard is not None}")
except Exception as e:
    print(f"  ✗ Erro ao criar MonitoringService: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ TODOS OS TESTES PASSARAM!")
print("=" * 60)
print("\nO sistema está pronto para uso:")
print("  - Error History: Rastreando erros")
print("  - Dashboard: Será iniciado em http://localhost:8080")
print("  - Check.py: Verificando site periodicamente")
print("  - Load Tester: Disponível para testes de carga")
print("\nExecute 'python main.py' para iniciar o serviço.")
