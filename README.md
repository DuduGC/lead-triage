# Triagem Inteligente de Leads

API REST em Python para receber mensagens comerciais, extrair sinais semânticos com Gemini e classificar leads com regras determinísticas. O princípio central do MVP é:

> O Gemini interpreta. O Python valida e decide.

O projeto é deliberadamente pequeno: não há frontend, filas, Redis, microsserviços ou CRUD administrativo.

## Problema e escopo do MVP

Uma mensagem livre como:

```text
Olá, sou uma pessoa da Empresa Exemplo. Precisamos de 15 computadores ainda este mês e queremos um orçamento.
```

é transformada em dados estruturados e em uma classificação `QUENTE`, `MORNO` ou `FRIO`. Quando a extração não é confiável, o lead é salvo como `REVIEW_REQUIRED`; o sistema não inventa dados nem deixa o LLM escolher a classificação.

O MVP oferece:

- validação de payload, e-mail, telefone, tamanho de mensagem e corpo HTTP;
- extração estruturada pelo Gemini com schema e evidências textuais;
- regras de score versionadas em Python (`v1`);
- persistência PostgreSQL via SQLAlchemy e migração Alembic;
- autenticação simples por `X-API-Key`;
- consultas de listagem e detalhe;
- erros genéricos, `request_id` e logs sem segredos;
- testes com fakes, sem chamadas reais ao Gemini.

## Arquitetura e fluxo

```mermaid
flowchart LR
    C[Cliente] --> A[FastAPI]
    A --> V[Validação Pydantic + limite de corpo]
    V --> G[Gemini: extração estruturada]
    G --> O[Validação Python + evidências]
    O --> R[Regras determinísticas v1]
    R --> D[(PostgreSQL)]
    D --> A
    O -. falha .-> RV[REVIEW_REQUIRED]
    RV --> D
```

O conteúdo do lead é enviado ao modelo dentro de um objeto JSON e é explicitamente tratado como dado não confiável. O prompt do sistema proíbe score, classificação, SQL, comandos e ações; o Python valida o retorno antes da persistência.

## Stack e estrutura

- Python 3.12+;
- FastAPI, Pydantic e `pydantic-settings`;
- SQLAlchemy 2 + `psycopg`;
- PostgreSQL;
- Alembic;
- SDK `google-genai`;
- pytest, httpx e Ruff.

```text
app/
  api/              autenticação, erros e limite de corpo
  integrations/     adaptador Gemini e validação de evidências
  persistence/      modelo SQLAlchemy, engine e repositório
  schemas/          contratos HTTP e enums
  services/         classificação e orquestração do lead
  config.py         configuração via ambiente/.env
  logging_config.py logs JSON com allowlist
  main.py           criação da aplicação e rotas
alembic/             migração PostgreSQL
tests/               testes unitários, integração em SQLite e segurança
```

## Regras de negócio

O score máximo é 100. Os pontos são calculados apenas quando os sinais foram extraídos e validados:

| Sinal | Condição | Pontos |
| --- | --- | ---: |
| Intenção | `solicitar_orcamento` ou `comprar` | 35 |
| Intenção | `pesquisar` | 10 |
| Quantidade | 1 / 2–9 / 10+ | 5 / 15 / 25 |
| Urgência | `baixa` / `media` / `alta` | 5 / 15 / 25 |
| Empresa | presente | 5 |
| Contato | e-mail ou telefone válido no request | 10 |

- `score >= 70`: `QUENTE`;
- `40 <= score < 70`: `MORNO`;
- `score < 40`: `FRIO`.

`versao_regras` é persistida para tornar mudanças futuras auditáveis. O Gemini nunca retorna nem controla score ou classificação.

## Modelo PostgreSQL

A tabela `leads` guarda somente os dados necessários ao fluxo: UUID, campos extraídos, mensagem original, score/classificação, status de processamento, motivo de revisão, versão das regras e timestamps.

Constraints importantes:

- mensagem entre 1 e 5.000 caracteres;
- quantidade entre 1 e 1.000.000 quando presente;
- enums restritos para intenção, urgência, classificação e status;
- score entre 0 e 100;
- `PROCESSED` exige score/classificação e não aceita `review_reason`;
- `REVIEW_REQUIRED` exige `review_reason` e não aceita score/classificação.

As consultas do repositório usam SQLAlchemy com parâmetros. Não há concatenação de entrada em SQL.

## API REST

Todas as rotas de negócio exigem o header `X-API-Key`. O valor é comparado com `secrets.compare_digest` e nunca aparece em logs.

