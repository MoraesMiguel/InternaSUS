# InternaSUS — Inteligência e Pressão Hospitalar em São Paulo

O InternaSUS é uma solução analítica para monitoramento da pressão sobre a rede hospitalar do estado de São Paulo, desenvolvida a partir de dados públicos do DATASUS e do IBGE.

O projeto integra dados do IBGE, SIH/SUS e do CNES — profissionais, equipamentos, leitos e serviços especializados — para transformar registros brutos de saúde pública e dados geográficos em indicadores e inteligência visual, apoiando gestores de saúda pública na identificação de desigualdades regionais, gargalos de capacidade e possíveis desequilíbrios entre demanda e oferta de recursos hospitalares.

## 1. Contextualização do problema

O estado de São Paulo possui uma das maiores e mais complexas redes do SUS no Brasil. Apesar da ampla infraestrutura disponível, o sistema enfrenta dificuldades para garantir acesso rápido, eficiente e equilibrado aos serviços de saúde em todo o território.

Os desafios envolvem desde a capacidade da Atenção Primária de atender e coordenar a jornada do paciente até a disponibilidade de especialistas, exames e procedimentos. Além disso, diferenças na distribuição de profissionais e serviços entre municípios contribuem para gargalos, deslocamentos de pacientes e aumento das filas de atendimento.

## 2. O problema que resolvemos

### 2.1. Filas para especialistas, exames e cirurgias

Pacientes podem enfrentar longos períodos de espera para acessar consultas especializadas, exames diagnósticos e cirurgias eletivas. Esses gargalos podem estar relacionados à alta demanda, capacidade insuficiente de atendimento, disponibilidade de profissionais e distribuição dos serviços.

**Problema:** identificar onde estão os principais gargalos de atendimento, quais serviços são mais afetados e quais fatores estão associados à formação das filas.

### 2.2. Desigualdade regional de acesso

A disponibilidade de serviços de saúde não é uniforme entre os municípios e regiões paulistas. Enquanto alguns polos concentram hospitais, equipamentos e serviços especializados, outras localidades dependem do encaminhamento de pacientes para municípios de referência.

**Problema:** identificar regiões com menor acesso relativo aos serviços de saúde e avaliar os desequilíbrios territoriais entre demanda populacional e capacidade assistencial.

### 2.3. Problemas na Atenção Primária (UBS)

A Atenção Primária representa a principal porta de entrada do SUS e possui papel fundamental na prevenção, diagnóstico inicial, acompanhamento e encaminhamento dos pacientes. Diferenças de cobertura e capacidade das UBS e equipes de Saúde da Família podem aumentar a pressão sobre outros níveis de atenção.

**Problema:** identificar municípios ou regiões com baixa cobertura ou capacidade de Atenção Primária e analisar sua relação com utilização de serviços especializados e hospitalares.

### 2.4. Falta ou má distribuição de profissionais especializados

A disponibilidade de médicos e outros profissionais especializados varia significativamente entre municípios e regiões. A concentração desses profissionais em determinados polos pode gerar vazios assistenciais, necessidade de deslocamento e sobrecarga dos centros de referência.

**Problema:** identificar quais especialidades e regiões apresentam maior desequilíbrio entre disponibilidade de profissionais e necessidade potencial da população, permitindo localizar áreas prioritárias para melhor alocação de recursos.

## 3. Fonte dos Dados

O InternaSUS utiliza dados públicos de diferentes sistemas oficiais de saúde, combinando informações de demanda assistencial, infraestrutura, capacidade hospitalar e disponibilidade de profissionais com dados demográficos dos municípios paulistas.

Grande parte dos dados do DATASUS é acessada por meio do PySUS, biblioteca Python que facilita a obtenção e o processamento das bases do SUS.

Documentação API: https://pysus.readthedocs.io/en/latest/databases/data-sources.html

### 3.1. CNES — Cadastro Nacional de Estabelecimentos de Saúde

O CNES fornece informações sobre a estrutura e os recursos disponíveis nos estabelecimentos de saúde. Para o projeto, são utilizados principalmente:

