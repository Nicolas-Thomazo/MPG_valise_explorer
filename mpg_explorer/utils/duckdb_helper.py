import os

import duckdb


def azure_secret():
    """
    This function is connection DuckDB to our Azure storage using connection string
    """
    conn_string = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    duckdb.sql("install azure")
    duckdb.sql("load azure")
    duckdb.sql(f"set azure_storage_connection_string = '{conn_string}'")
    duckdb.sql(f"set azure_transport_option_type = 'curl'")
