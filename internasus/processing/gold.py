"""
internasus.processing.gold
Camada Gold: lê os parquets da camada silver (data/silver/) e monta um star
schema (1 dimensão conformada + tabelas fato) para consumo no Power BI,
gravando cada tabela em data/gold/<nome>.parquet.

Schema:
  dim_municipio                  -- 1 linha por município de SP (cod_mun, nome, população)
  dim_estabelecimento            -- 1 linha por CNES (cadastro: natureza, esfera, tipo de unidade etc.)
  dim_leito                      -- 1 linha por (tp_leito, codleito) — tipo e especialidade do leito
  dim_diagnostico                -- 1 linha por código CID-10 (categoria/grupo/capítulo), de data/external/cid10/
  fato_filas_gargalos            -- grão município (README §2.1)
  fato_desigualdade_regional     -- grão município (README §2.2)
  fato_profissionais             -- grão município (README §2.4)
  fato_infra_estabelecimento     -- grão estabelecimento/CNES: equip. de imagem x médico (README §2.1/§2.4)
  fato_recursos_estabelecimento  -- grão estabelecimento/CNES: profissionais + leitos + equipamentos +
                                     serviços especializados, todos, e per capita em cima da população
                                     do município onde o estabelecimento fica
  fato_leitos_estabelecimento    -- grão estabelecimento/CNES x tipo de leito x especialidade do leito
  fato_internacoes_diagnostico   -- grão município x diagnóstico principal (CID-10)
  fato_atencao_primaria          -- grão município: cobertura de Atenção Primária (SISAB) x
                                     internações por condições sensíveis à AP - ICSAP (SIH) (README §3)

Todas as tabelas fato têm uma coluna `data_referencia` (DATE) — o grão
temporal deste MVP é um único ponto no tempo por tabela (última competência
disponível do CNES / ano de referência do SIA-SIH, já escopados pela camada
silver), então `data_referencia` é um rótulo único (31/dez do ano de
referência) para relacionar com a tabela Calendário que o usuário importa no
Power BI — não é uma data de evento linha a linha.

As queries abaixo portam, sem mudança de lógica, as células já validadas em
notebooks/InternaSUS.ipynb (execução completa sem erros contra os dados
reais) — os comentários "ver notebook, célula X" apontam a célula de origem.

O bloco de Atenção Primária (perguntas de negócio §3) é gerado por
fato_atencao_primaria a partir do SISAB (ingerido via API pública do
e-Gestor AB — ver internasus/ingestion/sisab.py, fora do PySUS), cruzado
com ICSAP (SIH). Só é gerado se a silver do SISAB existir (ver
internasus.processing.silver.gerar_silver_sisab); do contrário é pulado com
aviso, sem quebrar o resto da geração da gold.
"""

from datetime import date

import duckdb

from internasus.config import EXTERNAL_DATA_DIR, GOLD_DATA_DIR, SILVER_DATA_DIR
from internasus.domain import cnes_dominios


def conectar_silver() -> duckdb.DuckDBPyConnection:
    """Cria views DuckDB sobre os parquets já limpos em data/silver/."""
    con = duckdb.connect(database=":memory:")

    fontes = {
        "cnes_eq": SILVER_DATA_DIR / "cnes" / "cnes_eq.parquet",
        "cnes_lt": SILVER_DATA_DIR / "cnes" / "cnes_lt.parquet",
        "cnes_pf": SILVER_DATA_DIR / "cnes" / "cnes_pf.parquet",
        "cnes_sr": SILVER_DATA_DIR / "cnes" / "cnes_sr.parquet",
        "sia": SILVER_DATA_DIR / "sia" / "sia.parquet",
        "sih": SILVER_DATA_DIR / "sih" / "sih.parquet",
        "ibge_pop": SILVER_DATA_DIR / "ibge" / "ibge_pop.parquet",
        "sisab": SILVER_DATA_DIR / "sisab" / "sisab.parquet",
    }

    for nome, caminho in fontes.items():
        if caminho.exists():
            con.execute(
                f"CREATE OR REPLACE VIEW {nome} AS SELECT * FROM read_parquet('{caminho.as_posix()}')"
            )
        else:
            print(f"[conectar_silver] Aviso: '{nome}' não encontrado em {caminho} — pulando.")

    return con


def _preparar_views_derivadas(con: duckdb.DuckDBPyConnection) -> int | None:
    """Cria as views 'atual' (última competência de cada fonte CNES dentro da
    janela mantida pela silver), 'ibge_pop_ref' e 'dim_municipio'.
    Retorna o ano de referência (único ano presente em sia, já escolhido pela
    silver), ou None se sia/ibge_pop não estiverem disponíveis.
    """
    tabelas = con.execute("SHOW TABLES").df()["name"].tolist()

    for view in ["cnes_eq", "cnes_lt", "cnes_pf", "cnes_sr"]:
        if view in tabelas:
            con.execute(f"""
                CREATE OR REPLACE VIEW {view}_atual AS
                SELECT * FROM {view} WHERE COMPETEN = (SELECT MAX(COMPETEN) FROM {view})
            """)

    if "sia" not in tabelas or "ibge_pop" not in tabelas:
        return None

    ano_ref = con.execute("SELECT DISTINCT ano FROM sia").fetchone()[0]
    con.execute(f"""
        CREATE OR REPLACE VIEW ibge_pop_ref AS
        SELECT cod_mun, nome_mun, populacao FROM ibge_pop WHERE ano = {ano_ref}
    """)
    con.execute("""
        CREATE OR REPLACE VIEW dim_municipio AS
        SELECT cod_mun, nome_mun, populacao AS populacao_ref FROM ibge_pop_ref
    """)

    return ano_ref


