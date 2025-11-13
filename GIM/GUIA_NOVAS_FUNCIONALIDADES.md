# Guia de Uso - Novas Funcionalidades

## 🚀 Visão Geral

Este documento descreve como usar as três novas melhorias implementadas no sistema de monitoramento:

1. **Histórico de Erros & Detecção de Padrões** (`error_history.py`)
2. **Dashboard em Tempo Real** (`dashboard.py`)
3. **Testes de Carga** (`load_tester.py`)

---

## 1. 📊 Histórico de Erros & Detecção de Padrões

### Descrição

O módulo `error_history.py` rastreia todos os erros ao longo do tempo e detecta **padrões recorrentes**, permitindo identificar problemas sistemáticos.

### Funcionalidades

- ✅ Registra cada erro com timestamp, tipo, severidade e detalhes
- ✅ Detecta **erros recorrentes** (3+ ocorrências)
- ✅ Analisa **padrões de horário** (identifica horas com mais falhas)
- ✅ Calcula **score de confiabilidade** (%)
- ✅ Calcula **MTTR** (Mean Time To Recovery) em minutos
- ✅ Limpa registros antigos automaticamente
- ✅ Salva padrões em JSON para análise

### Arquivos Gerados

```
BASE_DIR/
├── error_history.jsonl          # Log de todos os erros (JSONL)
├── error_patterns.json          # Padrões detectados
└── error_stats.json             # Estatísticas e confiabilidade
```

### Como Usar

#### No código (exemplo integração em `check.py`):

```python
from error_history import ErrorHistory, ErrorType, ErrorSeverity

# Inicializa
error_history = ErrorHistory(settings)

# Registra um erro
error_history.record_error(
    error_type=ErrorType.SSL_EXPIRED,
    severity=ErrorSeverity.CRITICAL,
    message="Certificado expirou há 5 dias",
    details={"domain": "example.com", "expired_on": "2025-11-07"},
    ok_ssl=False,
    ok_http=True,
    ok_playwright=True
)

# Detecta padrões dos últimos 7 dias
patterns = error_history.detect_patterns(days_lookback=7)
print(f"Erros recorrentes: {patterns['recurring_errors']}")
print(f"Confiabilidade SSL: {patterns['component_reliability']['ssl']}%")

# Obtém score de confiabilidade
score = error_history.get_reliability_score(days_lookback=30)
print(f"Confiabilidade (30d): {score}%")

# Obtém MTTR
mttr = error_history.get_mttr(days_lookback=7)
print(f"MTTR (7d): {mttr} minutos")

# Resumo dos últimos 24 horas
summary = error_history.get_error_summary(hours_lookback=24)
print(f"Erros recentes: {summary['total_errors']}")

# Limpa registros antigos (mantém últimos 90 dias)
removed = error_history.clear_old_records(days_to_keep=90)
print(f"Registros removidos: {removed}")
```

#### Via linha de comando (teste rápido):

```bash
cd NOVO_MONITORAMENTO

# Python interativo
python -c "
from error_history import ErrorHistory
from config import load_settings

settings = load_settings()
history = ErrorHistory(settings)

# Verifica padrões
patterns = history.detect_patterns(days_lookback=7)
print(f'Padrões encontrados: {len(patterns.get(\"recurring_errors\", []))}')
"
```

### Exemplo de Resultado

```json
{
  "analysis_timestamp": "2025-11-12T15:30:00-03:00",
  "period_days": 7,
  "total_errors": 45,
  "error_types": {
    "playwright_timeout": 25,
    "http_performance": 12,
    "ssl_expiring_soon": 8
  },
  "recurring_errors": [
    {
      "error_type": "playwright_timeout",
      "count": 25,
      "percentage": 55.56
    },
    {
      "error_type": "http_performance",
      "count": 12,
      "percentage": 26.67
    }
  ],
  "time_patterns": {
    "hour_14": {"total_checks": 10, "errors": 8, "error_rate": 80.0},
    "hour_15": {"total_checks": 10, "errors": 7, "error_rate": 70.0},
    "worst_hour": "hour_14"
  },
  "component_reliability": {
    "ssl": 98.5,
    "http": 95.2,
    "playwright": 78.3
  }
}
```

### Tipos de Erro Suportados

