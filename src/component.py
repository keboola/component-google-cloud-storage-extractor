import logging
import os
import json
import ntpath
from keboola.utils.header_normalizer import get_normalizer, NormalizerStrategy
from keboola.component.base import ComponentBase, sync_action
from keboola.component.sync_actions import SelectElement
from google_cloud_storage.client import StorageClient
from google.auth.exceptions import GoogleAuthError
from google.api_core.exceptions import NotFound

KEY_SERVICE_ACCOUNT = "#service_account_key"

KEY_BUCKET_NAME = "bucket_name"
KEY_BUCKET_NAME_ARRAY = "bucket_name_array"

KEY_FILE_NAME = "file_name"
KEY_FILE_NAMES_ARRAY = "file_names_array"

REQUIRED_PARAMETERS = [KEY_SERVICE_ACCOUNT]
REQUIRED_IMAGE_PARS = []

logging.info("imported")


class UserException(Exception):
    pass


class Component(ComponentBase):
    def __init__(self):
        super().__init__()

        try:
            self.validate_configuration_parameters(REQUIRED_PARAMETERS)
            self.validate_image_parameters(REQUIRED_IMAGE_PARS)
        except ValueError as e:
            logging.exception(e)
            exit(1)

    def run(self):
        params = self.configuration.parameters
        service_account_json_key = params.get(KEY_SERVICE_ACCOUNT)

        bucket_name = params.get(KEY_BUCKET_NAME) or params.get(KEY_BUCKET_NAME_ARRAY)[0]

        try:
            service_account_json_key = KeyCredentials(service_account_json_key).key
            storage_client = StorageClient(bucket_name,
                                           service_account_json_key=service_account_json_key)
        except ValueError as value_error:
            raise UserException(value_error)

        if params.get(KEY_FILE_NAME):
            file_names = [params.get(KEY_FILE_NAME)]
        else:
            file_names = params.get(KEY_FILE_NAMES_ARRAY)

        out_folder = self.files_out_path
        normalizer = get_normalizer(NormalizerStrategy.DEFAULT, forbidden_sub="_")

        for file_name in file_names:
            filename = normalizer.normalize_header([ntpath.basename(file_name)])[0]
            output_destination = os.path.join(out_folder, filename)

            self.download_file(storage_client, bucket_name, file_name, output_destination)
            logging.info(f"Blob {file_name} downloaded to storage")

    @staticmethod
    def download_file(storage_client, bucket_name, file_name, output_destination):
        try:
            return storage_client.download_blob(bucket_name, file_name, output_destination)
        except GoogleAuthError as google_error:
            raise UserException(f"Download failed after retries due to : {google_error}")
        except NotFound as not_found:
            raise UserException(f"File {file_name} could not be found in bucket") from not_found

    @sync_action('list_buckets')
    def list_buckets(self):
        params = self.configuration.parameters
        service_account_json = params.get(KEY_SERVICE_ACCOUNT)
        try:
            service_account_json_key = KeyCredentials(service_account_json).key
            storage_client = StorageClient(service_account_json_key=service_account_json_key)
            available_buckets = storage_client.list_buckets()
            buckets_list = []
            for bucket in available_buckets:
                buckets_list.append(bucket.name)

        except ValueError as value_error:
            raise UserException(value_error)

        except Exception as e:
            raise UserException(e)

        result_buckets = [SelectElement(value=bucket) for bucket in buckets_list]
        return result_buckets

    @sync_action('list_files')
    def list_files(self):
        params = self.configuration.parameters
        service_account_json = params.get(KEY_SERVICE_ACCOUNT)
        parent_bucket = params.get(KEY_BUCKET_NAME_ARRAY)

        try:
            service_account_json_key = KeyCredentials(service_account_json).key
            storage_client = StorageClient(service_account_json_key=service_account_json_key)

            blobs = []

            for blob in storage_client.list_blobs(parent_bucket[0]):
                blobs.append(blob.name)

        except ValueError as value_error:
            raise UserException(value_error)

        result_files = [SelectElement(value=file) for file in blobs]
        return result_files


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


# Main entrypoint
if __name__ == "__main__":
    try:
        comp = Component()
        comp.execute_action()
    except UserException as exc:
        logging.exception(exc)
        exit(1)
    except Exception as exc:
        logging.exception(exc)
        exit(2)
