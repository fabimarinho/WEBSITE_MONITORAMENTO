# Integração: Dashboard com Main.py

## 📋 Resumo

O módulo `main.py` foi integrado com `dashboard.py` para iniciar automaticamente o Flask web server quando o serviço de monitoramento é iniciado. O dashboard exibe dados em tempo real coletados pelo `error_history`.

## 🔧 Mudanças Realizadas

### 1. **Imports Adicionados**
```python
from dashboard import HealthDashboard
```

### 2. **Propriedade Adicionada à Classe `MonitoringService.__init__`**
```python
self.dashboard: Optional[HealthDashboard] = None
```

### 3. **Inicialização do Dashboard em `start()`**
O dashboard é iniciado automaticamente:
```python
self.dashboard = HealthDashboard(self.settings)
self.dashboard.start()  # Inicia em thread separada
```

**Características:**
- Dashboard inicia em thread separada (não bloqueia scheduler)
- Se houver erro na inicialização, monitoramento continua sem dashboard
- Log informa a URL: `http://localhost:8080`

### 4. **Shutdown do Dashboard em `shutdown()`**
O dashboard é parado gracefully:
```python
if self.dashboard:
    self.dashboard.stop()
```

### 5. **Configuração Adicionada em `config.py`**
- **`DASHBOARD_PORT`**: Porta do servidor Flask (padrão: 8080)
- Pode ser customizada via variável de ambiente
- Validação: 1024-65535

## 📊 Fluxo de Inicialização

```
main.py start()
├── Inicializa componentes (checker, report_gen)
├── Cria e configura scheduler
├── Agenda jobs (check, daily_report, monthly_report)
├── Configura signal handlers
├── ★ Inicia dashboard em thread separada
│   └── HealthDashboard conecta a error_history
│       └── Servidor Flask disponível em http://localhost:DASHBOARD_PORT
├── Inicia scheduler
└── Entra no loop principal
```

## 🎯 Fluxo de Shutdown

```
shutdown()
├── ★ Para dashboard primeiro
│   └── Flask server para gracefully
├── Para scheduler
│   └── Aguarda jobs terminarem (até 10s)
└── Finaliza
```

## 🌐 Acesso ao Dashboard

Após iniciar o serviço de monitoramento:
```bash
python main.py
```

O dashboard estará disponível em:
- **URL padrão**: `http://localhost:8080`
- **URL customizada**: `http://localhost:{DASHBOARD_PORT}` (se configurado)

## ⚙️ Configuração da Porta

### Via Variável de Ambiente
```bash
export DASHBOARD_PORT=9000
python main.py
```

### Via `.env`
```env
DASHBOARD_PORT=9000
```

### Via Config Python
```python
from config import Settings

settings = Settings(
    SITE_URL="...",
    PORTAL_URL="...",
    DASHBOARD_PORT=9000
)
```

## 📋 Validação de Configuração

- **Tipo**: Integer
- **Intervalo**: 1024 - 65535
- **Padrão**: 8080

## 🔍 Log de Saída Esperado

```
INFO     main:main.py:XX MonitoringService inicializado
INFO     main:main.py:XX Iniciando serviço de monitoramento...
INFO     main:main.py:XX Inicializando componentes...
INFO     dashboard:dashboard.py:XX Dashboard iniciado com sucesso em http://localhost:8080
INFO     main:main.py:XX Serviço de monitoramento iniciado com sucesso
INFO     main:main.py:XX Scheduler rodando: True
```

## 🚀 Exemplo de Uso

### Iniciar Serviço com Dashboard
```python
from main import MonitoringService
from config import load_settings

settings = load_settings()
service = MonitoringService(settings)

with service.lifecycle():
    service.run()

# Dashboard automaticamente inicia e para
```

### Acesso ao Dashboard
1. Inicie o serviço
2. Abra navegador em `http://localhost:8080`
3. Veja métricas em tempo real:
   - Confiabilidade (24h, 7d, 30d)
   - MTTR (Mean Time To Recovery)
   - Histórico de erros
   - Padrões detectados
   - Performance por componente

## 🧪 Testes

Todos os testes passam com a integração:
```bash
pytest tests/ -v
# 67 passed in 1.93s
```

### Cobertura de Testes
- ✅ Configuração validada (13 testes)
- ✅ Check.py integrado (9 testes)
- ✅ Utils (Slack) integrado (24 testes)
- ✅ SSL checking (11 testes)
- ✅ Report generation (7 testes)
- ✅ Config loading (3 testes)

## 📊 Dados Exibidos no Dashboard

O dashboard conecta automaticamente ao `error_history` e exibe:

### 1. **Métricas Principais**
- Confiabilidade (%)
- MTTR em minutos
- Contagem de erros recentes

### 2. **Gráficos**
- Erros por hora do dia
- Confiabilidade 24h/7d/30d
- Latência de resposta

### 3. **Histórico**
- Últimos 24h de erros
- Detalhes de cada erro
- Severity colorcoding (CRITICAL, WARNING, INFO)

### 4. **Padrões**
- Erros recorrentes (3+ ocorrências)
- Componentes problemáticos
- Pior horário do dia

## 🛡️ Tratamento de Erros

### Dashboard não inicia
- ❌ Log: `Erro ao iniciar dashboard: [erro]`
- ✅ Monitoramento continua funcionando normalmente
- ✅ Sistema não fica bloqueado

### Dashboard para durante execução
- ✅ Monitoramento continua no scheduler
- ⚠️ Dados ainda são coletados em `error_history`
- 🔄 Reinicie serviço para dashboard voltar

## 🔄 Integration Flow

```
MonitoringService
├── SiteChecker.perform_check()
│   ├── Coleta dados
│   └── Registra erros via error_history.record_error()
├── error_history.jsonl (armazena)
├── HealthDashboard
│   ├── Lê error_history
│   ├── Calcula padrões
│   └── Exibe via http://localhost:8080
└── ReportGenerator
    └── Gera relatórios (diário/mensal)
```

## 📞 Próximas Etapas

1. ✅ Integração check.py + error_history (Concluída)
2. ✅ Integração main.py + dashboard (Concluída)
3. ⏳ Alertas automáticos (Próximo)
   - Notificar quando padrão detectado
   - Alertas de threshold
   - Integração com Slack

## 📚 Documentos Relacionados

- `INTEGRACAO_ERROR_HISTORY.md` - Integração error_history com check.py
- `GUIA_NOVAS_FUNCIONALIDADES.md` - Guia completo das 3 novas features
- `dashboard.py` - Código-fonte do dashboard
- `error_history.py` - Código-fonte do histórico de erros