```python
class ErrorType(Enum):
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
```

---

## 2. 🏥 Dashboard em Tempo Real

### Descrição

O módulo `dashboard.py` fornece uma interface web interativa para visualizar:
- Status atual de cada componente (SSL, HTTP, Playwright)
- Gráficos de confiabilidade
- Histórico de erros recentes
- Padrões de falha detectados
- Métricas de performance

### Funcionalidades

- ✅ Servidor web (Flask) na porta 8080
- ✅ Interface responsiva (funciona em móvel)
- ✅ Atualização automática a cada 30 segundos
- ✅ Gráficos interativos com Chart.js
- ✅ Exibe MTTR, confiabilidade por período
- ✅ Lista de erros recentes com severidade
- ✅ Detecção de padrões em tempo real

### Como Iniciar

#### Opção 1: Via Python Script

```python
from config import load_settings
from dashboard import HealthDashboard

settings = load_settings()
dashboard = HealthDashboard(settings, port=8080)
dashboard.start()

# Dashboard está rodando em http://0.0.0.0:8080
# Deixe rodando enquanto faz monitoramento
```

#### Opção 2: Via Scheduler (APScheduler)

Adicionar ao `main.py` para iniciar dashboard automaticamente:

```python
# No __init__ de MonitoringService
self.dashboard = HealthDashboard(settings, port=8080)
self.dashboard.start()

# No shutdown de MonitoringService
self.dashboard.stop()
```

#### Opção 3: Linha de comando

```bash
cd NOVO_MONITORAMENTO

python -c "
from config import load_settings
from dashboard import HealthDashboard

settings = load_settings()
dashboard = HealthDashboard(settings, port=8080)
dashboard.start()

print('Dashboard rodando em http://localhost:8080')
print('Pressione Ctrl+C para parar')

import time
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    dashboard.stop()
"
```

### Acessando o Dashboard

1. Abra navegador: `http://localhost:8080`
2. A página se atualiza automaticamente a cada 30 segundos
3. Visualize:
   - **Confiabilidade (24h, 7d)**: Taxa de sucesso em %
   - **MTTR**: Tempo médio de recuperação de falhas
   - **Erros Recentes**: Últimas 24 horas
   - **Gráfico de Padrões**: Taxa de erro por hora do dia
   - **Padrões Detectados**: Erros recorrentes com frequência

### APIs RESTful Disponíveis

#### GET `/api/health`

Retorna métricas de saúde:

```bash
curl http://localhost:8080/api/health
```

Resposta:

```json
{
  "timestamp": "2025-11-12T15:30:00-03:00",
  "reliability": {
    "24h": 98.5,
    "7d": 96.2,
    "30d": 95.8
  },
  "mttr_minutes": {
    "24h": 5.25,
    "7d": 8.5
  },
  "recent_errors": 3,
  "error_summary": {
    "period_hours": 24,
    "total_errors": 3,
    "errors_by_type": {
      "playwright_timeout": 2,
      "http_performance": 1
    }
  }
}
```

#### GET `/api/patterns`

Retorna padrões detectados:

```bash
curl http://localhost:8080/api/patterns
```

#### GET `/api/history`

Retorna histórico de erros recentes:

```bash
curl http://localhost:8080/api/history
```

### Interpretando o Dashboard

| Métrica | Valor Normal | Alerta | Crítico |
|---------|-----------|--------|---------|
| Confiabilidade | > 99% | 95-99% | < 95% |
| MTTR | < 5 min | 5-15 min | > 15 min |
| Taxa de Erro | < 1% | 1-5% | > 5% |

### Portas Alternativos

Se a porta 8080 está em uso:

```python
dashboard = HealthDashboard(settings, port=9090)
```

---

## 3. 🔥 Testes de Carga

### Descrição

O módulo `load_tester.py` simula múltiplos usuários acessando o site concorrentemente para:
- Medir como o site se comporta sob carga
- Identificar limite máximo de capacidade
- Detectar problemas de performance
- Coletar distribuição de latência

### Funcionalidades

- ✅ Teste de **carga** (múltiplos usuários simultâneos)
- ✅ Teste de **stress** (aumenta carga gradualmente até quebra)
- ✅ Coleta de latência (min, max, avg, p50, p95, p99)
- ✅ Medição de TTFB (Time To First Byte)
- ✅ Throughput (requisições por segundo)
- ✅ Classificação de erros por tipo
- ✅ Geração de relatório HTML

