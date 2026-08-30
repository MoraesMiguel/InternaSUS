# Resumo da Evolução — 30/08/2026

Resumo do que foi implementado hoje no projeto InternaSUS, para quem for dar continuidade. Todas as mudanças abaixo estão no working tree da branch `feature/revisao_processamento` (ainda não commitadas).

## Em uma frase

O pipeline saiu de "camada Gold com só CNES+SIA, sem SIH/IBGE" para um **star schema** (1 dimensão + 5 fatos, com SIH e população do IBGE integrados) e ganhou um **primeiro dashboard Streamlit** para navegar esses dados — mas o dashboard é só uma versão inicial e precisa evoluir.

## O que mudou, por área

### 1. Camada Silver (`internasus/processing/silver.py`) — reescrita
- Antes: só limpava CNES e SIA, linha a linha, sem recorte temporal (risco de estourar memória/disco com o histórico inteiro).
- Agora: aplica um **recorte temporal deliberado** por fonte:
  - **CNES** (EQ/LT/PF/SR): mantém só as últimas 12 competências (o CNES é uma "foto mensal repetida" — o mesmo registro aparece em todo mês em que esteve ativo, então usar o histórico inteiro infla os totais).
  - **SIA/SIH**: mantém só o "ano de referência" — o último ano com população estimada no IBGE **e** com os 12 meses completos de SIA — calculado dinamicamente, mais uma projeção de colunas (evita estourar disco: o SIA bruto tem ~524M linhas).
  - **IBGE/SIDRA**: mantém todos os anos (poucas linhas), com o código de município normalizado para 6 dígitos (CNES/SIA/SIH usam 6 dígitos; IBGE usava 7).
- Agora processa CNES, SIA, **SIH** e **IBGE/população** (SIH e IBGE não eram usados antes).

### 2. Camada Gold (`internasus/processing/gold.py`) — reescrita como star schema
Antes eram funções soltas, várias delas "puladas com aviso" porque dependiam de SIH/SIDRA (que ainda não existiam). Agora gera 6 tabelas em `data/gold/`:

| Tabela | Grão | O que responde |
|---|---|---|
| `dim_municipio` | município | dimensão conformada (código, nome, população) |
| `fato_filas_gargalos` | município | exames x equipamentos de imagem, ocupação de leitos cirúrgicos |
| `fato_desigualdade_regional` | município | evasão hospitalar, pressão sobre polos, infraestrutura per capita |
| `fato_profissionais` | município | médicos/enfermeiros per capita x demanda de alta complexidade |
| `fato_infra_estabelecimento` | estabelecimento (CNES) | equipamento de imagem sem especialista vinculado |
| `fato_recursos_estabelecimento` | estabelecimento (CNES) | **novo**: todos os profissionais/leitos/equipamentos/serviços de cada estabelecimento, relativizados pela população do município |

Todas as queries portam, sem mudar a lógica, o que já tinha sido validado em `notebooks/InternaSUS.ipynb` contra os dados reais.

**Fora do escopo (decisão registrada):** bloco de Atenção Primária (SISAB/SIAPS) não é gerado — essa fonte não está ingerida no projeto. Microrregião também ficou de fora (campo do CNES descontinuado/não confiável).

### Problemas nos dados que já foram resolvidos hoje
- **CNES repete o mesmo registro todo mês** em que ficou ativo (às vezes por anos) — se somasse tudo sem filtrar, os números ficavam inflados dezenas de vezes. Resolvido: agora só usamos a competência (mês) mais recente.
- **Código de município não batia entre as fontes** — CNES/SIA/SIH usam 6 dígitos, IBGE usava 7. Resolvido: tudo padronizado para 6 dígitos.
- **Campos de código com formatação diferente** (ex.: `'01'` com zero à esquerda em uma fonte, `'1'` sem zero em outra) faziam comparações silenciosamente não bater. Resolvido nas comparações usadas hoje.

### O que ainda falta / limitação conhecida (não é bug, é a fonte de dados mesmo)
- Não temos o dicionário oficial de códigos de equipamento/leito do CNES — hoje só distinguimos categorias amplas (ex. "Diagnóstico por Imagem"), não o tipo exato do aparelho.
- **SISAB (Atenção Primária/UBS) não está ingerido** — é a maior lacuna hoje, e impede responder as perguntas de negócio sobre UBS/Saúde da Família.
- População do IBGE é só anual (falta 2022 e 2023) — qualquer indicador "por habitante" usa a população de um único ano como base.
- Não existe uma malha territorial confiável (microrregião/mesorregião) ingerida — hoje só dá pra analisar por município.

