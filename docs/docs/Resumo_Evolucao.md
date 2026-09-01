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

## Atualização — 31/08/2026: auditoria de grão fato↔dimensão + dashboard com filtros de dimensão

### Auditoria de granularidade

Rodei uma checagem sistemática (duplicatas na chave declarada + órfãos fato→dimensão, direto nos parquets, não só lendo o SQL) em todas as 4 dimensões e 7 fatos da Gold:

- **Grão**: 0 duplicatas na chave declarada nas 11 tabelas — o grão declarado no docstring de cada tabela bate com a realidade.
- **Órfãos fato→dimensão**: só um problema real — `fato_internacoes_diagnostico.cod_mun` tinha 3,87% das linhas (15.907, cobrindo pacientes residentes em outras ~20 UFs) sem correspondência em `dim_municipio`, porque essa fato foi construída direto do `SIH` agrupado, sem passar por `dim_municipio` como as outras fatos de grão município (que ficam implicitamente restritas a SP por construção, já que nascem de um `LEFT JOIN` a partir de `dim_municipio`). **Corrigido**: `gold_fato_internacoes_diagnostico` agora faz `INNER JOIN dim_municipio`, ficando no mesmo escopo (SP) das demais — 410.885 → 394.978 linhas. Os 106 registros (0,03%) com `diagnostico_principal` sem tradução continuam como já documentado (CID pós-COVID, não é um problema novo).
- Validei que o atributo degenerado `cod_mun` bate 100% entre `dim_estabelecimento` e as 3 fatos de grão CNES (`fato_infra_estabelecimento`, `fato_recursos_estabelecimento`, `fato_leitos_estabelecimento`) — sem divergência.
- Achado não-bug: `fato_filas_gargalos.leitos_cirurgicos` recalcula com lógica própria exatamente o que `fato_leitos_estabelecimento` (filtrado `tp_leito='1'`) já responde — validei 100% igual em 645 municípios (0 diferenças). Registro como oportunidade de simplificação futura (referenciar em vez de recalcular do zero); não mexi agora pra não arriscar regressão numa fato já validada.

### Dashboard: página nova + filtros por atributos de dimensão

- **`dashboard/pages/4_Estabelecimentos_Leitos_Diagnosticos.py`** (nova) — 3 seções (Estabelecimentos, Leitos, Diagnósticos), cada uma com filtros pelos atributos da respectiva dimensão (`tipo_unidade_desc`/`esfera_administrativa_desc`/`tipo_gestao_desc` de `dim_estabelecimento`, `tipo_leito_desc` de `dim_leito`, `descricao_capitulo` de `dim_diagnostico`), além do filtro de município já padrão nas outras páginas.
- **`dashboard/pages/3_Profissionais.py`** — as duas seções de grão estabelecimento ("infra ociosa" e "recursos por estabelecimento") ganharam os mesmos filtros de `dim_estabelecimento`.
- **`dashboard/data_access.py`** — helpers genéricos `opcoes()`/`filtrar()` pros widgets de filtro (evita repetir boilerplate nas páginas); corrigido também um bug em `com_estabelecimento()` que ainda não tinha se manifestado (a função nunca tinha sido usada até agora): como as 3 fatos de grão CNES já carregam `cod_mun` como atributo degenerado e `dim_estabelecimento` também tem `cod_mun`, o merge por `cnes` gerava `cod_mun_x`/`cod_mun_y` duplicados — corrigido pra descartar o `cod_mun` da dimensão antes do merge (validado: os dois sempre concordavam mesmo, então não muda nenhum resultado).
- **Validação**: sem navegador/`chromium-cli` disponível no ambiente, usei `streamlit.testing.v1.AppTest` (runner oficial headless do próprio Streamlit) pra rodar as 5 páginas e simular seleção real nos filtros novos — todas rodam sem exception, e os filtros efetivamente re-filtram os dados (`st.metric` muda de valor ao selecionar uma opção).

## Atualização — 31/08/2026 (2): dashboard reformulado em 7 páginas

Depois de uma proposta de conteúdo (roteiro com página/gráfico/objetivo pra cada visual,
publicada como artifact durante a conversa), implementei as sugestões cujos dados já
estavam prontos na Gold — só ficaram de fora as duas que dependiam de dado novo
(`fato_fluxo_pacientes` e a flag ICSAP em `dim_diagnostico`, ambas ainda não
implementadas).

