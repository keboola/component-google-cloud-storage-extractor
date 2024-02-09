## Authorization
Authorization is done via a Google service account. Create an account with permission to list buckets and files and to read files. You can use Storage Admin
access for this data source. After you create the service account, download the JSON key and copy and paste it into the authorization section in the configuration.

## Row configuration
Each row can be configured to download any number of files from one Google Cloud Storage bucket.

There are two ways to select files:
- Using a file path, including [wildcards](https://docs.python.org/3/library/fnmatch.html).
  - Example: `bucket/2023-?/*.csv` or `*/*.xls`

- Selecting a bucket and files manually.
  1) The configuration requires loading available buckets and selecting one.
  2) After saving, it enables the listing and selecting of files within the chosen bucket.

For each row, you can define storage tags that will be used for all output files of the given row. Also, the downloaded files can be stored in Storage permanently instead of the default 14-day retention.

Each row can have its processors applied to the output.
Each file is downloaded to the files directory in data, so a move processor must be applied to send it to a table.