def _salvar(df, nome: str) -> None:
    destino = GOLD_DATA_DIR / f"{nome}.parquet"
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destino, index=False)
    print(f"[_salvar] {nome} -> {destino} ({len(df)} linhas)")


def gold_dim_municipio(con: duckdb.DuckDBPyConnection) -> None:
    """Dimensão conformada: 1 linha por município de SP."""
    df = con.execute("SELECT * FROM dim_municipio").df()
    _salvar(df, "dim_municipio")


def gold_dim_estabelecimento(con: duckdb.DuckDBPyConnection) -> None:
    """Dimensão: 1 linha por CNES, com os atributos de cadastro que se repetem
    nas 4 fontes CNES (EQ/LT/PF/SR) — natureza jurídica, esfera administrativa,
    tipo de gestão, tipo de unidade, região de saúde etc. Dá para segmentar
    `fato_recursos_estabelecimento`/`fato_infra_estabelecimento` por esses atributos
    em vez de só por município.

    Um mesmo CNES aparece em mais de uma das 4 fontes com o mesmo cadastro, mas
    nem toda fonte preenche todo campo (ex.: REGSAUDE vem em branco em ~metade
    das linhas de uma fonte isolada) — por isso agregamos por CNES pegando
    qualquer valor não-vazio disponível entre as 4, em vez de fixar uma fonte
    "preferida" (que descartaria valor bom só por não ser da fonte prioritária).

    Ficam de fora: MICR_REG (microrregião — campo do CNES já identificado como
    descontinuado/não confiável, ver docs/docs/Resumo_Evolucao.md) e os campos
    que vieram 100% em branco nesta base (DISTRADM, NATUREZA, NIV_HIER, TERCEIRO).

    Além do código bruto, cada campo de domínio ganha uma coluna `*_desc` com a
    descrição (ver internasus/domain/cnes_dominios.py — inclui o achado de que
    `esfera_administrativa` vem, nesta base, idêntica a `tipo_gestao`)."""
    tabelas = con.execute("SHOW TABLES").df()["name"].tolist()
    se_atual = {"cnes_eq_atual", "cnes_lt_atual", "cnes_pf_atual", "cnes_sr_atual"}
    if not se_atual <= set(tabelas):
        print("[gold_dim_estabelecimento] Faltam views CNES '_atual' — pulando.")
        return

    colunas_comuns = (
        "CNES, CODUFMUN, REGSAUDE, DISTRSAN, TPGESTAO, PF_PJ, NIV_DEP, "
        "ESFERA_A, CLIENTEL, TP_UNID, TURNO_AT, NAT_JUR"
    )
    df = con.execute(f"""
        WITH base AS (
            SELECT {colunas_comuns} FROM cnes_eq_atual
            UNION ALL
            SELECT {colunas_comuns} FROM cnes_lt_atual
            UNION ALL
            SELECT {colunas_comuns} FROM cnes_pf_atual
            UNION ALL
            SELECT {colunas_comuns} FROM cnes_sr_atual
        )
        SELECT
            CNES AS cnes,
            MAX(NULLIF(TRIM(CODUFMUN), '')) AS cod_mun,
            MAX(NULLIF(TRIM(REGSAUDE), '')) AS cod_regiao_saude,
            MAX(NULLIF(TRIM(DISTRSAN), '')) AS cod_distrito_sanitario,
            MAX(NULLIF(TRIM(TPGESTAO), '')) AS tipo_gestao,
            MAX(NULLIF(TRIM(PF_PJ), '')) AS pessoa_fisica_juridica,
            MAX(NULLIF(TRIM(NIV_DEP), '')) AS nivel_dependencia,
            MAX(NULLIF(TRIM(ESFERA_A), '')) AS esfera_administrativa,
            MAX(NULLIF(TRIM(CLIENTEL), '')) AS clientela,
            MAX(NULLIF(TRIM(TP_UNID), '')) AS tipo_unidade,
            MAX(NULLIF(TRIM(TURNO_AT), '')) AS turno_atendimento,
            MAX(NULLIF(TRIM(NAT_JUR), '')) AS natureza_juridica
        FROM base
        GROUP BY CNES
    """).df()

    df["tipo_gestao_desc"] = cnes_dominios.decodificar(df, "tipo_gestao", cnes_dominios.GESTAO)
    df["esfera_administrativa_desc"] = cnes_dominios.decodificar(
        df, "esfera_administrativa", cnes_dominios.GESTAO
    )
    df["nivel_dependencia_desc"] = cnes_dominios.decodificar(
        df, "nivel_dependencia", cnes_dominios.NIVEL_DEPENDENCIA
    )
    df["clientela_desc"] = cnes_dominios.decodificar(df, "clientela", cnes_dominios.CLIENTELA)
    df["tipo_unidade_desc"] = cnes_dominios.decodificar(df, "tipo_unidade", cnes_dominios.TIPO_UNIDADE)
    df["turno_atendimento_desc"] = cnes_dominios.decodificar(
        df, "turno_atendimento", cnes_dominios.TURNO_ATENDIMENTO
    )
    df["natureza_juridica_desc"] = cnes_dominios.decodificar(
        df, "natureza_juridica", cnes_dominios.NATUREZA_JURIDICA
    )

    _salvar(df, "dim_estabelecimento")


