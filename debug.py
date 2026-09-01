import duckdb

query = "SELECT * FROM read_parquet('data/raw/fonte=SISAB/**/*.parquet', hive_partitioning=true) LIMIT 1"
colunas = duckdb.execute(query).df().columns.tolist()

for col in colunas:
    print(col)