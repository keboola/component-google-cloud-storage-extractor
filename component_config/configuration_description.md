## Authorization
Authorization is done via a Google Service Account. Create an account with the permission to list buckets and files, and to read files. Storage Admin
access can be used for this Extractor. After creating the service account, download the JSON key and copy and paste it into the authorization section in the configuration.

## Row configuration
Each row can be configured to download any number of files from one Google Cloud Storage bucket.
There are two ways to select files:
- by a filepath including [wildcards](https://docs.python.org/3/library/fnmatch.html)
  - for example: `bucket/2023-?/*.csv` or `*/*.xls`

- Selecting bucket and files manually.
  1) The configuration requires loading available buckets and selecting one.
  2) After saving, it enables the listing and selection of files within the chosen bucket.

In each row can be defined a storage tags used for all output files of the given row. Also the downloaded files can be stored permanently in the Storage instead of default 14 days retention.

Each row can have its own processors applied to the output.
Each file is downloaded to the files directory in data, so a move processor must be applied to send it to a table.