### O que mudou
- **`Home.py`** virou "Painel de Situação": régua de 5 KPIs do estado inteiro,
  ranking dos 10 municípios mais críticos (3 indicadores lado a lado em percentil,
  não um score único opaco), e 6 cards de manchete com `st.page_link` direto pra
  cada página temática.
- **`1_Filas_e_Gargalos.py`** — dispersão oferta×demanda colorida pela
  `situacao_exames` que a Gold já calcula, leitos por tipo nos municípios mais
  carentes, e razão produção/serviço cadastrado.
- **`2_Desigualdade_Regional.py`** — bolha população×infraestrutura×evasão, e
  perfil de pressão externa dos polos regionais.
- **`3_Profissionais.py`** — quadrante médicos×demanda (`Déficit crítico` /
  `Intermediário` / `Confortável`) e RH por esfera administrativa, adicionados
  antes do conteúdo que já existia.
- **Página combinada antiga dividida em 3**, uma por tema (como no roteiro):
  `4_Estabelecimentos.py` (composição por natureza jurídica em barras 100%,
  dispersão leitos×profissionais, ranking de mais desguarnecidos),
  `5_Capacidade_Hospitalar.py` (leito complementar/UTI por mil hab. em destaque
  próprio, % SUS vs não-SUS, mix de especialidade nos 10 maiores municípios) e
  `6_Causas_de_Internacao.py` (capítulos CID por volume com % de concentração
  nos 5 maiores, capítulo × permanência média).

### Bugs pegos na validação (não eram do roteiro, apareceram testando)
Rodei `streamlit.testing.v1.AppTest` (sem `chromium-cli` disponível) em todas as
7 páginas, interagindo com cada filtro — 3 problemas reais apareceram e foram
corrigidos antes de fechar:
1. `4_Estabelecimentos.py` esqueceu de juntar `com_municipio` antes de usar
   `nome_mun` — `KeyError` imediato. Corrigido.
2. O gráfico "leitos por tipo nos 15 piores municípios" usava os 15 municípios
   com **menor** `leitos_por_mil_hab` — mas os 15 piores têm **zero** leitos, então
   não aparecem em `fato_leitos_estabelecimento` nenhuma vez e o gráfico saía
   vazio. Corrigido: agora pega os 15 piores **entre quem tem pelo menos 1 leito**
   (quem tem zero já está coberto pelo indicador simples).
3. O ranking "produção por serviço cadastrado" pedia top 15, mas só 4 municípios
   do estado inteiro têm essa razão > 0 — o resto do "top 15" saía preenchido
   com zeros empatados sem sentido. Corrigido pra mostrar só quem tem razão > 0.

### Achado de dado (não é bug do dashboard, é da base SIA)
Investigando o item 3 acima, achei a causa raiz: **`PA_UFMUN`** (o campo do SIA
usado por `gold.py` pra calcular `producao_ambulatorial`/`producao_por_mil_hab`
em `fato_filas_gargalos`) **só tem 4 valores distintos em toda a tabela silver**
(54,3 milhões de linhas, todas atribuídas a 4 dos 645 municípios de SP).
Comparei com `PA_MUNPCN` (usado por `exames_por_mil_hab`, outro campo da mesma
fato), que tem 3.773 valores distintos — normal. Não é um bug de join/formatação
(testei: os 4 valores de `PA_UFMUN` batem 100% com `dim_municipio`) — é uma
lacuna de cobertura do campo `PA_UFMUN` na extração bruta do SIA em si, herdada
de antes desta sessão. Efeito prático: `producao_ambulatorial` e
`producao_por_mil_hab` em `fato_filas_gargalos` só são confiáveis pra esses 4
municípios; os demais aparecerem como zero não significa "sem produção", é a
lacuna do campo. Documentei isso na legenda do gráfico afetado em vez de deixar
a leitura errada ("641 municípios sem produção") passar batido. Vale investigar
a extração do SIA bruto (`data/raw/fonte=SIA`) antes de confiar nesses dois
campos em qualquer análise futura — não investiguei a fundo pra não sair do
escopo do dashboard.

