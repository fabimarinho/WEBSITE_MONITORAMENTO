# Tipos de Erros Detectáveis pelo Sistema de Monitoramento

Este documento lista todos os tipos de erros que o programa de monitoramento consegue detectar e registrar.

---

## 📋 Resumo Executivo

O sistema de monitoramento realiza **3 verificações principais**:
1. **Verificação SSL/TLS** - Certificados digitais e segurança
2. **Verificação HTTP** - Disponibilidade e performance da aplicação
3. **Verificação Playwright** - Funcionalidade e fluxos de interação com a interface

---

## 🔒 1. ERROS DE CERTIFICADO SSL/TLS

### 1.1 Certificado Expirado
- **Detecção**: Verifica a data de expiração do certificado
- **Mensagem de Erro**: `Certificado EXPIRADO há [N] dias`
- **Impacto**: Site não carrega ou browsers mostram aviso de segurança
- **Status**: ❌ CRÍTICO

### 1.2 Certificado Expirando em Breve
- **Detecção**: Compara data de expiração com data atual + `SSL_EXPIRATION_WARNING_DAYS` (padrão: 30 dias)
- **Mensagem de Erro**: `Certificado expira em [N] dias`
- **Impacto**: Prepare-se para renovar antes que expire
- **Status**: ⚠️ AVISO

### 1.3 Certificado Inválido
- **Detecção**: Validação de assinatura e cadeia de certificados
- **Possíveis Causas**:
  - Certificado auto-assinado não confiável
  - Cadeia de certificados incompleta
  - Certificado revogado (CRL/OCSP)
  - Assinatura inválida
- **Status**: ❌ CRÍTICO

### 1.4 Hostname Não Corresponde
- **Detecção**: Verifica se o nome do domínio no certificado (CN/SAN) corresponde à URL
- **Possíveis Causas**:
  - Certificado para domínio incorreto
  - Configuração de DNS/proxy errada
- **Status**: ❌ CRÍTICO

### 1.5 Versão TLS Insegura
- **Detecção**: Verifica se a conexão usa TLS 1.2 ou superior (mínimo seguro)
- **Possíveis Causas**:
  - Servidor configurado com SSL 3.0, TLS 1.0 ou TLS 1.1
  - Servidor desatualizado
- **Status**: ⚠️ AVISO (Segurança)

### 1.6 Cipher Suite Fraco
- **Detecção**: Identifica algoritmos de criptografia considerados fracos
- **Exemplos**:
  - Cifras com exportação (40-bit)
  - RC4
  - DES
  - Sem Perfect Forward Secrecy (PFS)
- **Status**: ⚠️ AVISO (Segurança)

### 1.7 Erro na Conexão SSL
- **Possíveis Causas**:
  - Porta 443 fechada/bloqueada
  - Firewall rejeitando conexão
  - Timeout na conexão
  - Erro ao resolver hostname
  - Certificado mal formado
- **Mensagem**: `Error: [error_type]`
- **Status**: ❌ CRÍTICO

---

## 🌐 2. ERROS DE VERIFICAÇÃO HTTP

### 2.1 Status Code Incorreto
- **Detecção**: Verifica se o status code é 200 (OK)
- **Possíveis Status**:
  - `3xx` - Redirecionamentos (a aplicação pode estar em manutenção)
  - `4xx` - Erros de cliente
    - `400` - Bad Request
    - `401` - Não autorizado
    - `403` - Acesso proibido
    - `404` - Página não encontrada
  - `5xx` - Erros de servidor
    - `500` - Erro interno do servidor
    - `502` - Bad Gateway
    - `503` - Serviço indisponível
    - `504` - Gateway Timeout
- **Status**: ❌ CRÍTICO

### 2.2 Timeout na Conexão HTTP
- **Detecção**: Requisição excede tempo limite (padrão: 15 segundos)
- **Possíveis Causas**:
  - Servidor respondendo muito lentamente
  - Servidor offline/não respondendo
  - Problema de rede
  - Servidor sobrecarregado
  - Firewall bloqueando/atrasando tráfego
- **Status**: ❌ CRÍTICO

### 2.3 Erro de Conexão
- **Possíveis Causas**:
  - Servidor offline
  - DNS não consegue resolver o hostname
  - Porta não está aberta
  - Firewall bloqueando conexão
  - Erro de rede geral
- **Mensagem**: `Connection error: [details]`
- **Status**: ❌ CRÍTICO