| Método | Rota | Uso |
| --- | --- | --- |
| `POST` | `/leads` | valida, extrai, classifica e persiste um lead |
| `GET` | `/leads?limit=20&offset=0&classificacao=QUENTE&status=PROCESSED` | lista leads; filtros são opcionais |
| `GET` | `/leads/{id}` | retorna um lead por UUID |

Exemplo de request:

```json
{
  "mensagem": "Precisamos de 15 computadores ainda este mês e queremos um orçamento.",
  "email": "contato@example.test",
  "telefone": "+55 (11) 99999-0000"
}
```

Exemplo resumido de resposta processada (dados fictícios):

```json
{
  "id": "00000000-0000-0000-0000-000000000001",
  "status_processamento": "PROCESSED",
  "nome": "Pessoa Exemplo",
  "empresa": "Empresa Exemplo",
  "produto_interesse": "computadores",
  "quantidade": 15,
  "intencao": "solicitar_orcamento",
  "urgencia": "alta",
  "score": 100,
  "classificacao": "QUENTE",
  "motivos": ["intent_high", "quantity_10_plus", "urgency_high", "contact_present"],
  "review_reason": null
}
```

Uma resposta processada inclui `score`, `classificacao`, `motivos`, os campos extraídos e `status_processamento: "PROCESSED"`; a `versao_regras` fica persistida para auditoria. Uma resposta em revisão mantém `score` e `classificacao` nulos e informa somente um motivo seguro, como `gemini_timeout` ou `invalid_llm_output`.

Erros seguem o formato:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request",
    "request_id": "..."
  }
}
```

Códigos principais: `201` (criado), `200` (consulta), `401` (chave ausente/incorreta), `404` (UUID inexistente), `413` (corpo acima do limite), `422` (payload inválido), `503` (banco indisponível) e `500` (erro interno genérico).

## Configuração local

Execute os comandos abaixo no PowerShell, na raiz do projeto.

1. Criar o ambiente e instalar dependências:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
   ```

   Isso cria o ambiente isolado e instala runtime, testes e lint. O resultado esperado é `Successfully installed lead-triage`.
   Como alternativa, instale tudo pelo arquivo `requirements\requirements.txt`:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements\requirements.txt
   ```

2. Criar o arquivo local de configuração:

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

   Preencha `DATABASE_URL`, `GEMINI_API_KEY` e `APP_API_KEY` **pessoalmente** no `.env`. Não envie esses valores pelo chat, não os coloque no código e não faça commit do `.env`.

3. Variáveis disponíveis:

   | Variável | Tipo | Padrão |
   | --- | --- | --- |
   | `DATABASE_URL` | segredo | obrigatório |
   | `GEMINI_API_KEY` | segredo | obrigatório |
   | `APP_API_KEY` | segredo, mínimo 16 caracteres | obrigatório |
   | `GEMINI_MODEL` | configuração | `gemini-3.6-flash` |
   | `GEMINI_TIMEOUT_SECONDS` | configuração | `8` |
   | `GEMINI_MAX_ATTEMPTS` | configuração | `2` |
   | `MAX_MESSAGE_CHARS` | configuração | `5000` |
   | `MAX_BODY_BYTES` | configuração | `16384` |
   | `LOG_LEVEL` | configuração | `INFO` |

Para gerar uma chave da aplicação localmente sem enviá-la a ninguém:

```powershell
\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(24))"
```

## PostgreSQL e menor privilégio

Crie os papéis abaixo conectado ao PostgreSQL como administrador, substituindo os marcadores localmente. Os marcadores não são credenciais reais.

```sql
CREATE ROLE lead_triage_migrator LOGIN PASSWORD '<SENHA_FORTE_DO_MIGRADOR>';
CREATE ROLE lead_triage_app LOGIN PASSWORD '<SENHA_FORTE_DA_APLICACAO>';
CREATE DATABASE lead_triage OWNER lead_triage_migrator;

\connect lead_triage
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO lead_triage_app;
```

O papel `lead_triage_migrator` é usado somente para `alembic upgrade head` e pode criar/alterar tabelas. Depois da migração, conceda ao runtime apenas as operações do MVP:

```sql
GRANT SELECT, INSERT ON TABLE leads TO lead_triage_app;
ALTER DEFAULT PRIVILEGES FOR ROLE lead_triage_migrator IN SCHEMA public
  GRANT SELECT, INSERT ON TABLES TO lead_triage_app;
