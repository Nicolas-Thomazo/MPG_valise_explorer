import os
from io import BytesIO

import polars as pl
from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient


class AzureUtils:
    """
    Cette classe permet de lire et écrire des blobs depuis le container Azure MPG_valise_explorer par défaut.
    """

    def __init__(self, container_name="scrapping-exports"):
        conn_string = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
        self.blob_service_client = BlobServiceClient.from_connection_string(conn_string)
        self.container_name = container_name

    def read_file(self, path):
        try:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=path)
            return BytesIO(blob_client.download_blob().readall())
        except ResourceNotFoundError:
            print(f"No file found at path '{path}'.")

    def write_file(self, data: pl.DataFrame, path: str):
        """
        On récupère un dataframe polars, mais il n'y a pas d'implémentation pour l'écrire sur Azure directement
        Donc on est obligé de le transformer en Pandas.

        :param data: Dataframe polars
        :param path: Path où écrire le blob
        """
        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=path)
        blob_client.upload_blob(data.to_pandas().to_parquet(), overwrite=True)