### Validação
`python -m py_compile` nos 7 arquivos + `AppTest` completo (carregamento e
interação com todo `st.multiselect` de cada página) — 0 exceptions, 0 falhas.
Sem navegador/`chromium-cli` no ambiente pra um screenshot visual; recomendo
rodar `make dashboard` e olhar antes de considerar definitivo.

## Atualização — 01/09/2026: ajustes de feedback no dashboard

Rodada de correções pontuais pedidas depois de olhar o dashboard reformulado:

- **Home** — "Top 10 municípios em situação mais crítica" mostrava o mesmo número pra
  todo mundo no indicador de leitos. Causa: o gráfico usava percentil (`rank(pct=True)`)
  pra exibir, e a maioria dos 10 piores tem **zero leitos** — `pandas.rank` dá o mesmo
  percentil médio pra todo empate, então o grupo inteiro empatava. Não era bug de
  cálculo, era escolha ruim de exibição: percentil escondia que "zero" é zero. Trocado
  pra mostrar o valor bruto por mil hab. (o percentil continua usado só internamente,
  pra escolher os 10 piores).
- **Filas e Gargalos** — a dispersão oferta×demanda virou barras (top 15 municípios por
  `exames_por_mil_hab`, cor por `situacao_exames`), como pedido. Os 3 gráficos da página
  ganharam `sort="-coluna"` explícito — checado que o `st.bar_chart` do Streamlit, sem
  isso, deixa a ordenação a cargo do Vega-Lite (que preserva a ordem dos dados quando
  `sort=True`, mas o comportamento não é óbvio de garantir só com `.sort_values()` no
  pandas; melhor deixar explícito no gráfico).
- **Desigualdade Regional** — a bolha população×infra×evasão virou um quadrante
  evasão×pressão externa (`Exportador líquido` / `Polo regional` / `Exportador e polo ao
  mesmo tempo` / `Autossuficiente`) — cruza as duas métricas de fluxo direto, sem
  precisar decodificar tamanho de bolha. Removidos os rankings de "top exportadores" e
  "menor infra per capita" (o quadrante novo já cobre o insight de evasão; o de infra
  per capita seguia duplicado com a Home).
- **Profissionais** — filtro de município adicionado ao quadrante déficit×demanda (a
  mediana que define os quadrantes continua fixa no estado inteiro, não recalcula com o
  filtro — senão filtrar pra 2 municípios sempre botaria um em cada lado). Removido o
  gráfico "Profissionais por esfera administrativa".
- **Estabelecimentos** — "Composição por natureza jurídica dentro de esfera" (barras
  100%) virou uma contagem simples por natureza jurídica. A dispersão leitos×profissionais
  virou 2 barras lado a lado (profissionais por `tipo_unidade_desc`, leitos por
  `tipo_unidade_desc`). Removido "Estabelecimentos mais desguarnecidos pelo tamanho do
  município".

Validação: `AppTest` nas 7 páginas + interação em todo `st.multiselect` — 0 exceptions,
0 warnings (um `SettingWithCopyWarning` apareceu no quadrante de Profissionais por causa
do `filtrar()` devolver a referência original quando nenhum filtro é aplicado; corrigido
com `.copy()` explícito antes de atribuir a nova coluna).

## Próximos passos:

Até 31/08/2026 o dashboard era uma **primeira versão fraca**: mostrava cada tabela fato da Gold quase diretamente, sem cruzar dimensões entre si, então gerava pouco insight novo além de "top 15 por coluna" — isso mudou na 2ª atualização de 31/08 (7 páginas reformuladas, ver seção acima), mas as direções abaixo continuam valendo pro que falta:

