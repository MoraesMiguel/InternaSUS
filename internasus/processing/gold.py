"""
internasus.processing.gold
Camada Gold: lê os parquets da camada silver (data/silver/) e calcula os
indicadores/métricas finais, gravando cada um em data/gold/<nome>.parquet.

As queries aqui vieram do notebook InternaSUS.ipynb, adaptadas para ler da
camada silver (em vez do bronze direto) e gravar o resultado em disco.

Só estão ativas as métricas que dependem SOMENTE de CNES/SIA (já disponíveis).
As que dependem de SIH ou SIDRA/IBGE (ainda não baixados) ficam como funções
prontas, mas puladas com aviso — ative-as normalmente assim que os dados
existirem em data/silver/sih/ e data/silver/sidra/ (ou ibge_pop).
"""

from pathlib import Path
import duckdb

PROJ_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_SILVER = PROJ_ROOT / "data" / "silver"
DATA_GOLD = PROJ_ROOT / "data" / "gold"


def conectar_silver() -> duckdb.DuckDBPyConnection:
    """Cria views DuckDB sobre os parquets já limpos em data/silver/."""
    con = duckdb.connect(database=":memory:")

    fontes = {
        "cnes_eq": DATA_SILVER / "cnes" / "cnes_eq.parquet",
        "cnes_lt": DATA_SILVER / "cnes" / "cnes_lt.parquet",
        "cnes_pf": DATA_SILVER / "cnes" / "cnes_pf.parquet",
        "cnes_sr": DATA_SILVER / "cnes" / "cnes_sr.parquet",
        "cnes_st": DATA_SILVER / "cnes" / "cnes_st.parquet",
        "sia": DATA_SILVER / "sia" / "sia.parquet",
        # "sih": DATA_SILVER / "sih" / "sih.parquet",           # ativar quando existir
        # "sidra": DATA_SILVER / "sidra" / "sidra.parquet",     # ativar quando existir
        # "ibge_pop": DATA_SILVER / "sidra" / "ibge_pop.parquet",
    }

    for nome, caminho in fontes.items():
        if caminho.exists():
            con.execute(f"CREATE OR REPLACE VIEW {nome} AS SELECT * FROM read_parquet('{caminho}')")
        else:
            print(f"[conectar_silver] Aviso: '{nome}' não encontrado em {caminho} — pulando.")

    return con


def _salvar(df, nome: str) -> None:
    destino = DATA_GOLD / f"{nome}.parquet"
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destino, index=False)
    print(f"[_salvar] {nome} -> {destino} ({len(df)} linhas)")


def gold_infra_sem_profissionais(con: duckdb.DuckDBPyConnection) -> None:
    """
    4.1 Infraestrutura adequada carente de profissionais operacionais.
    Depende só de CNES (cnes_eq + cnes_pf) — disponível agora.
    """
    df = con.execute("""
        WITH medicos_especialistas AS (
            SELECT
                CNES,
                COUNT(DISTINCT CPF_PROF) AS qtd_anestesistas_cirurgioes
            FROM cnes_pf
            WHERE CBO IN ('225151', '225203')
            GROUP BY CNES
        ),
        equipamentos_alta_comp AS (
            SELECT
                CNES,
                MUNICIP AS cod_mun,
                SUM(CAST(QT_EXIST AS INTEGER)) AS qtd_equip_cirurgicos
            FROM cnes_eq
            WHERE CODEQUIP IN ('05', '06')
            GROUP BY CNES, MUNICIP
        )
        SELECT
            eq.cod_mun,
            eq.CNES,
            eq.qtd_equip_cirurgicos,
            COALESCE(pf.qtd_anestesistas_cirurgioes, 0) AS especialistas_vinculados,
            CASE
                WHEN COALESCE(pf.qtd_anestesistas_cirurgioes, 0) = 0 AND eq.qtd_equip_cirurgicos > 0
                THEN 'Infra Ociosa (Falta RH)'
                ELSE 'Operacional'
            END AS status_capacidade
        FROM equipamentos_alta_comp eq
        LEFT JOIN medicos_especialistas pf ON eq.CNES = pf.CNES
        WHERE eq.qtd_equip_cirurgicos > 0
        ORDER BY especialistas_vinculados ASC, eq.qtd_equip_cirurgicos DESC
    """).df()
    _salvar(df, "infra_sem_profissionais")