def gold_dim_leito(con: duckdb.DuckDBPyConnection) -> None:
    """Dimensão: 1 linha por (TP_LEITO, CODLEITO) — tipo e especialidade do
    leito — com descrição. Grão pequeno (tabela de domínio), não por
    estabelecimento; junta com `fato_leitos_estabelecimento` via
    (tp_leito, codleito).

    Nenhum TP_LEITO representa "emergencial"/"urgência" — isso é caráter da
    internação (SIH.CAR_INT), não tipo de leito; ver docstring de
    `internasus.domain.cnes_dominios.TIPO_LEITO`."""
    tabelas = con.execute("SHOW TABLES").df()["name"].tolist()
    if "cnes_lt_atual" not in tabelas:
        print("[gold_dim_leito] Falta view 'cnes_lt_atual' — pulando.")
        return

    df = con.execute("""
        SELECT DISTINCT
            TRIM(TP_LEITO) AS tp_leito,
            TRIM(CODLEITO) AS codleito
        FROM cnes_lt_atual
        WHERE TRIM(TP_LEITO) != '' AND TRIM(CODLEITO) != ''
    """).df()

    df["tipo_leito_desc"] = cnes_dominios.decodificar(df, "tp_leito", cnes_dominios.TIPO_LEITO)
    df["codigo_leito_desc"] = cnes_dominios.decodificar(df, "codleito", cnes_dominios.CODIGO_LEITO)

    _salvar(df, "dim_leito")


def gold_fato_leitos_estabelecimento(con: duckdb.DuckDBPyConnection, data_ref: date) -> None:
    """Grão estabelecimento (CNES) x tipo de leito x especialidade do leito.
    Quebra os leitos por tipo/especialidade em vez do total agregado usado em
    `fato_filas_gargalos` (que só filtra TP_LEITO='1', cirúrgico) — dá pra
    cruzar com `dim_leito` para responder a pergunta de negócio sobre
    ocupação de leitos por tipo de procedimento (cirúrgico, obstétrico, UTI
    etc.) por município ou estabelecimento."""
    tabelas = con.execute("SHOW TABLES").df()["name"].tolist()
    if "cnes_lt_atual" not in tabelas:
        print("[gold_fato_leitos_estabelecimento] Falta view 'cnes_lt_atual' — pulando.")
        return

    df = con.execute(f"""
        SELECT
            CNES AS cnes,
            CODUFMUN AS cod_mun,
            TRIM(TP_LEITO) AS tp_leito,
            TRIM(CODLEITO) AS codleito,
            DATE '{data_ref.isoformat()}' AS data_referencia,
            SUM(TRY_CAST(QT_EXIST AS INTEGER)) AS qtd_leitos_existentes,
            SUM(TRY_CAST(QT_CONTR AS INTEGER)) AS qtd_leitos_contratados,
            SUM(TRY_CAST(QT_SUS AS INTEGER)) AS qtd_leitos_sus,
            SUM(TRY_CAST(QT_NSUS AS INTEGER)) AS qtd_leitos_nao_sus
        FROM cnes_lt_atual
        WHERE TRIM(TP_LEITO) != '' AND TRIM(CODLEITO) != ''
        GROUP BY CNES, CODUFMUN, TRIM(TP_LEITO), TRIM(CODLEITO)
    """).df()
    _salvar(df, "fato_leitos_estabelecimento")


