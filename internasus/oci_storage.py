"""
internasus.oci_storage
Upload dos parquets locais (data/raw, data/silver, data/gold) para os
buckets correspondentes no OCI Object Storage.

Uso via CLI (requer ~/.oci/config já configurado):
    python -m internasus.oci_storage publish-raw
    python -m internasus.oci_storage publish-silver
    python -m internasus.oci_storage publish-gold
    python -m internasus.oci_storage publish-all
"""

from pathlib import Path

import oci
import typer

from internasus.config import GOLD_DATA_DIR, RAW_DATA_DIR, SILVER_DATA_DIR

# Nome dos buckets criados no Console OCI
BUCKET_BRONZE = "datasus-raw"
BUCKET_SILVER = "datasus-silver"
BUCKET_GOLD = "datasus-gold"

# Região onde os buckets foram criados (Brazil East - São Paulo)
REGION = "sa-saopaulo-1"

app = typer.Typer()


def _get_client() -> tuple[oci.object_storage.ObjectStorageClient, str]:
    """
    Cria o client do Object Storage a partir do ~/.oci/config e descobre
    automaticamente o namespace da tenancy (não precisa ser digitado à mão).
    """
    config = oci.config.from_file()  # lê ~/.oci/config por padrão
    config["region"] = REGION
    client = oci.object_storage.ObjectStorageClient(config)
    namespace = client.get_namespace().data
    return client, namespace


def upload_arquivo(caminho_local: Path, bucket: str, nome_objeto: str | None = None) -> None:
    """
    Envia um único arquivo local para um bucket do OCI.

    caminho_local: caminho do arquivo no seu PC (ex: data/raw/fonte=SIH/.../arquivo.parquet)
    bucket: nome do bucket de destino (use as constantes BUCKET_BRONZE/SILVER/GOLD)
    nome_objeto: caminho/nome que o arquivo terá dentro do bucket.
                 Se não informado, usa o mesmo caminho relativo do arquivo local
                 (preservando a estrutura fonte=/uf=/ano=/mes=/dataset=).
    """
    client, namespace = _get_client()

    if nome_objeto is None:
        nome_objeto = caminho_local.name

    with open(caminho_local, "rb") as f:
        client.put_object(
            namespace_name=namespace,
            bucket_name=bucket,
            object_name=nome_objeto,
            put_object_body=f,
        )
    print(f"[upload] {caminho_local} -> oci://{bucket}/{nome_objeto}")


def upload_pasta(pasta_local: Path, bucket: str, prefixo: str = "") -> None:
    """
    Envia todos os arquivos .parquet de uma pasta (recursivamente) para um bucket,
    preservando a estrutura de subpastas como "prefixo" do nome do objeto.

    Exemplo:
        upload_pasta(Path("data/raw"), BUCKET_BRONZE)
        # data/raw/fonte=CNES/uf=SP/ano=2020/mes=01/dataset=PF/PFSP2001.parquet
        # vira o objeto: fonte=CNES/uf=SP/ano=2020/mes=01/dataset=PF/PFSP2001.parquet
    """
    client, namespace = _get_client()
    arquivos = list(pasta_local.rglob("*.parquet"))

    if not arquivos:
        print(f"[upload_pasta] Nenhum .parquet encontrado em {pasta_local}")
        return

    print(
        f"[upload_pasta] Enviando {len(arquivos)} arquivo(s) de {pasta_local} para bucket '{bucket}'..."
    )

    for i, arquivo in enumerate(arquivos, start=1):
        caminho_relativo = arquivo.relative_to(pasta_local)
        nome_objeto = (
            f"{prefixo}{caminho_relativo.as_posix()}" if prefixo else caminho_relativo.as_posix()
        )

        with open(arquivo, "rb") as f:
            client.put_object(
                namespace_name=namespace,
                bucket_name=bucket,
                object_name=nome_objeto,
                put_object_body=f,
            )
        print(f"  [{i}/{len(arquivos)}] {caminho_relativo} -> oci://{bucket}/{nome_objeto}")

    print("[upload_pasta] Concluído.")


@app.command("publish-raw")
def publish_raw() -> None:
    """Envia data/raw/ (camada Bronze) para o bucket datasus-raw."""
    upload_pasta(RAW_DATA_DIR, BUCKET_BRONZE)


@app.command("publish-silver")
def publish_silver() -> None:
    """Envia data/silver/ para o bucket datasus-silver."""
    upload_pasta(SILVER_DATA_DIR, BUCKET_SILVER)


@app.command("publish-gold")
def publish_gold() -> None:
    """Envia data/gold/ para o bucket datasus-gold."""
    upload_pasta(GOLD_DATA_DIR, BUCKET_GOLD)


@app.command("publish-all")
def publish_all() -> None:
    """Envia data/raw/, data/silver/ e data/gold/ para os respectivos buckets, em sequência."""
    publish_raw()
    publish_silver()
    publish_gold()


if __name__ == "__main__":
    app()