### Arquivos Gerados

```
BASE_DIR/load_tests/
├── load_test_20251112_153000_results.jsonl  # Detalhe de cada requisição
├── load_test_20251112_153000_stats.json     # Estatísticas agregadas
├── stress_test_20251112_154000.json         # Resultados de stress test
└── ... (outros testes)
```

### Como Usar

#### Teste de Carga Simples (10 usuários, 10 requisições cada)

```python
from config import load_settings
from load_tester import LoadTester

settings = load_settings()
tester = LoadTester(settings)

# Simula 10 usuários fazendo 10 requisições cada
# com ramp-up de 30 segundos
results = tester.run_load_test(
    num_users=10,
    requests_per_user=10,
    ramp_up_seconds=30,
    think_time_ms=500,
    timeout_seconds=30,
)

print(f"Taxa de sucesso: {results['success_rate']}%")
print(f"Latência média: {results['latency']['avg_ms']}ms")
print(f"P95: {results['latency']['p95_ms']}ms")
print(f"Throughput: {results['throughput_rps']} req/s")
```

#### Teste de Stress (aumenta carga até quebra)

```python
# Aumenta de 10 em 10 usuários até 100
results = tester.run_stress_test(
    max_users=100,
    increment_users=10,
    requests_per_increment=5,
    timeout_seconds=30,
)

print(f"Níveis de stress testados: {len(results['levels'])}")
for level in results['levels']:
    print(f"  {level['user_count']} usuários: {level['success_rate']}% sucesso")
```

#### Teste Customizado

```python
# Teste mais agressivo
tester.run_load_test(
    num_users=50,              # 50 usuários simultâneos
    requests_per_user=20,      # 20 requisições cada (total: 1000)
    ramp_up_seconds=60,        # Ramp-up de 1 minuto
    think_time_ms=200,         # Espera 200ms entre requisições
    timeout_seconds=60,        # Timeout de 60s por requisição
)
```

#### Linha de Comando

```bash
python -c "
from config import load_settings
from load_tester import LoadTester

settings = load_settings()
tester = LoadTester(settings)

# Teste de carga
print('Iniciando teste de carga...')
results = tester.run_load_test(num_users=20, requests_per_user=10)

print(f'✓ Sucesso: {results[\"success_rate\"]}%')
print(f'✓ Latência: {results[\"latency\"][\"avg_ms\"]}ms')
print(f'✓ P99: {results[\"latency\"][\"p99_ms\"]}ms')
print(f'✓ Throughput: {results[\"throughput_rps\"]} req/s')
"
```

### Interpretando Resultados

#### Arquivo de Estatísticas (`*_stats.json`)

```json
{
  "test_type": "load",
  "start_time": "2025-11-12T15:30:00-03:00",
  "end_time": "2025-11-12T15:35:00-03:00",
  "duration_seconds": 300.0,
  "total_requests": 1000,
  "successful_requests": 980,
  "failed_requests": 20,
  "success_rate": 98.0,
  "error_rate": 2.0,
  "throughput_rps": 3.33,
  "latency": {
    "min_ms": 150.0,
    "max_ms": 5200.0,
    "avg_ms": 850.0,
    "p50_ms": 750.0,
    "p95_ms": 2100.0,
    "p99_ms": 4500.0
  },
  "ttfb": {
    "avg_ms": 250.0,
    "min_ms": 100.0,
    "max_ms": 800.0
  },
  "error_breakdown": {
    "Timeout": 15,
    "Connection error": 5
  }
}
```

#### Interpretação das Métricas

| Métrica | O que significa | Valor Normal |
|---------|-----------------|--------------|
| **success_rate** | % de requisições com status 200 | > 99% |
| **throughput_rps** | Requisições por segundo | Depende da capacidade |
| **avg_ms** | Latência média | < 1000ms |
| **p95_ms** | 95% das requisições respondem em X ms | < 2000ms |
| **p99_ms** | 99% das requisições respondem em X ms | < 5000ms |
| **TTFB avg** | Tempo até primeiro byte | < 500ms |

### Cenários de Teste Recomendados