1. **Mais dimensões para cruzar dados.** `Hoje a única dimensão real é dim_municipio`.
   - ✅ **`dim_estabelecimento`** (1 linha por CNES: `tipo_unidade`, `esfera_administrativa`, `tipo_gestao`, `natureza_juridica`, `pessoa_fisica_juridica`, `cod_regiao_saude`, `cod_distrito_sanitario`, `clientela`, `turno_atendimento`) — implementada em `gold.py`, junta com `fato_recursos_estabelecimento`/`fato_infra_estabelecimento` via `cnes` (helper `com_estabelecimento` em `dashboard/data_access.py`). Atributos vêm agregados das 4 fontes CNES (qualquer valor não-vazio entre EQ/LT/PF/SR, não uma fonte fixa) porque nenhuma fonte isolada preenche todo campo — `cod_regiao_saude` mesmo assim fica nulo em 56% dos estabelecimentos e `cod_distrito_sanitario` em 97% (esse último só é preenchido de fato pra município com distrito sanitário próprio, ex. capital) — é uma limitação real da base, não um bug da agregação. `MICR_REG`, `DISTRADM`, `NATUREZA`, `NIV_HIER` e `TERCEIRO` ficaram de fora (o primeiro por já ter sido descartado antes por não confiável; os demais porque vieram 100% em branco nesta extração).
     - ✅ **Decodificação dos códigos** — cada campo de domínio (`tipo_gestao`, `esfera_administrativa`, `nivel_dependencia`, `clientela`, `tipo_unidade`, `turno_atendimento`, `natureza_juridica`) ganhou uma coluna `*_desc` com a descrição por extenso, sem substituir o código bruto. Tabelas em `internasus/domain/cnes_dominios.py`, fonte: dicionários do pacote R `microdatasus` (rfsaldanha) cruzados e corrigidos contra a Tabela de Natureza Jurídica oficial (Receita Federal/IBGE) — durante a validação um código (`3306`→`3301` para "Organização Social (OS)") foi corrigido porque o valor do microdatasus não batia com o que aparece de fato nos nossos dados. Dois achados de dado documentados no módulo: (1) `ESFERA_A` na competência atual do nosso CNES vem **idêntica** a `TPGESTAO` ('M'/'E'), não no esquema clássico 1-4 (Federal/Estadual/Municipal/Privada) — por isso é decodificada com o mesmo dicionário de `TPGESTAO`; (2) `NAT_JUR = '4000'` (~29% dos estabelecimentos) e `TP_UNID = '16'` não existem em nenhuma tabela de domínio encontrada — ficam sem tradução (`None`) em vez de um significado inventado.
   - ✅ **`dim_leito`** (1 linha por `tp_leito`×`codleito` — tipo e especialidade do leito, ex. Cirúrgico/Cardiologia, Complementar/UTI Neonatal) + **`fato_leitos_estabelecimento`** (grão CNES×tipo de leito×especialidade, 8.327 linhas) — implementadas em `gold.py`, junta via `com_leito` em `dashboard/data_access.py`. Domínios em `internasus/domain/cnes_dominios.py` (`TIPO_LEITO`, `CODIGO_LEITO`), fonte: CnesWeb oficial (cnes2.datasus.gov.br) + wiki CONASS — 58 dos 63 códigos de `CODLEITO` reais dos nossos dados foram confirmados; 5 (`65`,`70`,`72`,`83`,`94`, ~0,6% das linhas) não foram encontrados em nenhuma fonte e ficam sem tradução. Achado importante: **nenhum `TP_LEITO` representa "emergencial"/"urgência"** — isso é caráter da internação (`SIH.CAR_INT`, eletivo/urgência), não tipo de leito, então a pergunta de negócio §1.3 ("leitos... para cirurgias eletivas e emergenciais") só fica totalmente respondida cruzando esta dimensão com `SIH.CAR_INT` também — ainda não feito, é o próximo passo natural para fechar essa pergunta.
   - ✅ **`dim_diagnostico`** (1 linha por código CID-10 — categoria/subcategoria, com hierarquia categoria→grupo→capítulo, 14.233 linhas) + **`fato_internacoes_diagnostico`** (grão município×diagnóstico principal do SIH, 410.885 linhas) — implementadas em `gold.py`, junta via `com_diagnostico` em `dashboard/data_access.py`. Fonte: as 4 tabelas oficiais CID-10 do DATASUS (capítulos/grupos/categorias/subcategorias), baixadas via `internasus/ingestion/cid10.py` (comando `make ingest-cid10` / `python -m internasus.dataset ingest-cid10`, já incluído em `ingest-all`) e convertidas para UTF-8 em `data/external/cid10/` — referência estática, não vem de `data/raw` (ver nota abaixo sobre por que precisou de um script próprio). Cobertura validada: 99,97% dos `DIAG_PRINC` reais do SIH têm tradução (join em duas etapas — primeiro por subcategoria de 4 caracteres, depois por categoria de 3 pros registros sem o dígito de subcategoria); os poucos códigos sem match (`U09`,`U10`,`U109`,`N182`-`N185`,`C824`,`C826`) são revisões da CID-10 mais novas que a tabela baixada (ex. condições pós-COVID-19) e ficam sem tradução. Um bug real foi pego e corrigido na validação: a tabela oficial `GRUPOS.CSV` tem faixas de código aninhadas (um grupo amplo com sub-grupos dentro cobrindo os mesmos códigos), então o primeiro `JOIN...BETWEEN` gerava fan-out (uma categoria virava 2-3 linhas); corrigido pra ficar só com a faixa mais estreita por categoria. Resultado validado contra epidemiologia real: parto espontâneo cefálico é a causa #1 de internação em SP (como esperado no SUS), e por capítulo CID os 5 maiores são Gravidez/parto/puerpério, Doenças do aparelho digestivo, do aparelho circulatório, causas externas (lesões) e do aparelho respiratório — todos consistentes com o perfil real de internações do Brasil.
     - **Nota sobre a fonte do download:** `/data/` inteiro está no `.gitignore`, então `data/external/cid10/` não é versionado — precisa ser baixado por quem for rodar o pipeline, daí o script. A fonte oficial (`www2.datasus.gov.br/cid10/V2008/downloads/CID10CSV.zip`) é lenta/instável (~15s por request em HTTP, HTTPS fora do ar nos testes) — o script usa um espelho no GitHub (`SidneyBissoli/cid10-br-mcp`) com o mesmo conteúdo oficial (conteúdo validado linha a linha contra os `DIAG_PRINC` reais antes de confiar nele).
   - Dimensão de **tempo/competência** (hoje é uma foto única, `data_referencia` fixa) — precisaria manter mais histórico na Silver em vez de só as últimas 12 competências. Ainda não iniciada.
   - Dimensão de **especialidade/CBO** (`CNES-PF.CBO`, `SIA-PA.PA_CBOCOD`) — resolveria as perguntas de negócio sobre defasagem/distribuição por especialidade; exigiria uma fato nova em grão município×especialidade para não inflar as fatos existentes, e não há dicionário oficial de CBO ingerido ainda. Ainda não iniciada.
   - Dimensão de **equipamento** (`CNES-EQ.TIPEQUIP`/`CODEQUIP`) e de **procedimento** (grupo SIGTAP, 2 primeiros dígitos de `PA_PROC_ID`/`PROC_REA`) — candidatas levantadas mas não iniciadas (ver conversa que gerou este resumo).
   - Dimensão de **demografia** (sexo/faixa etária/raça-cor, `SIH.SEXO`/`IDADE`/`RACA_COR`) — candidata levantada mas não iniciada.