def gold_dim_diagnostico(con: duckdb.DuckDBPyConnection) -> None:
    """Dimensão: 1 linha por código CID-10 (subcategoria de 4 caracteres ou
    categoria de 3, no formato usado por `SIH.DIAG_PRINC` — sem ponto, ex.
    'O800'), com a hierarquia completa (categoria/grupo/capítulo).

    Fonte: tabelas oficiais CID-10 do DATASUS (capítulos/grupos/categorias/
    subcategorias), obtidas via data/external/cid10/ (ver README de origem —
    mesmas 4 tabelas publicadas em datasus.saude.gov.br). Não geradas pela
    Silver porque não vêm de data/raw — são referência estática, por isso
    ficam em data/external/, não data/silver/.

    Cobertura validada contra os DIAG_PRINC reais do nosso SIH: 99,9%
    (8.713 de 8.722 códigos distintos) juntando primeiro por subcategoria (4
    caracteres) e, pro que sobrar, por categoria (3 caracteres — registros
    sem o dígito de subcategoria). Os 9 códigos sem tradução (`U09`, `U10`,
    `U109`, `N182`-`N185`, `C824`, `C826`) são revisões mais novas da CID-10
    (ex. condições pós-COVID-19) que não estão nesta tabela — ficam None."""
    caminho = EXTERNAL_DATA_DIR / "cid10"
    if not (caminho / "subcategorias.csv").exists():
        print(f"[gold_dim_diagnostico] Tabelas CID-10 não encontradas em {caminho} — pulando.")
        return

    for nome in ["capitulos", "grupos", "categorias", "subcategorias"]:
        con.execute(f"""
            CREATE OR REPLACE VIEW cid_{nome} AS
            SELECT * FROM read_csv('{(caminho / f"{nome}.csv").as_posix()}', header=true, all_varchar=true)
        """)

    df = con.execute("""
        WITH codigos AS (
            SELECT SUBCAT AS codigo, DESCRICAO AS descricao, SUBSTR(SUBCAT, 1, 3) AS cod_categoria
            FROM cid_subcategorias
            UNION
            SELECT CAT AS codigo, DESCRICAO AS descricao, CAT AS cod_categoria
            FROM cid_categorias
        ),
        -- CID-10-GRUPOS.CSV tem faixas aninhadas (um grupo amplo e sub-grupos
        -- dentro dele cobrem a mesma categoria) — sem isso o BETWEEN faz
        -- fan-out (1 categoria -> várias linhas de grupo). Fica só a faixa
        -- mais estreita (mais específica) por categoria (aproximação numérica
        -- da largura: letra*100 + 2 dígitos).
        grupo_por_categoria AS (
            SELECT
                c.cod_categoria,
                g.DESCRICAO AS descricao_grupo,
                ROW_NUMBER() OVER (
                    PARTITION BY c.cod_categoria
                    ORDER BY
                        (ascii(SUBSTR(g.CATFIM, 1, 1)) * 100 + TRY_CAST(SUBSTR(g.CATFIM, 2, 2) AS INTEGER))
                        - (ascii(SUBSTR(g.CATINIC, 1, 1)) * 100 + TRY_CAST(SUBSTR(g.CATINIC, 2, 2) AS INTEGER))
                ) AS rn
            FROM (SELECT DISTINCT cod_categoria FROM codigos) c
            JOIN cid_grupos g ON c.cod_categoria BETWEEN g.CATINIC AND g.CATFIM
            QUALIFY rn = 1
        )
        SELECT
            c.codigo,
            c.descricao,
            c.cod_categoria,
            cat.DESCRICAO AS descricao_categoria,
            gp.descricao_grupo,
            cap.NUMCAP AS numero_capitulo,
            cap.DESCRICAO AS descricao_capitulo
        FROM codigos c
        LEFT JOIN cid_categorias cat ON c.cod_categoria = cat.CAT
        LEFT JOIN grupo_por_categoria gp ON c.cod_categoria = gp.cod_categoria
        LEFT JOIN cid_capitulos cap ON c.cod_categoria BETWEEN cap.CATINIC AND cap.CATFIM
    """).df()
    _salvar(df, "dim_diagnostico")


def gold_fato_internacoes_diagnostico(con: duckdb.DuckDBPyConnection, data_ref: date) -> None:
    """Grão município x diagnóstico principal (CID-10). Principais causas de
    internação por município — cruza com `dim_diagnostico` para agrupar por
    categoria/grupo/capítulo (ex. "Doenças do aparelho circulatório").

    `MUNIC_RES` (residência do paciente) inclui município de qualquer UF do
    Brasil — pacientes de fora de SP internados em hospital de SP — enquanto
    `dim_municipio` só tem os 645 municípios de SP (mesmo escopo das outras
    fatos de grão município, que já ficam implicitamente restritas a SP por
    serem construídas a partir de `dim_municipio`). Sem o INNER JOIN abaixo,
    ~3,9% das internações (residentes de fora de SP) ficariam com `cod_mun`
    órfão ao cruzar com `dim_municipio` no consumo (Power BI/Streamlit)."""
    tabelas = con.execute("SHOW TABLES").df()["name"].tolist()
    if "sih" not in tabelas:
        print("[gold_fato_internacoes_diagnostico] Falta view 'sih' — pulando.")
        return

    df = con.execute(f"""
        SELECT
            s.MUNIC_RES AS cod_mun,
            s.DIAG_PRINC AS diagnostico_principal,
            DATE '{data_ref.isoformat()}' AS data_referencia,
            COUNT(*) AS total_internacoes,
            SUM(s.DIAS_PERM) AS dias_permanencia_total,
            SUM(CASE WHEN s.DIAS_PERM > 0 THEN 1 ELSE 0 END) AS internacoes_com_permanencia
        FROM sih s
        INNER JOIN dim_municipio dm ON s.MUNIC_RES = dm.cod_mun
        WHERE s.DIAG_PRINC IS NOT NULL AND TRIM(s.DIAG_PRINC) != ''
        GROUP BY s.MUNIC_RES, s.DIAG_PRINC
    """).df()
    _salvar(df, "fato_internacoes_diagnostico")


