"""
internasus.processing.gold
Camada Gold: lê os parquets da camada silver (data/silver/) e monta um star
schema (1 dimensão conformada + tabelas fato) para consumo no Power BI,
gravando cada tabela em data/gold/<nome>.parquet.

Schema:
  dim_municipio                  -- 1 linha por município de SP (cod_mun, nome, população)
  fato_filas_gargalos            -- grão município (README §2.1)
  fato_desigualdade_regional     -- grão município (README §2.2)
  fato_profissionais             -- grão município (README §2.4)
  fato_infra_estabelecimento     -- grão estabelecimento/CNES: equip. de imagem x médico (README §2.1/§2.4)
  fato_recursos_estabelecimento  -- grão estabelecimento/CNES: profissionais + leitos + equipamentos +
                                     serviços especializados, todos, e per capita em cima da população
                                     do município onde o estabelecimento fica

Todas as tabelas fato têm uma coluna `data_referencia` (DATE) — o grão
temporal deste MVP é um único ponto no tempo por tabela (última competência
disponível do CNES / ano de referência do SIA-SIH, já escopados pela camada
silver), então `data_referencia` é um rótulo único (31/dez do ano de
referência) para relacionar com a tabela Calendário que o usuário importa no
Power BI — não é uma data de evento linha a linha.

As queries abaixo portam, sem mudança de lógica, as células já validadas em
notebooks/InternaSUS.ipynb (execução completa sem erros contra os dados
reais) — os comentários "ver notebook, célula X" apontam a célula de origem.

O bloco de Atenção Primária (perguntas de negócio §3) não é gerado aqui:
depende do SISAB/SIAPS, que não está ingerido no projeto (ver README §3.4
e Achado 4 do notebook).
"""

from datetime import date

import duckdb

from internasus.config import GOLD_DATA_DIR, SILVER_DATA_DIR


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
                   ROUND((SUM(i.total_dias_permanencia) / NULLIF(SUM(l.qtd), 0) / 365.0) * 100, 2) AS taxa_ocupacao_leitos_pct
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
    gold_fato_filas_gargalos(con, data_ref)
    gold_fato_desigualdade_regional(con, data_ref)
    gold_fato_profissionais(con, data_ref)
    gold_fato_infra_estabelecimento(con, data_ref)
    gold_fato_recursos_estabelecimento(con, data_ref)

    print(
        "[gerar_gold] Bloco de Atenção Primária (perguntas de negócio §3) não gerado: "
        "depende do SISAB/SIAPS, que não está ingerido no projeto (ver README §3.4)."
    )


if __name__ == "__main__":
    gerar_gold()