### 3. Publicação para o OCI (`internasus/oci_storage.py`)
Virou uma CLI Typer com 4 comandos: `publish-raw`, `publish-silver`, `publish-gold`, `publish-all` (antes só tinha o upload da camada raw, disparado direto no `__main__`).

### 4. Dashboard Streamlit — novo (`dashboard/`)
Primeira versão navegável dos dados da Gold, local (lê `data/gold/*.parquet` diretamente, sem passar pelo OCI/Autonomous Database ainda):
- `Home.py` — visão geral (contagem de municípios, ano de referência, estabelecimentos mapeados).
- `pages/1_Filas_e_Gargalos.py`, `2_Desigualdade_Regional.py`, `3_Profissionais.py` — um gráfico de barras "top 15" + tabela filtrável por município, por tema.
- `data_access.py` — leitura cacheada dos parquets (`@st.cache_data`) + helper para juntar qualquer fato de grão-município com `dim_municipio`.
- Roda com `make dashboard` (alvo novo no `Makefile`).

**Importante para quem continuar:** essa é uma primeira versão propositalmente simples, apenas para teste!

### 5. Renomeações e organização
- `internasus/config.py`: `INTERIM_DATA_DIR`/`PROCESSED_DATA_DIR` (nomenclatura genérica do template cookiecutter) viraram `SILVER_DATA_DIR`/`GOLD_DATA_DIR`, alinhado com a nomenclatura real do pipeline (bronze/silver/gold). `internasus/features.py` foi atualizado para usar o novo nome.
- `internasus/loaders.py`: as views `sih` e `ibge_pop` (comentadas, "ajustar quando existir") foram ativadas, já que os dados existem agora.
- `docs/`: `docs/README.md` foi removido e o conteúdo relevante reorganizado em páginas próprias dentro de `docs/docs/` — `Estrutura_de_Dados_e_Problemas.md` (o que existe hoje na Gold e problemas de dados encontrados) e `Perguntas_de_Negócio.md` (as perguntas de negócio por tema, com as fontes que respondem cada uma). `docs/mkdocs.yml` ficou vazio nessa passagem — precisa reconfigurar `nav`/tema se o site do mkdocs for publicado.
- `notebooks/InternaSUS.ipynb` foi bastante expandido (é a fonte de verdade das queries que foram portadas para `gold.py`) e existe um novo notebook exploratório, `notebooks/Exploracao_Silver_Gold.ipynb`.

## Como rodar o pipeline completo hoje

```bash
make silver          # data/raw/ -> data/silver/
make gold             # data/silver/ -> data/gold/ (star schema)
make dashboard        # streamlit run dashboard/Home.py (lê data/gold/ local)
make publish-all      # opcional: sobe raw+silver+gold para o OCI
```

## Próximos passos:

O dashboard atual é reconhecidamente uma **primeira versão fraca**: mostra cada tabela fato da Gold quase diretamente, sem cruzar dimensões entre si, então gera pouco insight novo além de "top 15 por coluna". Direções combinadas para evoluir:

1. **Mais dimensões para cruzar dados.** `Hoje a única dimensão real é dim_municipio`. 
  Candidatas a explorar:
   - Dimensão de **tempo/competência** (hoje é uma foto única, `data_referencia` fixa) — precisaria manter mais histórico na Silver em vez de só as últimas 12 competências.
   - Dimensão de **tipo de estabelecimento/serviço** (natureza jurídica, tipo de unidade CNES) para segmentar `fato_recursos_estabelecimento` além de "por município".
2. **Trazer outras fontes via API** para enriquecer o cruzamento — candidato natural é o **SISAB** (Atenção Primária/UBS), que hoje é a lacuna mais citada nos documentos de negócio (todo o bloco 3 de `Perguntas_de_Negócio.md` depende dele e não está implementado).
3. **Repensar o dashboard** não como "uma página por tabela fato", mas com filtros/cruzamentos que atravessem as tabelas (ex.: cruzar `fato_profissionais` com `fato_filas_gargalos` no mesmo município, lado a lado).

Nenhuma dessas três frentes foi iniciada ainda — são o ponto de partida sugerido para a próxima pessoa.