2. **Trazer outras fontes via API** para enriquecer o cruzamento — candidato natural é o **SISAB** (Atenção Primária/UBS), que hoje é a lacuna mais citada nos documentos de negócio (todo o bloco 3 de `Perguntas_de_Negócio.md` depende dele e não está implementado).
3. **Repensar o dashboard** não como "uma página por tabela fato", mas com filtros/cruzamentos que atravessem as tabelas (ex.: cruzar `fato_profissionais` com `fato_filas_gargalos` no mesmo município, lado a lado).
   - ✅ **Feito na 2ª atualização de 31/08/2026** (ver seção acima): 7 páginas, cada uma cruzando pelo menos 2 indicadores no mesmo visual (dispersões/quadrantes em vez de rankings soltos) e com filtro por atributo de dimensão, não só por município. Restam em aberto: a página "Fluxo de Pacientes" (falta `fato_fluxo_pacientes`) e o índice de causas evitáveis (falta a flag ICSAP em `dim_diagnostico`) — as duas únicas sugestões do roteiro que dependiam de dado novo.

A frente 2 (SISAB) continua sem nenhum começo. A frente 1 (mais dimensões) tem `dim_estabelecimento`, `dim_leito` e `dim_diagnostico` prontas — `especialidade/CBO`, `equipamento`, `procedimento`, `demografia`, `tempo/competência`, `fato_fluxo_pacientes` e a flag ICSAP seguem como candidatas não iniciadas (ver lista acima e o roteiro publicado durante a conversa).
