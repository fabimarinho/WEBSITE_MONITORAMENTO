# Integração: Error History com Check.py

## 📋 Resumo

O módulo `check.py` foi integrado com `error_history.py` para automaticamente rastrear e registrar todos os erros de verificação de site, permitindo análise de padrões de falha.

## 🔧 Mudanças Realizadas

### 1. **Imports Adicionados**
```python
from error_history import ErrorHistory, ErrorType, ErrorSeverity
```

### 2. **Inicialização da ErrorHistory**
No `__init__` da classe `SiteChecker`:
```python
self.error_history = ErrorHistory(settings)
```

### 3. **Registro Automático de Erros**

#### SSL Errors
- Quando `ok_ssl = False`: Registra como `ErrorType.SSL_ERROR` com severidade `CRITICAL`
- Captura detalhes do certificado SSL para análise

#### HTTP Errors
Todos os 5 tipos de erros HTTP agora são registrados:
1. **HTTP Status Error**: Status code ≠ 200 → `ErrorType.HTTP_ERROR`
2. **HTTP Timeout**: Timeout após DEFAULT_HTTP_TIMEOUT (15s) → `ErrorType.HTTP_TIMEOUT`
3. **Connection Error**: Falha de conexão → `ErrorType.HTTP_ERROR`
4. **Request Exception**: Erro genérico em request → `ErrorType.HTTP_ERROR`
5. **Unexpected Error**: Erro não esperado → `ErrorType.HTTP_ERROR`

#### Playwright Errors
1. **Playwright Timeout**: Timeout no navegador → `ErrorType.PLAYWRIGHT_TIMEOUT`
2. **Playwright Interaction Error**: Falha na interação → `ErrorType.PLAYWRIGHT_ERROR`
3. **Unexpected Playwright Error**: Erro genérico → `ErrorType.PLAYWRIGHT_ERROR`

## 📊 Fluxo de Dados

```
SiteChecker.perform_check()
├── _do_ssl_check()
│   ├── Verifica SSL
│   └── Se falhar → error_history.record_error(ErrorType.SSL_ERROR)
├── _do_http_check()
│   ├── Verifica HTTP
│   └── Se falhar → error_history.record_error(ErrorType.HTTP_*)
└── _do_playwright_check()
    ├── Verifica Playwright
    └── Se falhar → error_history.record_error(ErrorType.PLAYWRIGHT_*)
```

## 🎯 Tipos de Erro Registrados

| Tipo de Erro | Error Type | Severidade | Exemplo |
|---|---|---|---|
| SSL falhou | `SSL_ERROR` | CRITICAL | Certificado expirado, inválido |
| HTTP timeout | `HTTP_TIMEOUT` | CRITICAL | Conexão pendurada por 15+ segundos |
| HTTP erro | `HTTP_ERROR` | WARNING | Status 500, 404, etc. |
| Playwright timeout | `PLAYWRIGHT_TIMEOUT` | CRITICAL | Elemento não encontrado em 30s |
| Playwright erro | `PLAYWRIGHT_ERROR` | WARNING | Falha na interação com página |

## 💾 Armazenamento

Os erros são automaticamente armazenados em:
- **error_history.jsonl**: Log de linha por linha de todos os erros
- **error_patterns.json**: Padrões detectados (recurr ências, picos horárias)
- **error_stats.json**: Estatísticas agregadas

Localização padrão: `NOVO_MONITORAMENTO/relatorio/`

## 🔍 Como Usar

### Verificar Erros Recentes
```python
from check import SiteChecker
from config import load_settings

settings = load_settings()
checker = SiteChecker(settings)
result = checker.perform_check()

# Os erros foram automaticamente registrados em error_history
# Para ver os erros:
history = checker.error_history
patterns = history.detect_patterns(days_lookback=7)
print(f"Erros detectados: {patterns['total_errors']}")
print(f"Padrões: {patterns['recurring_errors']}")
```

### Ver Confiabilidade
```python
reliability = checker.error_history.get_reliability_score(days_lookback=30)
mttr = checker.error_history.get_mttr(days_lookback=7)

print(f"Confiabilidade (30d): {reliability:.1f}%")
print(f"MTTR (7d): {mttr:.2f} minutos")
```

### Integração com Dashboard
O dashboard acessa automaticamente os dados de erro_history:
```python
from dashboard import HealthDashboard

dashboard = HealthDashboard(settings, port=8080)
dashboard.start()
# Navegue para http://localhost:8080
# Dashboard exibe todos os erros em tempo real
```

## 📝 Exemplo de Log

Um erro HTTP registrado em `error_history.jsonl`:
```json
{
  "timestamp": "2024-01-15 10:30:00 BRT",
  "error_type": "http_timeout",
  "severity": "CRITICAL",
  "message": "HTTP request timeout after 15s",
  "details": {"timeout_seconds": 15},
  "ok_ssl": true,
  "ok_http": false,
  "ok_playwright": true
}
```

## 🧪 Testes

Todos os testes de `check.py` passam com a integração:
```bash
pytest tests/test_check.py -v
# 9 passed in 1.04s
```

## ⚙️ Configuração

### Limpeza Automática de Erros Antigos
Por padrão, erros com mais de 90 dias são removidos:
```python
# Em error_history.py
history.clear_old_records(days=90)  # Executado automaticamente
```

Para customizar:
```python
history.clear_old_records(days=180)  # Manter últimos 180 dias
```

### Detecção de Padrões
Padrões são detectados quando um erro ocorre 3+ vezes:
```python
patterns = history.detect_patterns(days_lookback=7)
# recurring_errors conterá erros que ocorreram 3+ vezes na semana
```

## 🚀 Próximas Etapas

1. ✅ **Integração com check.py** (Concluída)
2. ⏳ **Integração com main.py** (Próxima)
   - Iniciar dashboard automaticamente
   - Executar error_history cleanup regularmente
3. ⏳ **Alertas Automáticos**
   - Enviar notificação quando padrão de erro é detectado
   - Alertas de threshold (ex: <95% confiabilidade)

## 📞 Suporte

Para mais informações sobre error_history, consulte:
- `GUIA_NOVAS_FUNCIONALIDADES.md` - Guia completo
- `error_history.py` - Documentação do código
