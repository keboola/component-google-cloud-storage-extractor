import fnmatch
import json
import logging
import os
from datetime import datetime
from typing import List

from google.api_core.exceptions import NotFound
from google.auth.exceptions import GoogleAuthError
from keboola.component.base import ComponentBase, sync_action
from keboola.component.sync_actions import SelectElement

from configuration import Configuration
from google_cloud_storage.client import StorageClient

KEY_SERVICE_ACCOUNT = "#service_account_key"

REQUIRED_PARAMETERS = [KEY_SERVICE_ACCOUNT]
REQUIRED_IMAGE_PARS = []

logging.info("imported")


class UserException(Exception):
    pass


class Component(ComponentBase):
    def __init__(self):
        super().__init__()

    def _init_configuration(self) -> None:
        self.validate_configuration_parameters(Configuration.get_dataclass_required_parameters())
        self._configuration: Configuration = Configuration.load_from_dict(self.configuration.parameters)

    def run(self):

        params = self.configuration.parameters
        self._init_configuration()

        current_date_time = datetime.now()

        service_account_json = params.get(KEY_SERVICE_ACCOUNT)
        new_files_only = self._configuration.files.new_files_only
        out_folder = self.files_out_path

        try:
            service_account_json_key = KeyCredentials(service_account_json).key
            storage_client: StorageClient = StorageClient(service_account_json_key=service_account_json_key)

        except ValueError as value_error:
            raise UserException(value_error)

        blobs = []

        if self._configuration.files.file_name:  # using file path or wildcard
            bucket_name = self.get_bucket_name_from_path()
            for blob in storage_client.list_blobs(bucket_name):
                if not blob.name.endswith("/") and fnmatch.fnmatch(bucket_name + "/" + blob.name,
                                                                   self._configuration.files.file_name):
                    blobs.append(blob)

        else:  # defined bucket and file names
            bucket_name = self._configuration.bucket_name or self._configuration.files.bucket_name_array[0]
            file_names = [self._configuration.file_name] if self._configuration.file_name \
                else self._configuration.files.file_names_array

            blobs = self.get_blobs_from_names(storage_client, bucket_name, file_names)

        downloaded_files = self.download_blobs(storage_client, out_folder, new_files_only, blobs)

        self._create_manifests(downloaded_files,
                               self._configuration.destination.custom_tag,
                               self._configuration.destination.permanent)

        self.write_state_file({"last_run": current_date_time.isoformat()})

    def get_bucket_name_from_path(self) -> str:
        """
        Get bucket name from file path. If the file path starts with "/",
        the bucket name is the second element of the path.
        Returns:

        """
        if self._configuration.files.file_name.startswith("/"):
            return self._configuration.files.file_name.split("/")[1]
        else:
            return self._configuration.files.file_name.split("/")[0]

    def download_blobs(self, storage_client, out_folder, new_files_only, blobs) -> List[str]:
        downloaded_files = []
        last_run = datetime.fromisoformat(self.get_state_file().get("last_run", "2000-01-01T15:05:36.675730"))

        for blob in blobs:
            if not new_files_only or (new_files_only and blob.updated.replace(tzinfo=None) > last_run):
                filename = f'{blob.bucket.name}/{blob.name}'
                output_destination = os.path.join(out_folder, filename.replace("/", "_"))
                self.download_file(storage_client, blob.bucket.name, blob.name, output_destination)
                downloaded_files.append(filename)
                logging.info(f"Blob {filename} downloaded to storage")

            elif new_files_only:
                logging.info(f"Blob {blob.name} was not downloaded because it was not modified since last run")

        return downloaded_files

    @staticmethod
    def get_blobs_from_names(storage_client: StorageClient, bucket: str, files: List[str] = None) -> List:
        """
        Get blobs from bucket by name. Returns all files if no files are specified.
        Args:
            storage_client:
            bucket:
            files:

        Returns:

        """
        blobs = []
        if not files:
            logging.info(f"Files are not defined. All files from the bucket {bucket} will be downloaded.")

        for blob in storage_client.list_blobs(bucket):
            if blob.name in files:
                blobs.append(blob)

            elif not files and not blob.name.endswith("/"):
                # add all blobs if files are not defined
                blobs.append(blob)

        return blobs

    @staticmethod
    def download_file(storage_client, bucket_name, file_name, output_destination):
        try:
            return storage_client.download_blob(bucket_name, file_name, output_destination)
        except GoogleAuthError as google_error:
            raise UserException(f"Download failed after retries due to : {google_error}")
        except NotFound as not_found:
            raise UserException(f"File {file_name} could not be found in bucket") from not_found

    def _create_manifests(self, downloaded_files, tags, permanent) -> None:

        tags = tags.split(",")

        if permanent:
            logging.info("Downloaded files will be stored as permanent files.")

        for filename in downloaded_files:
            file_def = self.create_out_file_definition(filename, tags=tags, is_permanent=permanent)
            self.write_manifest(file_def)

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

        result_buckets = [SelectElement(value=bucket) for bucket in buckets_list]
        return result_buckets

    @sync_action('list_files')
    def list_files(self):
        params = self.configuration.parameters
        service_account_json = params.get(KEY_SERVICE_ACCOUNT)

        parent_bucket = params.get("settings", {}).get("bucket_name_array", [None])

        try:
            service_account_json_key = KeyCredentials(service_account_json).key
            storage_client = StorageClient(service_account_json_key=service_account_json_key)

            blobs = []

            for blob in storage_client.list_blobs(parent_bucket[0]):
                if not blob.name.endswith("/"):
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
