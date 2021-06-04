import logging
import os
import json
from pathlib import Path
from keboola.component import CommonInterface
from google_cloud_storage.client import StorageClient
from google.auth.exceptions import GoogleAuthError
from google.api_core.exceptions import NotFound

KEY_BUCKET_NAME = "bucket_name"
KEY_SERVICE_ACCOUNT = "#service_account_key"
KEY_FILE_NAME = "file_name"

REQUIRED_PARAMETERS = [KEY_SERVICE_ACCOUNT, KEY_BUCKET_NAME, KEY_FILE_NAME]
REQUIRED_IMAGE_PARS = []


class UserException(Exception):
    pass


def get_local_data_path():
    return Path(__file__).resolve().parent.parent.joinpath('data').as_posix()


def get_data_folder_path():
    data_folder_path = None
    if not os.environ.get('KBC_DATADIR'):
        data_folder_path = get_local_data_path()
    return data_folder_path


class Component(CommonInterface):
    def __init__(self):
        data_folder_path = get_data_folder_path()
        super().__init__(data_folder_path=data_folder_path)
        try:
            self.validate_configuration(REQUIRED_PARAMETERS)
            self.validate_image_parameters(REQUIRED_IMAGE_PARS)
        except ValueError as e:
            logging.exception(e)
            exit(1)

    def run(self):
        params = self.configuration.parameters
        service_account_json_key = params.get(KEY_SERVICE_ACCOUNT)
        bucket_name = params.get(KEY_BUCKET_NAME)
        try:
            service_account_json_key = KeyCredentials(service_account_json_key).key
            storage_client = StorageClient(bucket_name,
                                           service_account_json_key=service_account_json_key)
        except ValueError as value_error:
            raise UserException(value_error)

        file_name = params.get(KEY_FILE_NAME)
        table = self.create_out_table_definition(file_name)
        self.download_file(storage_client, bucket_name, table)

        with open(table.full_path, 'r') as ft:
            header = ft.readline()
            header_list = header.split(',')
        table.columns = header_list
        self.write_tabledef_manifest(table)

    @staticmethod
    def download_file(storage_client, bucket_name, file):
        try:
            storage_client.download_blob(bucket_name, file.name, file.full_path)
        except GoogleAuthError as google_error:
            raise UserException(f"Download failed after retries due to : {google_error}")
        except NotFound as not_found:
            raise UserException(f"File {file.name} could not be found in bucket") from not_found
        logging.info(f"Blob {file.name} downloaded to storage")


class KeyCredentials:
    REQUIRED_KEY_PARAMETERS = ["client_email", "token_uri", "private_key", "project_id"]

    def __init__(self, key_string):
        self.key = self.parse_key_string(key_string)
        self.validate_key()

    @staticmethod
    def parse_key_string(key_string):
        try:
            key = json.loads(key_string, strict=False)
        except (ValueError, TypeError):
            raise UserException("The service account key format is incorrect, copy and paste the whole JSON content "
                                "of the key file into the text field")
        return key

    def validate_key(self):
        missing_fields = []
        for par in self.REQUIRED_KEY_PARAMETERS:
            if not self.key.get(par):
                missing_fields.append(par)

        if missing_fields:
            raise UserException(f'Google service account key is missing mandatory fields: {missing_fields} ')


"""
        Main entrypoint
"""
if __name__ == "__main__":
    try:
        comp = Component()
        comp.run()
    except UserException as exc:
        logging.exception(exc)
        exit(1)
    except Exception as exc:
        logging.exception(exc)
        exit(2)
