# Google Cloud Storage Data Source

This component enables you to download files from Google Cloud Storage into Keboola and apply processors. 

**Table of contents:**  
  
[TOC]

## Authorization
Authorization is done via a Google service account. Create an account with permission to list buckets and files and to read files. You can use Storage Admin
access for this data source. After creating the service account, download the JSON key and copy and paste it into the authorization section in the configuration.

## Row configuration
Each row can be configured to download any number of files from one Google Cloud Storage bucket.
There are two ways to select files:
- Using a file path, including [wildcards](https://docs.python.org/3/library/fnmatch.html).
  - Example: `bucket/2023-?/*.csv` or `bucket/*/*.xls`
  - **Note:** The wildcard is not supported in the bucket name.

- Selecting a bucket and files manually.
  1) The configuration requires loading available buckets and selecting one.
  2) After saving, it enables listing and selecting files within the chosen bucket.

For each row, you can define storage tags that will be used for all output files of the given row. Also, the downloaded files can be stored in Storage permanently instead of the default 14-day retention.

Each row can have processors applied to the output.
Each file is downloaded to the files directory in data, so a move processor must be applied to send it to a table.

## Applying processors
To download a CSV file to a table, apply the following processors:

```json
{
  "before": [],
  "after": [
    {
      "definition": {
        "component": "keboola.processor-move-files"
      },
      "parameters": {
        "direction": "tables",
        "addCsvSuffix": false,
        "folder": "support-test"
      }
    },
    {
      "definition": {
        "component": "keboola.processor-create-manifest"
      },
      "parameters": {
        "columns_from": "header"
      }
    },
    {
      "definition": {
        "component": "keboola.processor-skip-lines"
      },
      "parameters": {
        "lines": 1
      }
    }
  ]
}
```

To download XLS or XLSX files and save them to tables, apply the following processors: 

```json
{
  "before": [],
  "after": [
    {
      "definition": {
        "component": "jakub-bartel.processor-xls2csv"
      }
    },
    {
      "definition": {
        "component": "keboola.processor-move-files"
      },
      "parameters": {
        "direction": "tables"
      }
    },
    {
      "definition": {
        "component": "keboola.processor-create-manifest"
      },
      "parameters": {
        "columns_from": "header"
      }
    }
  ]
}
```