# SkyFlow ✈️

Pipeline de dados de tráfego aéreo brasileiro — **100% gratuito**, agendado, com
arquitetura em camadas (bronze/silver/gold), testes de qualidade e relatório em Power BI.

> Projeto de portfólio de Engenharia de Dados. Coleta posições de aeronaves sobre o
> Brasil de hora em hora (rede [OpenSky](https://opensky-network.org/)), transforma os
> dados com DuckDB e serve um relatório analítico.

---

## Arquitetura

| Camada | Ferramenta | Papel |
|---|---|---|
| Agendamento | GitHub Actions (cron) | Dispara a coleta de hora em hora, sem servidor |
| Ingestão | Python + `requests` | Autentica (OAuth2) e coleta o snapshot do Brasil |
| Armazenamento | Parquet particionado | Dados versionados no repositório |
| Transformação | DuckDB (SQL) | Bronze → Silver → Gold |
| Qualidade | Great Expectations | Valida schema, nulos e ranges por camada |
| Enriquecimento | APIs do IBGE | Dimensões de UF e região |
| Dashboard | Power BI Desktop | Relatório do tráfego (refresh manual sobre o gold) |

**Fluxo:** Actions (de hora em hora) → coletor Python → grava **bronze** em Parquet →
DuckDB transforma em **silver** e **gold** → Great Expectations valida → commit dos Parquet.

---

## Estrutura do repositório

```
skyflow/
├── src/              # código Python (coletor, utilitários)
├── sql/              # transformações DuckDB (bronze→silver→gold)
├── data/
│   ├── bronze/       # dados crus (append-only), particionados por data/hora
│   ├── silver/       # dados limpos e conformados
│   └── gold/         # marts prontos para o Power BI
├── quality/          # suites do Great Expectations
├── powerbi/          # arquivo .pbix do relatório
├── docs/             # diagramas e documentação
├── requirements.txt
└── .gitignore
```

---

## Como rodar (local)

```bash
# 1. Ambiente virtual
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 2. Dependências
pip install -r requirements.txt

# 3. Credenciais da OpenSky (NÃO versionar)
#    Baixe credentials.json da sua conta OpenSky (Account → API client)
#    e coloque na raiz do projeto, OU exporte as variáveis:
export OPENSKY_CLIENT_ID=seu_id
export OPENSKY_CLIENT_SECRET=seu_secret
```

> ⚠️ **Segurança:** `credentials.json`, `.env` e chaves estão no `.gitignore`.
> Nunca faça commit de credenciais.

---

## Decisões de arquitetura

Ver [`docs/`](docs/) para o documento de escopo completo. Destaque de um trade-off
assumido conscientemente:

- **Dados versionados no Git** é um antipadrão em produção (o histórico incha), mas
  aceitável aqui: volume pequeno, custo zero, reprodutível por quem clonar. Em produção,
  isso iria para object storage (S3/R2), com o Git guardando apenas o código.

---

## Status

🚧 Em desenvolvimento — estrutura inicial.
