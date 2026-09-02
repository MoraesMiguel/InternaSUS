from internasus.processing.gold import conectar_silver, _preparar_views_derivadas

con = conectar_silver()
_preparar_views_derivadas(con)

# pega o código IBGE do município a partir do nome (via dim_municipio)
cod = con.execute("SELECT cod_mun FROM dim_municipio WHERE nome_mun ILIKE '%Iguape%'").fetchone()[0]
print("cod_mun:", cod)

# 1. confirma o total/evasão bruto pra essa cidade
print(con.execute(f"""
    SELECT
        MUNIC_RES, COUNT(*) AS total,
        SUM(CASE WHEN MUNIC_RES != MUNIC_MOV THEN 1 ELSE 0 END) AS evasao
    FROM sih
    WHERE MUNIC_RES = '{cod}'
    GROUP BY 1
""").df())

# 2. a pergunta chave: esse município TEM leito de internação cadastrado no CNES?
print(con.execute(f"""
    SELECT COUNT(*) AS total_leitos
    FROM cnes_lt_atual
    WHERE CODUFMUN = '{cod}'
""").df())