### 2.4 SSL/TLS Handshake Error
- **Possíveis Causas**:
  - Certificado inválido
  - Protocolo SSL/TLS não suportado
  - Versionamento incompatível
- **Status**: ❌ CRÍTICO

### 2.5 Redirecionamentos Excessivos
- **Detecção**: Múltiplos redirecionamentos (3xx) em cascata
- **Possíveis Causas**:
  - Loop de redirecionamento
  - Configuração incorreta de reverse proxy
  - Problema de HTTPS/HTTP
- **Status**: ⚠️ AVISO

### 2.6 Resposta Muito Lenta (Performance)
- **Detecção**: Tempo de resposta (TTFB/Total) acima de limites saudáveis
- **Métricas Monitoradas**:
  - **TTFB** (Time To First Byte): Tempo até primeira resposta
  - **Total Time**: Tempo total da requisição
  - **Content Length**: Tamanho da resposta
  - **Download Speed**: Velocidade de download em Mbps
- **Possíveis Causas**:
  - Servidor sobrecarregado
  - Conexão lenta
  - Processamento lento no servidor
  - Grandes volumes de dados sendo transferidos
- **Status**: ⚠️ AVISO (Performance)

### 2.7 Content-Type Inesperado
- **Detecção**: Resposta não é do tipo esperado (ex: HTML recebido quando esperava JSON)
- **Possíveis Causas**:
  - Erro no servidor
  - Configuração incorreta
  - Cache desatualizado
- **Status**: ⚠️ AVISO

### 2.8 Tamanho de Resposta Anormal
- **Detecção**: Resposta muito pequena (< 100 bytes) ou muito grande
- **Possíveis Causas**:
  - Página de erro em vez de conteúdo real
  - Erro ao processar requisição
  - Resposta incompleta
- **Status**: ⚠️ AVISO

---

## 🎭 3. ERROS DE VERIFICAÇÃO PLAYWRIGHT (Interface/Funcionalidade)

### 3.1 Timeout ao Carregar a Página
- **Detecção**: Página não carrega dentro do tempo limite (padrão: 30 segundos)
- **Possíveis Causas**:
  - Servidor respondendo muito lentamente
  - Recurso externo não carregando
  - JavaScript em loop ou travado
  - Servidor offline
- **Status**: ❌ CRÍTICO

### 3.2 Timeout ao Localizar Elemento
- **Detecção**: Elemento esperado não aparece no timeout (padrão: 5-10 segundos)
- **Seletores Monitorados**:
  - **Select de Organização**: `[data-testid="org-select"]` ou `select:has-text("Organização")`
  - **Lista de Documentos**: `[data-testid="doc-list"]` ou `.documents-list`
  - **Link do Documento**: `[data-testid="doc-link"]` ou `a:has-text("Visualizar")`
  - **Visualizador de Documento**: `iframe[src*="pdf"]` ou `embed[type="application/pdf"]`
- **Possíveis Causas**:
  - Layout da página foi alterado
  - JavaScript que renderiza o elemento não foi executado
  - Elemento renderizado dinamicamente mas não apareceu
  - Página com erro (erro 500, etc)
  - CSS `display: none` ou `visibility: hidden`
- **Status**: ❌ CRÍTICO

### 3.3 Erro ao Selecionar Opção no Select
- **Detecção**: Falha ao executar `select_option()` com label `SUCCESS_ORG_LABEL`
- **Possíveis Causas**:
  - Rótulo da opção foi alterado
  - Select é do tipo personalizado (não é `<select>` HTML nativo)
  - Opção não existe na lista
  - Select desabilitado ou invisível
- **Status**: ❌ CRÍTICO

### 3.4 Erro ao Clicar em Elemento
- **Possíveis Causas**:
  - Elemento não é clicável
  - Elemento está coberto por outro elemento
  - JavaScript event listener não está registrado
  - Elemento foi removido do DOM
  - Timeout
- **Status**: ❌ CRÍTICO

### 3.5 JavaScript Error / Console Error
- **Detecção**: Erros JavaScript captados no console do navegador
- **Possíveis Causas**:
  - Erro em código JavaScript da página
  - Biblioteca JavaScript com problema
  - Erro ao carregar recurso (script externo, API, etc)
- **Status**: ⚠️ AVISO

### 3.6 Erro ao Abrir Documento (PDF/Visualizador)
- **Detecção**: Iframe/embed do documento não aparece dentro do timeout
- **Possíveis Causas**:
  - Documento não conseguiu ser processado
  - Erro ao gerar visualização
  - Servidor de PDF offline
  - Permissões insuficientes
  - Tipo de arquivo não suportado
