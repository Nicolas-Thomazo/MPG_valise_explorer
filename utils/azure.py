from io import StringIO

import polars as pl
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient


class AzureUtils:
    """
    Cette classe permet de lire et écrire des blobs depuis le container Azure MPG_valise_explorer par défaut.
    """

    def __init__(self, container_name="MPG_valise_explorer"):
        token_credential = DefaultAzureCredential()
        account_url = ""  # https://learn.microsoft.com/en-us/python/api/overview/azure/storage-blob-readme?view=azure-python
        self.blob_service_client = BlobServiceClient(account_url=account_url, credential=token_credential)
        self.container_name = container_name

    def read_file(self, path):
        downloaded_blob = self.blob_service_client.download_blob(path, encoding="utf8")
        return StringIO(downloaded_blob.readall())

    def write_file(self, data: pl.DataFrame, path: str):
        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=path)
        blob_client.upload_blob(data, overwrite=True)