def gold_fato_filas_gargalos(con: duckdb.DuckDBPyConnection, data_ref: date) -> None:
    """Grão município. Une gargalos de exames (SIA x CNES-EQ), ocupação de
    leitos cirúrgicos (SIH x CNES-LT) e defasagem de serviços especializados
    (CNES-SR x SIA). Ver notebook, células dd534130 / e9519c47 / cb1a35da."""
    df = con.execute(f"""
        WITH producao_exames AS (
            SELECT LEFT(PA_MUNPCN, 6) AS cod_mun, COUNT(*) AS total_exames
            FROM sia WHERE PA_PROC_ID LIKE '02%' GROUP BY 1  -- 02 = finalidade diagnóstica (SIGTAP)
        ),
        equipamentos_disp AS (
            SELECT CODUFMUN AS cod_mun, SUM(QT_EXIST) AS total_equipamentos
            FROM cnes_eq_atual WHERE TIPEQUIP = '01' GROUP BY 1  -- Diagnóstico por Imagem (zero-padded)
        ),
        internacoes_cirurgicas AS (
            SELECT CNES, COUNT(*) AS volume_internacoes, SUM(DIAS_PERM) AS total_dias_permanencia
            FROM sih WHERE PROC_REA LIKE '04%' AND DIAS_PERM > 0 GROUP BY CNES  -- 04 = cirúrgicos (SIGTAP)
        ),
        leitos_cirurgicos AS (
            SELECT CNES, CODUFMUN AS cod_mun, SUM(QT_EXIST) AS qtd
            FROM cnes_lt_atual WHERE TP_LEITO = '1' GROUP BY CNES, CODUFMUN
        ),
        pressao_leitos AS (
            SELECT l.cod_mun,
                SUM(l.qtd) AS leitos_cirurgicos,
                SUM(i.volume_internacoes) AS cirurgias_realizadas,
                CASE
                    WHEN SUM(l.qtd) < 3 THEN NULL
                    WHEN (SUM(i.total_dias_permanencia) / NULLIF(SUM(l.qtd), 0) / 365.0) * 100 > 150 THEN NULL
                    ELSE ROUND((SUM(i.total_dias_permanencia) / NULLIF(SUM(l.qtd), 0) / 365.0) * 100, 2)
                END AS taxa_ocupacao_leitos_pct
            FROM leitos_cirurgicos l
            LEFT JOIN internacoes_cirurgicas i ON l.CNES = i.CNES
            GROUP BY l.cod_mun
        ),
        oferta_servicos AS (
            SELECT CODUFMUN AS cod_mun, COUNT(*) AS total_servicos FROM cnes_sr_atual GROUP BY 1
        ),
        producao_amb AS (
            SELECT LEFT(PA_UFMUN, 6) AS cod_mun, COUNT(*) AS total_producao FROM sia GROUP BY 1
        )
        SELECT
            d.cod_mun,
            DATE '{data_ref.isoformat()}' AS data_referencia,
            COALESCE(e.total_equipamentos, 0) AS equipamentos_imagem,
            COALESCE(p.total_exames, 0) AS exames_realizados,
            ROUND(COALESCE(p.total_exames, 0) * 1000.0 / NULLIF(d.populacao_ref, 0), 2) AS exames_por_mil_hab,
            ROUND(COALESCE(p.total_exames, 0) / NULLIF(e.total_equipamentos, 0), 2) AS exames_por_equipamento,
            CASE
                WHEN COALESCE(e.total_equipamentos, 0) = 0 AND COALESCE(p.total_exames, 0) > 0 THEN 'Sem equipamento próprio (gargalo)'
                WHEN COALESCE(e.total_equipamentos, 0) > 0 AND COALESCE(p.total_exames, 0) = 0 THEN 'Equipamento ocioso'
                WHEN COALESCE(e.total_equipamentos, 0) = 0 AND COALESCE(p.total_exames, 0) = 0 THEN 'Sem produção e sem equipamento'
                ELSE 'Com produção e equipamento'
            END AS situacao_exames,
            COALESCE(pl.leitos_cirurgicos, 0) AS leitos_cirurgicos,
            COALESCE(pl.cirurgias_realizadas, 0) AS cirurgias_realizadas,
            pl.taxa_ocupacao_leitos_pct,
            COALESCE(os.total_servicos, 0) AS servicos_especializados_cadastrados,
            COALESCE(pa.total_producao, 0) AS producao_ambulatorial,
            ROUND(COALESCE(pa.total_producao, 0) * 1000.0 / NULLIF(d.populacao_ref, 0), 2) AS producao_por_mil_hab,
            ROUND(COALESCE(os.total_servicos, 0) * 1000.0 / NULLIF(d.populacao_ref, 0), 4) AS servicos_por_mil_hab
        FROM dim_municipio d
        LEFT JOIN equipamentos_disp e ON d.cod_mun = e.cod_mun
        LEFT JOIN producao_exames p ON d.cod_mun = p.cod_mun
        LEFT JOIN pressao_leitos pl ON d.cod_mun = pl.cod_mun
        LEFT JOIN oferta_servicos os ON d.cod_mun = os.cod_mun
        LEFT JOIN producao_amb pa ON d.cod_mun = pa.cod_mun
    """).df()
    _salvar(df, "fato_filas_gargalos")