- **Status**: ❌ CRÍTICO

### 3.7 Erro ao Fazer Screenshot (Falha)
- **Detecção**: Não consegue capturar screenshot da página com erro
- **Possíveis Causas**:
  - Permissões de arquivo insuficientes
  - Disco cheio
  - Caminho inválido
- **Status**: ⚠️ AVISO (não afeta monitoramento principal)

### 3.8 Memory/Performance Anormal (JavaScript)
- **Detecção**: Métricas de memória ou performance capturadas na página
- **Métricas Monitoradas**:
  - **DNS Time**: Tempo de resolução DNS
  - **TCP Time**: Tempo de handshake TCP
  - **SSL Time**: Tempo de handshake SSL
  - **TTFB**: Time To First Byte
  - **Download Time**: Tempo de download
  - **DOM Processing**: Tempo de processamento do DOM
  - **DOM Content Loaded**: Tempo até evento DOMContentLoaded
  - **Load Complete**: Tempo até evento load
  - **Memory Used/Total**: Uso de memória JavaScript
  - **Total Resources**: Número de recursos carregados
  - **Total Resource Size**: Tamanho total dos recursos
- **Possíveis Problemas**:
  - Vazamento de memória (memory_used crescendo)
  - Muitos recursos sendo carregados
  - Recursos muito grandes
  - Lentidão no carregamento da página
- **Status**: ⚠️ AVISO (Performance)

### 3.9 Redirecionamento Inesperado
- **Detecção**: Página foi redirecionada para URL diferente da esperada
- **Possíveis Causas**:
  - Autenticação necessária (redirecionamento para login)
  - Página movida
  - Configuração de rewrite incorreta
- **Status**: ⚠️ AVISO

### 3.10 Popup/Modal Bloqueando Interação
- **Possíveis Causas**:
  - Popup de notificação não fechou
  - Modal de confirmação apareceu
  - Anúncio ou banner bloqueando cliques
- **Status**: ⚠️ AVISO

---

## 📊 4. ERROS DE LOGGING E NOTIFICAÇÃO

### 4.1 Falha ao Registrar Log
- **Detecção**: Erro ao escrever no arquivo JSONL de log
- **Possíveis Causas**:
  - Permissões insuficientes no diretório
  - Disco cheio
  - Arquivo corrompido
  - Caminho inválido
- **Status**: ⚠️ AVISO

### 4.2 Falha ao Enviar Notificação Slack
- **Detecção**: Erro ao enviar mensagem para webhook do Slack
- **Possíveis Causas**:
  - Webhook inválido ou expirado
  - Conexão com Slack falhou
  - Webhook com valor de exemplo ainda configurado
  - Formato do webhook inválido
  - Timeout na requisição ao Slack
- **Retry**: Tenta novamente até 2 vezes com backoff exponencial
- **Status**: ⚠️ AVISO (notificação crítica não entregue)

### 4.3 Webhook do Slack com Formato Inválido
- **Detecção**: Webhook não segue padrão `https://hooks.slack.com/services/AAA/BBB[/CCC]`
- **Impacto**: Mensagens de falha não são enviadas para o Slack
- **Status**: ❌ CRÍTICO (para notificações)

### 4.4 Webhook do Slack com Valor de Exemplo
- **Detecção**: Webhook contém string `your/webhook/url`
- **Impacto**: Mensagens de falha não são enviadas (webhook não é real)
- **Status**: ❌ CRÍTICO (para notificações)

---

## ⚙️ 5. ERROS DE CONFIGURAÇÃO

### 5.1 Configuração Inválida
- **Possíveis Problemas**:
  - `SITE_URL` vazio ou inválido
  - `PORTAL_URL` vazio ou inválido
  - `SUCCESS_ORG_LABEL` vazio
  - `TIMEZONE` inválido
  - `CHECK_INTERVAL_HOURS` ou `CHECK_INTERVAL_MINUTES` inválidos
  - `SLACK_WEBHOOK` com formato incorreto
  - `SSL_EXPIRATION_WARNING_DAYS` negativo ou zero
  - `DAILY_REPORT_HOUR` fora do range 0-23
- **Status**: ❌ CRÍTICO (impede execução)

### 5.2 Arquivo .env Não Encontrado
- **Impacto**: Sistema usa valores padrão ou falha
- **Status**: ⚠️ AVISO

### 5.3 Variáveis de Ambiente Ausentes
- **Possíveis Variáveis Críticas**:
  - `SITE_URL`
  - `PORTAL_URL`
  - `TIMEZONE`