# --- Métricas que dependem de fontes ainda não baixadas (SIH e/ou SIDRA/IBGE) ---
# Deixe assim até baixar os dados; depois é só remover o "return" de aviso.

def gold_gargalos_exames(con: duckdb.DuckDBPyConnection) -> None:
    """1.1 Ociosidade vs Sobrecarga de Equipamentos — precisa de ibge_pop (SIDRA)."""
    tabelas = con.execute("SHOW TABLES").df()["name"].tolist()
    if "ibge_pop" not in tabelas:
        print("[gold_gargalos_exames] Pulado: precisa de 'ibge_pop' (SIDRA), ainda não disponível.")
        return

    df = con.execute("""
        WITH producao_exames AS (
            SELECT MUNIC_RES AS cod_mun, COUNT(*) AS total_exames_realizados
            FROM sia WHERE PROC_REA LIKE '02%' GROUP BY MUNIC_RES
        ),
        equipamentos_disp AS (
            SELECT CODUFMUN AS cod_mun, SUM(CAST(QT_EXIST AS INTEGER)) AS total_equipamentos
            FROM cnes_eq WHERE CODEQUIP IN ('01', '02', '03') GROUP BY CODUFMUN
        )
        SELECT
            i.cod_mun, i.nome_mun, i.populacao,
            COALESCE(e.total_equipamentos, 0) AS equipamentos,
            COALESCE(p.total_exames_realizados, 0) AS exames_realizados,
            ROUND(COALESCE(p.total_exames_realizados, 0) / NULLIF(e.total_equipamentos, 0), 2) AS exames_por_equipamento
        FROM ibge_pop i
        LEFT JOIN equipamentos_disp e ON i.cod_mun = e.cod_mun
        LEFT JOIN producao_exames p ON i.cod_mun = p.cod_mun
        ORDER BY exames_por_equipamento DESC
    """).df()
    _salvar(df, "gargalos_exames")


def gold_pressao_leitos(con):
    """1.2 Taxa de Ocupação e Pressão sobre Leitos Cirúrgicos — precisa de SIH."""
    if "sih" not in con.execute("SHOW TABLES").df()["name"].tolist():
        print("[gold_pressao_leitos] Pulado: precisa de 'sih', ainda não disponível.")
        return
    # SQL igual ao do notebook (seção 1.2) — reative quando sih existir.


def gold_municipios_exportadores(con):
    """2.1 Municípios exportadores de pacientes — precisa de SIH."""
    if "sih" not in con.execute("SHOW TABLES").df()["name"].tolist():
        print("[gold_municipios_exportadores] Pulado: precisa de 'sih', ainda não disponível.")
        return
    # SQL igual ao do notebook (seção 2.1) — reative quando sih existir.


def gold_polos_sobrecarregados(con):
    """2.2 Polos regionais sobrecarregados — precisa de SIH."""
    if "sih" not in con.execute("SHOW TABLES").df()["name"].tolist():
        print("[gold_polos_sobrecarregados] Pulado: precisa de 'sih', ainda não disponível.")
        return
    # SQL igual ao do notebook (seção 2.2) — reative quando sih existir.


def gold_icsap_vs_aps(con):
    """3.1 Internações evitáveis vs cobertura APS — precisa de SIH e sisab_indicadores."""
    tabelas = con.execute("SHOW TABLES").df()["name"].tolist()
    if "sih" not in tabelas or "sisab_indicadores" not in tabelas:
        print("[gold_icsap_vs_aps] Pulado: precisa de 'sih' e 'sisab_indicadores', ainda não disponíveis.")
        return
    # SQL igual ao do notebook (seção 3.1) — reative quando as fontes existirem.


def gold_vazios_assistenciais(con: duckdb.DuckDBPyConnection) -> None:
    """4.2 Vazios assistenciais (profissionais por 1000 hab) — precisa de ibge_pop."""
    if "ibge_pop" not in con.execute("SHOW TABLES").df()["name"].tolist():
        print("[gold_vazios_assistenciais] Pulado: precisa de 'ibge_pop' (SIDRA), ainda não disponível.")
        return
    # SQL igual ao do notebook (seção 4.2) — reative quando ibge_pop existir.


if __name__ == "__main__":
    con = conectar_silver()
    gold_infra_sem_profissionais(con)
    gold_gargalos_exames(con)
    gold_pressao_leitos(con)
    gold_municipios_exportadores(con)
    gold_polos_sobrecarregados(con)
    gold_icsap_vs_aps(con)
    gold_vazios_assistenciais(con)