def gold_fato_desigualdade_regional(con: duckdb.DuckDBPyConnection, data_ref: date) -> None:
    """Grão município. Fuga assistencial (SIH) x infraestrutura per capita (CNES).
    Ver notebook, células afbe805d / 4a6e28ac."""
    df = con.execute(f"""
        WITH exportadores AS (
            SELECT
                MUNIC_RES AS cod_mun,
                COUNT(*) AS total_internacoes,
                SUM(CASE WHEN MUNIC_RES != MUNIC_MOV THEN 1 ELSE 0 END) AS evasao,
                ROUND(SUM(CASE WHEN MUNIC_RES != MUNIC_MOV THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS pct_evasao
            FROM sih GROUP BY MUNIC_RES HAVING COUNT(*) > 100
        ),
        polos AS (
            SELECT
                MUNIC_MOV AS cod_mun,
                COUNT(*) AS total_atendimentos,
                SUM(CASE WHEN MUNIC_RES != MUNIC_MOV THEN 1 ELSE 0 END) AS externos,
                ROUND(SUM(CASE WHEN MUNIC_RES != MUNIC_MOV THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS pct_pressao_externa
            FROM sih GROUP BY MUNIC_MOV
        ),
        leitos AS (SELECT CODUFMUN AS cod_mun, SUM(QT_EXIST) AS total FROM cnes_lt_atual GROUP BY 1),
        equipamentos AS (SELECT CODUFMUN AS cod_mun, SUM(QT_EXIST) AS total FROM cnes_eq_atual GROUP BY 1),
        servicos AS (SELECT CODUFMUN AS cod_mun, COUNT(*) AS total FROM cnes_sr_atual GROUP BY 1)
        SELECT
            d.cod_mun,
            DATE '{data_ref.isoformat()}' AS data_referencia,
            COALESCE(ex.total_internacoes, 0) AS total_internacoes_residentes,
            COALESCE(ex.evasao, 0) AS evasao_hospitalar,
            ex.pct_evasao,
            COALESCE(po.total_atendimentos, 0) AS total_atendimentos_polo,
            COALESCE(po.externos, 0) AS pacientes_externos,
            po.pct_pressao_externa,
            COALESCE(l.total, 0) AS leitos_total,
            COALESCE(e.total, 0) AS equipamentos_total,
            COALESCE(s.total, 0) AS servicos_total,
            ROUND(COALESCE(l.total, 0) * 1000.0 / NULLIF(d.populacao_ref, 0), 3) AS leitos_por_mil_hab,
            ROUND(COALESCE(e.total, 0) * 1000.0 / NULLIF(d.populacao_ref, 0), 3) AS equipamentos_por_mil_hab,
            ROUND(COALESCE(s.total, 0) * 1000.0 / NULLIF(d.populacao_ref, 0), 3) AS servicos_por_mil_hab
        FROM dim_municipio d
        LEFT JOIN exportadores ex ON d.cod_mun = ex.cod_mun
        LEFT JOIN polos po ON d.cod_mun = po.cod_mun
        LEFT JOIN leitos l ON d.cod_mun = l.cod_mun
        LEFT JOIN equipamentos e ON d.cod_mun = e.cod_mun
        LEFT JOIN servicos s ON d.cod_mun = s.cod_mun
        WHERE d.populacao_ref > 0
    """).df()
    _salvar(df, "fato_desigualdade_regional")


def gold_fato_profissionais(con: duckdb.DuckDBPyConnection, data_ref: date) -> None:
    """Grão município. Médicos/enfermeiros per capita (CNES-PF) x demanda de
    alta complexidade (SIA/SIH). Ver notebook, células 8be17627 / 1f8cbaef."""
    df = con.execute(f"""
        WITH prof AS (
            SELECT
                CODUFMUN AS cod_mun,
                COUNT(DISTINCT CASE WHEN CBO LIKE '225%' THEN CPF_PROF END) AS medicos,
                COUNT(DISTINCT CASE WHEN CBO LIKE '2235%' THEN CPF_PROF END) AS enfermeiros
            FROM cnes_pf_atual GROUP BY 1
        ),
        alta_complexidade AS (
            SELECT LEFT(PA_UFMUN, 6) AS cod_mun, COUNT(*) AS producao
            FROM sia WHERE PA_NIVCPL = '3' GROUP BY 1  -- 3 = alta complexidade (domínio PA_NIVCPL)
        ),
        cirurgias AS (
            SELECT MUNIC_MOV AS cod_mun, COUNT(*) AS total FROM sih WHERE PROC_REA LIKE '04%' GROUP BY 1
        )
        SELECT
            d.cod_mun,
            DATE '{data_ref.isoformat()}' AS data_referencia,
            COALESCE(p.medicos, 0) AS medicos,
            COALESCE(p.enfermeiros, 0) AS enfermeiros,
            ROUND(COALESCE(p.medicos, 0) * 1000.0 / NULLIF(d.populacao_ref, 0), 3) AS medicos_por_mil_hab,
            ROUND(COALESCE(p.enfermeiros, 0) * 1000.0 / NULLIF(d.populacao_ref, 0), 3) AS enf_por_mil_hab,
            COALESCE(a.producao, 0) AS producao_alta_complexidade,
            COALESCE(c.total, 0) AS cirurgias,
            COALESCE(a.producao, 0) + COALESCE(c.total, 0) AS demanda_alta_complexidade,
            -- demanda_por_especialista usa "medicos" (CBO 225%, mesmo filtro de cima) como base —
            -- não há um recorte de "especialista de alta complexidade" separado no CNES-PF.
            ROUND((COALESCE(a.producao, 0) + COALESCE(c.total, 0)) / NULLIF(p.medicos, 0), 2) AS demanda_por_especialista
        FROM dim_municipio d
        LEFT JOIN prof p ON d.cod_mun = p.cod_mun
        LEFT JOIN alta_complexidade a ON d.cod_mun = a.cod_mun
        LEFT JOIN cirurgias c ON d.cod_mun = c.cod_mun
        WHERE d.populacao_ref > 0
    """).df()
    _salvar(df, "fato_profissionais")