* **CNES-PF (Profissionais)**: distribuição de profissionais e especialistas por estabelecimento e município.
* **CNES-EQ (Equipamentos)**: disponibilidade e distribuição de equipamentos de saúde.
* **CNES-LT (Leitos)**: quantidade e características dos leitos, utilizada para avaliar a capacidade hospitalar.
* **CNES-SR (Serviços Especializados)**: oferta de especialidades e serviços nos estabelecimentos de saúde.

**Papel no projeto:** representar a oferta e capacidade instalada da rede de saúde.

### 3.2. SIA/SUS — Sistema de Informações Ambulatoriais

Contém registros da produção ambulatorial do SUS, incluindo consultas, exames e outros procedimentos realizados.

**Papel no projeto:** mensurar a demanda e produção ambulatorial e identificar diferenças regionais no acesso aos serviços.

### 3.3. SIH/SUS — Sistema de Informações Hospitalares

Reúne dados relacionados às internações hospitalares financiadas pelo SUS, incluindo procedimentos, características das internações e utilização da rede hospitalar.

**Papel no projeto:** analisar a demanda hospitalar, o volume de internações e a pressão exercida sobre a capacidade disponível.

### 3.4. SISAB / SIAPS — Atenção Primária à Saúde

Fornece informações relacionadas aos atendimentos e ao desempenho da Atenção Primária à Saúde (APS).

**Papel no projeto:** incorporar indicadores da atenção primária e investigar sua relação com a demanda por serviços ambulatoriais e hospitalares.

### 3.5. IBGE — Dados Demográficos e Geográficos

Os dados do IBGE complementam as bases de saúde com informações sobre:

* população dos municípios;
* códigos e limites municipais;
* coordenadas e informações geográficas;
* malhas territoriais.

**Papel no projeto:** permitir a construção de indicadores per capita, comparações entre municípios e análises geoespaciais.

## 4. Integração das Fontes

A combinação dessas bases permite analisar o sistema de saúde sob diferentes perspectivas:

**População (IBGE)** → **Atenção Primária (SISAB/SIAPS)** → **Atendimento Ambulatorial (SIA)** → **Internações (SIH)**

O CNES representa a capacidade disponível por meio de profissionais, leitos, equipamentos e serviços especializados.

Essa integração possibilita comparar **demanda** × **capacidade** × **população**, formando a base analítica utilizada pelo InternaSUS para identificar gargalos, desigualdades regionais e pressão sobre a rede de saúde do estado de São Paulo.

## 5. Arquitetura do Projeto

A arquitetura do projeto segue os princípios da Medallion Architecture, organizando os dados nas camadas Bronze, Silver e Gold. O processamento será executado localmente utilizando Python, enquanto o Oracle Cloud Infrastructure (OCI) será responsável pelo armazenamento persistente das diferentes camadas e pela disponibilização dos dados para consumo.

A arquitetura está dividida em quatro etapas principais:

1. Ingestão
2. Processamento
3. Armazenamento
4. Consumo

### 5.1. Ingestão

A etapa de ingestão é responsável pela extração dos dados das fontes externas e pela criação da camada de dados brutos.

* Fontes de dados

    * DataSUS (API: PySUS): Dados do CNES (Estabelecimentos, Profissionais, Equipamentos, Leitos, Serviços Especializados, Equipes), SIA (Sistema de Informações Hospitalares) e SIH (Sistema de Informações Ambulatoriais)
    * PySUS (API: SIDRA): Dados demográficos e populacionais

As extrações serão realizadas em Python, considerando somente dados referentes ao Estado de São Paulo no período de 2020 a 2026.

Após a extração, os dados serão convertidos para Apache Parquet, formato colunar escolhido por oferecer compressão eficiente, menor utilização de armazenamento e melhor desempenho durante operações analíticas.