- **Status**: ❌ CRÍTICO

---

## 🛠️ 6. ERROS DO SISTEMA/INFRAESTRUTURA

### 6.1 Erro de Acesso ao Arquivo
- **Possíveis Causas**:
  - Permissões insuficientes
  - Caminho inválido
  - Arquivo em uso por outro processo
- **Status**: ❌ CRÍTICO

### 6.2 Erro ao Criar Diretório
- **Possíveis Causas**:
  - Permissões insuficientes
  - Espaço em disco insuficiente
  - Caminho inválido ou muito longo
- **Status**: ❌ CRÍTICO

### 6.3 Erro Geral/Inesperado
- **Detecção**: Exceção não prevista capturada
- **Ação**: Registra stack trace completo para debugging
- **Status**: ❌ CRÍTICO

### 6.4 Erro ao Iniciar Browser (Playwright)
- **Possíveis Causas**:
  - Chromium não instalado
  - Falta de dependências do sistema
  - Permissões insuficientes
- **Status**: ❌ CRÍTICO

### 6.5 Memory Leak / Alta Utilização de Memória
- **Detecção**: (via métricas Playwright)
- **Possíveis Causas**:
  - Página JavaScript com vazamento
  - Muitos recursos em memória
  - Browser não liberando memória
- **Status**: ⚠️ AVISO (Performance)

---

## 📈 7. ERROS DE PERFORMANCE (Com Alerta)

Estes não são "erros" técnicos, mas indicadores de problemas potenciais:

- **TTFB Alto** (> 5s): Latência de rede ou processamento no servidor
- **Download Lento** (< 1 Mbps): Conexão de rede limitada
- **DOM Processing Lento** (> 3s): JavaScript pesado no cliente
- **Total Load Time Alto** (> 30s): Página muito pesada ou recursos lentos
- **Muitos Recursos** (> 100): Página carregando muitos arquivos
- **Resource Size Alto** (> 50 MB): Total de dados muito grande

---

## 📋 RESUMO POR SEVERIDADE

### ❌ CRÍTICO (Impede Operação)
- Certificado expirado ou inválido
- Status HTTP não-200
- Timeout na página
- Timeout ao localizar elemento crítico
- Erro ao selecionar organização ou abrir documento
- Webhook Slack inválido ou com formato errado
- Configuração inválida

### ⚠️ AVISO (Funciona, mas com Problema)
- Certificado expirando em breve
- TLS ou Cipher Suite fraco
- Performance baixa
- Falha ao enviar notificação Slack (após retries)
- Screenshot não conseguiu ser salvo
- JavaScript error no console

---

## 🔄 FLUXO DE DETECÇÃO

```
1. Verificação SSL/TLS
   ↓
2. Verificação HTTP
   ↓
3. Verificação Playwright
   ↓
4. Se alguma falha → Registra log (JSONL)
   ↓
5. Se alguma falha → Envia notificação Slack (com retry)
   ↓
6. Gera relatório diário/mensal
```

---

## 📝 EXEMPLO DE RELATÓRIO

Quando um erro é detectado, o sistema registra:

```json
{
  "timestamp": "2025-11-12 15:30:00 BRT",
  "site_url": "https://www.japeri.rj.gov.br/",
  "portal_url": "https://pmjaperi.geosiap.net.br/portal-transparencia/...",
  "ok_ssl": true,
  "ok_http": true,
  "ok_playwright": false,
  "playwright_detail": {
    "error": "Timeout ao interagir com elemento",
    "messages": ["Timeout waiting for locator..."],
    "performance": { /* métricas */ }
  },
  "screenshot": "fail_20251112_153000_123456.png",
  "recorded_at": "2025-11-12 15:30:15 BRT"
}
```

---

## 💡 PRÓXIMAS MELHORIAS POSSÍVEIS

1. **Alertas Configuráveis** - Definir thresholds customizados por métrica
2. **Histórico de Erros** - Detectar padrões de falha
3. **Root Cause Analysis** - Análise automática da causa do erro
4. **Escalação de Alertas** - Diferentes níveis de notificação (Slack, Email, SMS)
5. **Métricas Exportáveis** - Prometheus/Grafana para visualização
6. **Health Dashboard** - Dashboard em tempo real
7. **Testes de Carga** - Simular múltiplos usuários
8. **Testes de Failover** - Verificar redundância

---

**Versão**: 1.0  
**Atualizado em**: 12 de Novembro de 2025
