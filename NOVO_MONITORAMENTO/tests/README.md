# Testes Automatizados

Este diretório contém os testes automatizados para o sistema de monitoramento.

## Estrutura

```
tests/
├── __init__.py          # Inicialização do pacote de testes
├── conftest.py          # Fixtures e configurações compartilhadas
├── test_config.py       # Testes para config.py
├── test_utils.py        # Testes para utils.py
├── test_ssl_check.py    # Testes para ssl_check.py
├── test_check.py        # Testes para check.py
└── test_report.py       # Testes para report.py
```

## Instalação

Instale as dependências de teste:

```bash
pip install -r requirements.txt
```

## Executando os Testes

### Executar todos os testes

```bash
pytest
```

### Executar testes com cobertura

```bash
pytest --cov=. --cov-report=html --cov-report=term-missing
```

### Executar testes específicos

```bash
# Testes de um módulo específico
pytest tests/test_config.py

# Testes de uma classe específica
pytest tests/test_config.py::TestSettings

# Testes de uma função específica
pytest tests/test_config.py::TestSettings::test_settings_creation
```

### Executar testes com verbosidade

```bash
pytest -v          # Verboso
pytest -vv         # Muito verboso
pytest -s          # Mostra output (print statements)
```

### Executar testes marcados

```bash
# Apenas testes unitários
pytest -m unit

# Apenas testes de integração
pytest -m integration

# Testes relacionados a SSL
pytest -m ssl
```

## Tipos de Testes

### Testes Unitários
Testam funções e classes isoladamente, usando mocks quando necessário.

### Testes de Integração
Testam a interação entre múltiplos componentes do sistema.

## Fixtures Disponíveis

As seguintes fixtures estão disponíveis em `conftest.py`:

- `temp_dir`: Diretório temporário para testes
- `sample_env_file`: Arquivo .env de exemplo
- `sample_settings`: Instância de Settings para testes
- `mock_requests`: Mock da biblioteca requests
- `mock_playwright`: Mock da biblioteca Playwright
- `sample_log_entry`: Entrada de log de exemplo
- `sample_logs`: Lista de logs de exemplo
- `reset_env`: Reseta variáveis de ambiente (automático)

## Cobertura de Testes

O objetivo é manter uma cobertura de código acima de 80%. Para verificar a cobertura:

```bash
pytest --cov=. --cov-report=html
```

Isso gera um relatório HTML em `htmlcov/index.html`.

## Boas Práticas

1. **Nomes Descritivos**: Use nomes de teste que descrevam claramente o que está sendo testado
2. **Arrange-Act-Assert**: Organize os testes em três fases: preparação, execução, verificação
3. **Isolamento**: Cada teste deve ser independente e não depender de outros testes
4. **Mocks**: Use mocks para dependências externas (HTTP, Playwright, etc.)
5. **Fixtures**: Reutilize fixtures para código comum de setup

## Exemplo de Teste

```python
def test_example_function_success(sample_settings: Settings):
    """Testa função de exemplo com sucesso."""
    # Arrange
    expected_result = "success"
    
    # Act
    result = example_function(sample_settings)
    
    # Assert
    assert result == expected_result
```

## Troubleshooting

### Erro: ModuleNotFoundError
Certifique-se de estar executando os testes do diretório raiz do projeto:
```bash
cd NOVO_MONITORAMENTO
pytest
```

### Erro: ImportError
Verifique se todas as dependências estão instaladas:
```bash
pip install -r requirements.txt
```

### Testes muito lentos
Use marcadores para pular testes lentos:
```bash
pytest -m "not slow"
```