def gold_fato_infra_estabelecimento(con: duckdb.DuckDBPyConnection, data_ref: date) -> None:
    """Grão estabelecimento (CNES). Equipamento de imagem sem médico especialista
    vinculado. Ver notebook, célula 94e2dcde."""
    df = con.execute(f"""
        WITH medicos_especialistas AS (
            SELECT CNES, COUNT(DISTINCT CPF_PROF) AS qtd_especialistas
            FROM cnes_pf_atual WHERE CBO LIKE '225%' GROUP BY CNES
        ),
        equipamentos_alta_comp AS (
            SELECT CNES, CODUFMUN AS cod_mun, SUM(QT_EXIST) AS qtd_equip
            FROM cnes_eq_atual WHERE TIPEQUIP = '01' GROUP BY CNES, CODUFMUN
        )
        SELECT
            eq.CNES AS cnes,
            eq.cod_mun,
            DATE '{data_ref.isoformat()}' AS data_referencia,
            eq.qtd_equip AS qtd_equipamentos_imagem,
            COALESCE(pf.qtd_especialistas, 0) AS especialistas_vinculados,
            CASE
                WHEN COALESCE(pf.qtd_especialistas, 0) = 0 AND eq.qtd_equip > 0 THEN 'Infra Ociosa (Falta RH)'
                ELSE 'Operacional'
            END AS status_capacidade
        FROM equipamentos_alta_comp eq
        LEFT JOIN medicos_especialistas pf ON eq.CNES = pf.CNES
        WHERE eq.qtd_equip > 0
    """).df()
    _salvar(df, "fato_infra_estabelecimento")


def gold_fato_recursos_estabelecimento(con: duckdb.DuckDBPyConnection, data_ref: date) -> None:
    """Grão estabelecimento (CNES). Para cada estabelecimento: todos os
    profissionais (não só médicos), todos os leitos, todos os equipamentos e
    todos os serviços especializados cadastrados — mais o mesmo recurso
    relativizado pela população do município onde o estabelecimento fica
    (via dim_municipio), para identificar estabelecimentos com pouco recurso
    para o tamanho da população local. Sem limiar/flag embutido — os números
    ficam expostos pra quem consome (Power BI/Streamlit) ordenar/filtrar."""
    df = con.execute(f"""
        WITH profissionais AS (
            SELECT
                CNES,
                COUNT(DISTINCT CPF_PROF) AS total_profissionais,
                COUNT(DISTINCT CASE WHEN CBO LIKE '225%' THEN CPF_PROF END) AS medicos,
                COUNT(DISTINCT CASE WHEN CBO LIKE '2235%' THEN CPF_PROF END) AS enfermeiros
            FROM cnes_pf_atual GROUP BY CNES
        ),
        leitos AS (
            SELECT CNES, SUM(QT_EXIST) AS total_leitos FROM cnes_lt_atual GROUP BY CNES
        ),
        equipamentos AS (
            SELECT CNES, SUM(QT_EXIST) AS total_equipamentos FROM cnes_eq_atual GROUP BY CNES
        ),
        servicos AS (
            SELECT CNES, COUNT(*) AS total_servicos FROM cnes_sr_atual GROUP BY CNES
        ),
        -- universo de estabelecimentos = união de quem aparece em qualquer uma das 4 fontes CNES
        estabelecimentos AS (
            SELECT DISTINCT CNES, CODUFMUN AS cod_mun FROM cnes_eq_atual
            UNION
            SELECT DISTINCT CNES, CODUFMUN AS cod_mun FROM cnes_lt_atual
            UNION
            SELECT DISTINCT CNES, CODUFMUN AS cod_mun FROM cnes_pf_atual
            UNION
            SELECT DISTINCT CNES, CODUFMUN AS cod_mun FROM cnes_sr_atual
        )
        SELECT
            est.CNES AS cnes,
            est.cod_mun,
            DATE '{data_ref.isoformat()}' AS data_referencia,
            COALESCE(prof.total_profissionais, 0) AS total_profissionais,
            COALESCE(prof.medicos, 0) AS medicos,
            COALESCE(prof.enfermeiros, 0) AS enfermeiros,
            COALESCE(l.total_leitos, 0) AS total_leitos,
            COALESCE(e.total_equipamentos, 0) AS total_equipamentos,
            COALESCE(s.total_servicos, 0) AS total_servicos_especializados,
            dm.populacao_ref AS populacao_municipio,
            ROUND(COALESCE(prof.total_profissionais, 0) * 1000.0 / NULLIF(dm.populacao_ref, 0), 3) AS profissionais_por_mil_hab_municipio,
            ROUND(COALESCE(l.total_leitos, 0) * 1000.0 / NULLIF(dm.populacao_ref, 0), 3) AS leitos_por_mil_hab_municipio,
            ROUND(COALESCE(e.total_equipamentos, 0) * 1000.0 / NULLIF(dm.populacao_ref, 0), 3) AS equipamentos_por_mil_hab_municipio,
            ROUND(COALESCE(s.total_servicos, 0) * 1000.0 / NULLIF(dm.populacao_ref, 0), 4) AS servicos_por_mil_hab_municipio
        FROM estabelecimentos est
        LEFT JOIN profissionais prof ON est.CNES = prof.CNES
        LEFT JOIN leitos l ON est.CNES = l.CNES
        LEFT JOIN equipamentos e ON est.CNES = e.CNES
        LEFT JOIN servicos s ON est.CNES = s.CNES
        LEFT JOIN dim_municipio dm ON est.cod_mun = dm.cod_mun
    """).df()
    _salvar(df, "fato_recursos_estabelecimento")