```

O papel da aplicação não recebe `CREATE`, `DROP`, `ALTER` ou `DELETE`. Como o Alembic lê `DATABASE_URL`, use temporariamente a URL do migrador para aplicar a migração e depois restaure no `.env` a URL do papel `lead_triage_app`. Em um ambiente real, mantenha as credenciais de migração fora do runtime.

Aplicar a migração, na raiz do projeto:

```powershell
\.venv\Scripts\alembic.exe upgrade head
```

Resultado esperado: a revisão `0001_create_leads` é aplicada sem erro. Se aparecer erro de autenticação/conexão, confira a URL local e se o PostgreSQL está acessível; não cole a URL no chat.

## Executar a API

Com o `.env` preenchido e a migração aplicada:

```powershell
\.venv\Scripts\uvicorn.exe app.main:app --reload
```

Resultado esperado: servidor em `http://127.0.0.1:8000`. A documentação interativa do FastAPI fica em `/docs`.

Exemplo PowerShell (substitua a chave apenas no seu terminal):

```powershell
$headers = @{ "X-API-Key" = "<SUA_CHAVE_LOCAL>" }
$body = @{
  mensagem = "Precisamos de 15 computadores ainda este mês e queremos um orçamento."
  email = "contato@example.test"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/leads `
  -Headers $headers -ContentType "application/json" -Body $body
```

Para listar, use `Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/leads -Headers $headers`. `401` indica header ausente/incorreto; `413` indica corpo acima do limite; `503` indica banco indisponível ou falha não recuperável na persistência.

## Testes e qualidade

Na raiz do projeto:

```powershell
\.venv\Scripts\python.exe -m pytest -q
\.venv\Scripts\ruff.exe check app tests alembic
\.venv\Scripts\ruff.exe format --check app tests alembic
```

Os testes usam SQLite em memória e fakes do Gemini; não precisam de PostgreSQL, `GEMINI_API_KEY` válida ou chamadas externas. O resultado validado nesta etapa foi `73 passed`, Ruff sem erros e 31 arquivos formatados.

A suíte cobre:

- classes `QUENTE`, `MORNO`, `FRIO` e limites de score;
- schema, e-mail, telefone e corpo excessivo;
- sucesso, revisão, `401`, `404`, `413`, `422` e `503` da API;
- persistência, constraints e listagem;
- timeout, rate limit, indisponibilidade, autenticação e output inválido do Gemini;
- SQL injection, prompt injection e ausência de PII/secrets nos logs.

## Segurança, privacidade e limitações

- Entrada do usuário é não confiável; limites e schemas são aplicados antes do processamento.
- Prompt injection é mitigado por separação de instruções/dados, schema fechado, evidências e isolamento das regras Python. Filtros de palavras não são a defesa principal.
- O Gemini recebe somente a mensagem necessária para extração; nunca recebe chaves, URLs de banco, headers ou configurações internas.
- Logs usam uma allowlist de campos operacionais e não registram mensagem completa, e-mail, telefone, tokens ou connection strings.
- Erros externos são mapeados para mensagens genéricas sem stack trace, SQL ou paths.
- O MVP não tem autenticação de usuários, painel de revisão, atualização/remoção de leads, rate limiting distribuído ou fila assíncrona. A chamada ao Gemini é síncrona e deve ser revisitada se o volume crescer.
- A classificação é uma heurística v1; alterá-la exige revisar testes e incrementar `versao_regras`.

## Observações

O projeto inclui CI em `.github/workflows/ci.yml`. A rotina instala `requirements/requirements.txt` e executa testes, Ruff e verificação de formatação sem precisar de PostgreSQL, Gemini ou secrets.


## Auditoria antes de publicar

Na raiz do projeto, revise a saída abaixo antes de qualquer commit:

```powershell
rg -n --hidden -g '!*.pyc' -g '!.env*' -g '!.venv/**' -g '!.pytest_cache*' -g '!.ruff_cache/**' -g '!work/**' -g '!*.egg-info/**' -g '!README.md' 'AIza|BEGIN PRIVATE KEY|postgresql://|GEMINI_API_KEY=|DATABASE_URL=|APP_API_KEY=' .
```

É esperado encontrar apenas nomes de variáveis, placeholders como `<INSIRA_PESSOALMENTE>` e exemplos explicitamente fictícios. Se aparecer uma chave, senha, URL completa ou dado pessoal real, remova-o e gere uma nova credencial antes de publicar. O `.gitignore` exclui `.env`, ambientes virtuais, caches, builds e artefatos locais, mantendo apenas `.env.example`.