Os arquivos serão inicialmente armazenados na pasta local: **data/raw/**

Essa pasta funciona como uma área local de trabalho para os dados recém-extraídos. Após a conclusão e validação da extração, os arquivos Parquet serão enviados para a camada Bronze no OCI Object Storage.

**Principais atividades:**
* Extração dos dados do DataSUS através do PySUS;
* Extração dos dados do IBGE através da API SIDRA;
* Filtragem dos dados para o Estado de São Paulo;
* Controle do período entre 2020 e 2026;
* Conversão dos dados para Parquet;
* Validação básica dos arquivos extraídos;
* Armazenamento na pasta data/raw/;
* Upload dos arquivos para o bucket Bronze.

## 5.2. Processamento

O processamento será realizado localmente, utilizando os arquivos Parquet disponíveis nas pastas de trabalho do projeto.

Como os arquivos da camada Raw já estarão disponíveis localmente após a extração, o pipeline utilizará esses arquivos diretamente para as transformações. Dessa forma, evita-se realizar o upload para o OCI e posteriormente baixar os mesmos arquivos novamente para processamento.

O bucket Bronze permanece como a cópia persistente e oficial dos dados brutos, permitindo recuperação e reprocessamento quando necessário.

### 5.2.1. Bronze → Silver

A transformação da camada Bronze para Silver será responsável pela preparação e integração dos dados.

Entre as principais atividades estão:

* Padronização dos nomes das colunas;
* Conversão e validação de tipos de dados;
* Tratamento de valores nulos;
* Remoção de registros duplicados;
* Padronização de códigos de municípios;
* Tratamento de datas;
* Validação das regras de qualidade;
* Seleção das colunas necessárias;
* Integração entre diferentes fontes;
* Enriquecimento dos dados.

Os resultados serão armazenados localmente em: **data/silver/**

Após a conclusão do processamento, os arquivos Parquet serão enviados para o bucket Silver do OCI Object Storage.

### 5.2.2. Silver → Gold

A segunda etapa de processamento será responsável pela criação das estruturas analíticas e indicadores utilizados pelo projeto.

Nesta etapa serão realizadas atividades como:

* Agregações por município;
* Agregações por período;
* Agregações por estabelecimento;
* Agregações por especialidade;
* Cruzamento entre dados do DataSUS e IBGE;
* Cálculo de indicadores;
* Cálculo de métricas relacionadas à população;
* Construção das tabelas destinadas ao consumo analítico.

Os resultados serão armazenados localmente em: **data/gold/**

Após a geração, os arquivos serão enviados para o bucket Gold do OCI.

## 5.3. Armazenamento

O OCI Object Storage será utilizado como Data Lake e armazenamento persistente do projeto.

A separação em camadas permite preservar os dados originais e manter diferentes níveis de processamento de forma independente.

* Camada Bronze: Armazena dados brutos provenientes das APIs. Possui a finalizade de preservar os dados originais para auditoria e reprocessamento.
* Camada Silver: Dados limpos, padronizados e integrados. Possui a finalizade de disponibilizar dados confiáveis para análise e agregação.
* Camada Gold: Dados agregados e indicadores. Possui a finalizade de disponibilizar estruturas prontas para consumo analítico.

Os arquivos serão armazenados principalmente em formato Parquet.

Sempre que aplicável, os dados poderão ser particionados por atributos como:

* Fonte;
* Estado;
* Ano;
* Mês;
* Tipo de dataset.

Por exemplo, dados de produção ambulatorial poderão ser organizados considerando fonte, estado, ano e mês. Essa estratégia permite processar somente as partições necessárias, reduzindo leitura de dados e utilização de memória.

### 5.3.1. Armazenamento Local x OCI

O armazenamento local e o armazenamento no OCI possuem responsabilidades diferentes:

* Pastas locais: Workspace utilizado durante extração, transformação e agregação
* OCI Bronze: Armazenamento persistente dos dados brutos
* OCI Silver: Armazenamento persistente dos dados tratados
* OCI Gold: Armazenamento persistente dos dados agregados
* Autonomous Database: Serving Layer para disponibilização dos dados analíticos

Dessa forma, as pastas locais não representam a fonte definitiva dos dados. O OCI Object Storage será considerado o armazenamento persistente e oficial das camadas do Data Lake.

## 5.4. Serving Layer

Após a criação e armazenamento da camada Gold, os dados necessários para a aplicação serão carregados no OCI Autonomous Database.

A carga será realizada a partir dos arquivos existentes no bucket Gold do OCI, em vez de utilizar diretamente os arquivos da pasta Gold local.

Essa abordagem permite:

* Desacoplar o banco de dados da máquina utilizada para desenvolvimento;
* Garantir que a carga utilize a versão persistida da camada Gold;
* Reexecutar cargas sem repetir todo o processamento;
* Facilitar uma futura migração do processamento local para serviços de processamento em nuvem;
* Centralizar o acesso aos dados disponibilizados para consumo.
* Permitir a utilização de tecnologias como Select AI.

O Autonomous Database será responsável por armazenar as tabelas analíticas utilizadas pela SQL de maneira eficiente.

## 5.5. Consumo

O Streamlit será utilizado para desenvolver a aplicação analítica do projeto.

A aplicação realizará consultas diroetamente ao Autonomus Database, evitando que grandes volumes de arquivos Parquet precisem ser processados durante a utilização do dashboard.

A camada de consumo será responsável principalmente por:

* Consulta dos dados;
* Aplicação de filtros;
* Apresentação de KPIs;
* Construção de gráficos;
* Visualização de indicadores;
* Comparações entre municípios e períodos;
* Disponibilização dos resultados das análises.

Dessa forma, operações pesadas de limpeza, transformação e agregação permanecem nas etapas anteriores do pipeline, enquanto o Streamlit fica concentrado na consulta e apresentação das informações.

## 5.6. Tecnologias por Etapa

* Ingestão:
    Tecnologia: Python, PySUS, SIDRA API
    Finalidade: Extração dos dados

* Processamento Bronze → Silver:
    Tecnologia: Python, Polars/Pandas, PyArrow	
    Finalidade: Limpeza, padronização e integração

* Processamento Silver → Gold:
    Tecnologia: Python, Polars/Pandas	
    Finalidade: Agregações, métricas e indicadores

* Formato de armazenamento:	
    Tecnologia: Apache Parquet	
    Finalidade: Armazenamento colunar e comprimido

* Transferência para OCI:
    Tecnologia: OCI Python SDK / OCI CLI	
    Finalidade: Upload e gerenciamento dos arquivos

* Data Lake:	
    Tecnologia: OCI Object Storage	
    Finalidade: Armazenamento das camadas Bronze, Silver e Gold

* Serving Layer:	
    Tecnologia: OCI Autonomous Database	
    Finalidade: Disponibilização dos dados para consulta

* Consumo:	
    Tecnologia: Streamlit	
    Finalidade: Dashboards e aplicação analítica

## 6. Como Reproduzir o Projeto

Esta seção descreve, de forma objetiva, os passos necessários para qualquer pessoa clonar o repositório, instalar as dependências e reproduzir a ingestão dos dados localmente. O que está implementado e reproduzível hoje é a etapa de **Ingestão** (§5.1): extração das fontes públicas e gravação em Parquet em `data/raw/`. As demais etapas descritas na seção 5 (Bronze → Silver → Gold, OCI Object Storage, Autonomous Database, Streamlit) fazem parte da arquitetura alvo do projeto e ainda não possuem código de reprodução neste repositório.

### 6.1. Pré-requisitos

* Git
* Python 3.12 (fixado em `pyproject.toml`, `requires-python = "~=3.12.0"`)
* [uv](https://docs.astral.sh/uv/getting-started/installation/) — gerenciador de ambiente e dependências usado pelo projeto
* Acesso à internet, para baixar dados do FTP do DATASUS (`ftp.datasus.gov.br`) e da API SIDRA do IBGE (`apisidra.ibge.gov.br`)
* Nenhuma chave de API ou credencial é necessária para a ingestão: ambas as fontes são públicas e sem autenticação.

### 6.2. Clonar o repositório e instalar as dependências

```bash
git clone <url-do-repositorio>
cd internasus
make requirements   # equivalente a: uv sync
```

O comando cria o ambiente virtual em `.venv/` e instala exatamente as versões de dependências fixadas em `uv.lock`, garantindo que qualquer pessoa reproduza o mesmo ambiente. Depois disso, ative o ambiente (`.\.venv\Scripts\activate` no Windows, `source ./.venv/bin/activate` no Unix/macOS) ou prefixe os comandos abaixo com `uv run`.

### 6.3. Rodar os testes

```bash
make test              # suíte unitária: rápida, sem rede, com FTP/HTTP mockados
make test-integration   # testes de integração reais contra DATASUS/IBGE: mais lentos, exigem rede
```

### 6.4. Ingerir todos os dados de uma vez

```bash
make data
# equivalente a: python -m internasus.dataset ingest-all
```

Esse comando executa em sequência a ingestão de CNES, SIA, SIH (DATASUS) e SIDRA (IBGE), sempre restrita ao Estado de São Paulo (`UF=SP`) e ao intervalo 2020–2026, valores padrão definidos em `internasus/config.py`. Competências (ano/mês) ainda sem publicação são puladas com um aviso no log, não são tratadas como falha. Arquivos cujo Parquet de destino já existe também são pulados (ingestão idempotente), então o comando pode ser reexecutado com segurança para retomar uma extração incompleta.

### 6.5. Ingerir uma fonte por vez

Cada fonte pode ser baixada isoladamente, via Makefile ou diretamente pelo CLI (`internasus/dataset.py`, construído com Typer). O CLI aceita `--uf`, `--ano-inicio` e `--ano-fim` para sobrescrever os padrões.

**CNES** — Estabelecimentos de Saúde (grupos PF, EQ, LT, SR, ST):
```bash
make ingest-cnes
# ou: python -m internasus.dataset ingest-cnes --uf SP --ano-inicio 2020 --ano-fim 2026
```

**SIA** — Sistema de Informações Ambulatoriais (grupo PA):
```bash
make ingest-sia
# ou: python -m internasus.dataset ingest-sia --uf SP --ano-inicio 2020 --ano-fim 2026
```

**SIH** — Sistema de Informações Hospitalares (grupo RD, AIH Reduzida):
```bash
make ingest-sih
# ou: python -m internasus.dataset ingest-sih --uf SP --ano-inicio 2020 --ano-fim 2026
```

**SIDRA/IBGE** — população estimada por município (tabela 6579):
```bash
make ingest-sidra
# ou: python -m internasus.dataset ingest-sidra --ano-inicio 2020 --ano-fim 2026
```

CNES, SIA e SIH são baixados diretamente do FTP oficial do DATASUS (via `pysus.api.ftp`), convertidos de DBC para Parquet localmente e então gravados em disco. SIDRA é obtido por uma chamada HTTP direta à API pública do IBGE, sem depender de biblioteca específica do IBGE. Falhas em um arquivo/tabela específico não interrompem os demais: cada comando retorna um resumo (`baixados`, `pulados`, `falhas`) e o processo termina com código de saída 1 se houver alguma falha.

### 6.6. Onde os dados ficam e como estão organizados

```
data/raw/
├── fonte=CNES/uf=SP/ano=AAAA/mes=MM/dataset={PF,EQ,LT,SR,ST}/*.parquet
├── fonte=SIA/uf=SP/ano=AAAA/mes=MM/dataset=PA/*.parquet
├── fonte=SIH/uf=SP/ano=AAAA/mes=MM/dataset=RD/*.parquet
└── fonte=IBGE_SIDRA/uf=SP/ano=AAAA/dataset=6579/dados.parquet
```

O particionamento segue o padrão Hive-style (`chave=valor/`), o que permite leitura seletiva por partição em ferramentas como DuckDB, Polars ou pandas, sem precisar carregar todos os arquivos. A pasta `data/` está fora do controle de versão (`.gitignore`): cada pessoa que reproduzir o projeto gera seus próprios arquivos localmente ao rodar os comandos de ingestão acima — nenhum dado bruto é distribuído pelo repositório.

### 6.7. Cache local do pysus

A biblioteca `pysus` mantém um cache de metadados e downloads. Para garantir reprodutibilidade entre máquinas diferentes, esse cache é redirecionado para dentro do projeto (`.pysus_cache/`, também fora do controle de versão) através da variável de ambiente `PYSUS_CACHEPATH`, definida automaticamente em `internasus/config.py` antes de qualquer import do `pysus`.