def gold_fato_atencao_primaria(con: duckdb.DuckDBPyConnection, data_ref: date) -> None:
    """Grão município. Cobertura de Atenção Primária/ESF (SISAB) x
    internações por Condições Sensíveis à Atenção Primária - ICSAP (SIH).
    Responde à pergunta de negócio §3.1: "municípios com baixa cobertura da
    APS apresentam, proporcionalmente, mais internações evitáveis?".

    Filtro de CID-10 para CSAP (Condições Sensíveis à Atenção Primária) —
    lista ampliada de códigos por categoria de 3 caracteres: doenças
    infecciosas preveníveis/tratáveis na APS (tuberculose, difteria,
    coqueluche, tétano, meningites bacterianas), diabetes (E10-E14),
    hipertensão/doença hipertensiva e isquêmica do coração (I10, I11, I20),
    doenças respiratórias crônicas/agudas comuns na infância (asma, DPOC,
    pneumonias, infecções respiratórias altas) e gastroenterites/doenças
    infecciosas intestinais (K25-K28)."""
    df = con.execute(f"""
        WITH internacoes_totais AS (
            SELECT MUNIC_RES AS cod_mun, COUNT(*) AS total_internacoes FROM sih GROUP BY MUNIC_RES
        ),
        internacoes_icsap AS (
            SELECT MUNIC_RES AS cod_mun, COUNT(*) AS total_internacoes_icsap FROM sih
            WHERE SUBSTRING(DIAG_PRINC, 1, 3) IN (
                'A15', 'A16', 'A17', 'A18', 'A19', 'A36', 'A37', 'A33', 'A34', 'A35',
                'E10', 'E11', 'E12', 'E13', 'E14', 'I10', 'I11', 'I20',
                'J44', 'J45', 'J46', 'J00', 'J01', 'J02', 'J03', 'J06',
                'K25', 'K26', 'K27', 'K28'
            )
            GROUP BY MUNIC_RES
        )
        SELECT
            d.cod_mun,
            DATE '{data_ref.isoformat()}' AS data_referencia,
            COALESCE(s.cobertura_esf_pct, 0) AS cobertura_esf_pct,
            COALESCE(s.cobertura_eab_pct, 0) AS cobertura_eab_pct,
            s.qt_esf,
            s.qt_eap20,
            s.qt_eap30,
            s.qt_capacidade_equipe,
            COALESCE(i.total_internacoes, 0) AS total_internacoes,
            COALESCE(icsap.total_internacoes_icsap, 0) AS internacoes_icsap,
            ROUND(COALESCE(icsap.total_internacoes_icsap, 0) * 100.0 / NULLIF(i.total_internacoes, 0), 2) AS taxa_icsap_pct,
            ROUND(COALESCE(icsap.total_internacoes_icsap, 0) * 10000.0 / NULLIF(d.populacao_ref, 0), 2) AS icsap_por_10k_hab
        FROM dim_municipio d
        LEFT JOIN sisab s ON d.cod_mun = s.cod_mun
        LEFT JOIN internacoes_totais i ON d.cod_mun = i.cod_mun
        LEFT JOIN internacoes_icsap icsap ON d.cod_mun = icsap.cod_mun
        WHERE d.populacao_ref > 0
    """).df()
    _salvar(df, "fato_atencao_primaria")


def gerar_gold() -> None:
    """Gera todo o star schema da camada gold a partir da camada silver (data/silver/)."""
    con = conectar_silver()
    ano_ref = _preparar_views_derivadas(con)

    if ano_ref is None:
        print(
            "[gerar_gold] 'sia'/'ibge_pop' indisponíveis na silver — pulando toda a geração da gold."
        )
        return

    data_ref = date(ano_ref, 12, 31)
    print(
        f"[gerar_gold] Ano de referência (herdado da silver): {ano_ref} -> data_referencia = {data_ref.isoformat()}"
    )

    gold_dim_municipio(con)
    gold_dim_estabelecimento(con)
    gold_dim_leito(con)
    gold_dim_diagnostico(con)
    gold_fato_filas_gargalos(con, data_ref)
    gold_fato_desigualdade_regional(con, data_ref)
    gold_fato_profissionais(con, data_ref)
    gold_fato_infra_estabelecimento(con, data_ref)
    gold_fato_recursos_estabelecimento(con, data_ref)
    gold_fato_leitos_estabelecimento(con, data_ref)
    gold_fato_internacoes_diagnostico(con, data_ref)

    tabelas = con.execute("SHOW TABLES").df()["name"].tolist()
    if "sisab" in tabelas:
        try:
            gold_fato_atencao_primaria(con, data_ref)
            print("[gerar_gold] Bloco de Atenção Primária (fato_atencao_primaria) gerado com sucesso.")
        except Exception as e:
            print(f"[gerar_gold] Falha ao gerar fato_atencao_primaria: {e}")
    else:
        print(
            "[gerar_gold] Aviso: 'sisab' não encontrado na silver — pulando fato_atencao_primaria "
            "(rode internasus.ingestion.sisab e depois internasus.processing.silver antes)."
        )


if __name__ == "__main__":
    gerar_gold()