#### Teste 1: Verificação de Capacidade
```python
tester.run_load_test(num_users=10, requests_per_user=50)
```
**Objetivo**: Verificar se o site aguenta 10 usuários simultâneos

#### Teste 2: Stress Test
```python
tester.run_stress_test(max_users=100, increment_users=10)
```
**Objetivo**: Encontrar o ponto de quebra

#### Teste 3: Resistência (Soak Test)
```python
tester.run_load_test(
    num_users=5,
    requests_per_user=100,  # Muitas requisições
    think_time_ms=1000,
)
```
**Objetivo**: Verificar comportamento prolongado

#### Teste 4: Carga Pico
```python
tester.run_load_test(
    num_users=50,
    requests_per_user=10,
    ramp_up_seconds=10,  # Ramp-up rápido
)
```
**Objetivo**: Simular pico de tráfego repentino

---

## 🔗 Integração entre Componentes

Os três módulos funcionam juntos:

```
┌─────────────────────────────────────────────┐
│   Sistema de Monitoramento Principal        │
├─────────────────────────────────────────────┤
│  check.py (verifica site) + error_history   │
│         ↓                                   │
│  Registra erros → error_history.jsonl       │
└─────────────────────────────────────────────┘
         ↓                    ↓
    ┌────────────┐    ┌──────────────┐
    │ Histórico  │    │  Dashboard   │
    │ & Padrões  │    │ (Tempo Real) │
    │            │    │              │
    │ Detecta:   │    │ Exibe:       │
    │ • Padrões  │    │ • Gráficos   │
    │ • MTTR     │    │ • APIs       │
    │ • Confiab. │    │ • Alertas    │
    └────────────┘    └──────────────┘
                           ↓
                    Usuário acessa
                   http://localhost:8080
                            ↓
                   └──────────────────┐
                                      ↓
                        ┌──────────────────────┐
                        │   Load Tester        │
                        │ Simula múltiplos     │
                        │ usuários em paralelo │
                        │ Coleta latências     │
                        │ Gera relatório       │
                        └──────────────────────┘
```

---

## 📋 Checklist de Implementação

- [x] Módulo de histórico de erros (`error_history.py`)
- [x] Dashboard em tempo real (`dashboard.py`)
- [x] Teste de carga (`load_tester.py`)
- [x] Flask adicionado ao `requirements.txt`
- [ ] Integração com `check.py` (chamar `error_history.record_error()`)
- [ ] Integração com `main.py` (iniciar dashboard no boot)
- [ ] Testes unitários para novo módulos
- [ ] Documentação em `README.md`

---

## 🚨 Troubleshooting

### Dashboard não inicia

**Problema**: `Address already in use`

**Solução**: Mudar porta ou matar processo anterior

```bash
# Listar processos em porta 8080
netstat -an | findstr 8080

# Usar porta diferente
python -c "
from config import load_settings
from dashboard import HealthDashboard

settings = load_settings()
dashboard = HealthDashboard(settings, port=9090)
dashboard.start()
"
```

### Teste de carga falha com timeout

**Problema**: `Timeout ao conectar`

**Solução**: Aumentar timeout ou reduzir número de usuários

```python
tester.run_load_test(
    num_users=5,  # Reduzir
    timeout_seconds=60,  # Aumentar
)
```

### Histórico de erros vazio

**Problema**: Nenhum erro foi registrado

**Solução**: Verificar se `error_history.record_error()` está sendo chamado

```python
# Teste manual
from error_history import ErrorHistory, ErrorType, ErrorSeverity
from config import load_settings

settings = load_settings()
history = ErrorHistory(settings)

history.record_error(
    error_type=ErrorType.HTTP_TIMEOUT,
    severity=ErrorSeverity.WARNING,
    message="Teste manual",
    details={"test": True},
)

patterns = history.detect_patterns()
print(f"Erros: {patterns['total_errors']}")
```

---

## 📞 Próximos Passos

1. Integrar módulos com `check.py` e `main.py`
2. Adicionar testes unitários
3. Criar alertas automáticos baseados em padrões
4. Exportar métricas para Prometheus/Grafana
5. Adicionar exportação em PDF de relatórios

---

**Versão**: 1.0  
**Atualizado em**: 12 de Novembro de 2025
