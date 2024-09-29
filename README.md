<!-- markdownlint-disable MD033 MD046 MD024 -->

# lightlike-cli

![GitHub Release](https://img.shields.io/github/v/release/ayvi-0001/lightlike-cli?display_name=release&style=social&label=Latest%20Release)&nbsp;&nbsp;
![GitHub commits since latest release](https://img.shields.io/github/commits-since/ayvi-0001/lightlike-cli/latest?style=social)&nbsp;&nbsp;
![GitHub last commit](https://img.shields.io/github/last-commit/ayvi-0001/lightlike-cli?style=social)&nbsp;&nbsp;

A time-tracking REPL, using [Google BigQuery](https://cloud.google.com/bigquery?hl=en) as a backend.

- [Features](#features)
- [Installation & Setup](#installation--setup)
- [Command Guide](https://github.com/ayvi-0001/lightlike-cli/blob/main/docs/command_guide.md)

![example](/docs/assets/gifs/example.gif)

---

## Features

<ins>*Addtional feature videos to be added*</ins>

- **Aliased commands & Auto Completion.**

  The primary goal of this tool is to make logging hours as fast as possible.
  All commands are aliased - as long as it is unique, you can type the shortest prefix down to a single character to call that command.
  All options have a short flag and relevant autocompletions if applicable.
  Previously entered notes autocomplete if their respective projects are selected as an option.

  ```bash
  # no options starts a new time entry under "no-project"
  $ timer run
  $ t ru

  $ timer run --project lightlike-cli --note "readme" --start 1h --billable true
  $ t ru -plightlike-cli -n"readme" -s1h -b1
  ```

- **Concurrent timers.**

  You can have multiple time entries running at once, pausing and resuming as needed.

- **Export timesheet summaries.**

  Export a timesheet summary as an `svg`/`csv`/`json`.

- **BigQuery Shell.**

  Write directly to BigQuery <span style="color:grey">(***Note**: This is a very minimal feature shell, as it's not main focus of this tool*)</span>.

- **Backup/restore snapshots.**

  Create and restore table snapshots using the `bq snapshot` command group.

- **System commands.**

  Any command not recognized by this cli will get passed to the shell.\
  Configure what shell is used with command `app:config:set:general:shell`.

  They can also be passed by typing the command and pressing `:!` or `esc`+`enter`,\
  or press `meta`+`shift`+`1` to enable a system prompt.

  `:c{1 | 2 | 3 | 4}` to add/remove completions from the global completer.\
  `1`=commands, `2`=history, `3`=path, `4`=executables

  Path autocompletion is automatic for `cd`.

---

## Installation & Setup

- This package is not currently hosted on PyPI. It may be uploaded in the future.
- Support for a local only version is planned long-term.

<br />

```bash
# Run the following command to install the latest release:
pip install "lightlike @ git+https://github.com/ayvi-0001/lightlike-cli@$TAG" # substitute TAG, e.g. TAG=v0.0.0

# Run the following command to install the latest commit:
pip install "lightlike @ git+https://github.com/ayvi-0001/lightlike-cli@main"
```

<br />

There is a short initial setup the first time the CLI runs to configure the default timezone, settings/authorization for BigQuery, and running scripts to build the required procedures/tables.

Once it's installed, start the REPL by running the command `$ lightlike`

<br />

> [!NOTE]
> This tool depends on the library [`rtoml`](https://github.com/samuelcolvin/rtoml) which is implemented in [rust](https://www.rust-lang.org/).
> When installing from your package manager , it will attempt to find the appropriate binary for your system configuration from [this list](https://pypi.org/project/rtoml/#files).
> If it's it's unable to determine this, you'll need [rust stable](https://releases.rs/) installed to compile it.
>
> If your package manager was unable to determine your system configuration but you see an appropriate binary available, you can try to install it manually:
>
> ```bash
> pip install https://files.pythonhosted.org/packages/4c/6d/48ce15a3919a5c07a19ae3c80b9fadbe1e13a5e475198143965d3de6e60b/rtoml-0.11.0-cp311-none-win_amd64.whl
> ```
>

<br />

> [!NOTE]
> This CLI requires a connection to BigQuery. You must have a [Google Cloud Project](https://developers.google.com/workspace/guides/create-project) with [billing enabled](https://cloud.google.com/billing/docs/how-to/modify-project).
> Authorization for BigQuery can come from 2 sources:
>
> - **Environment**: Application Default Credentials set using [`gcloud`](https://cloud.google.com/sdk/gcloud). [See here for information on installing the gcloud SDK](https://cloud.google.com/sdk/docs/install).
> - **Service Account Key**: [See here for information on creating service accounts](https://cloud.google.com/iam/docs/service-accounts-create). You'll need the role [Service Account Key Admin](https://cloud.google.com/iam/docs/understanding-roles#iam.serviceAccountKeyAdmin).
>   If you are authorizing using a service account key, this CLI will ask you to **provide a password** that it will use to encrypt the key. This is to avoid keeping a plain-text file of the key on the local machine.\
>   If you have `gcloud` installed, you can create a service-account and grant it the required permissions with the following script.
>
>   ```bash
>   #!/usr/bin/env bash
>
>   # @note gcloud_sdk_version '487.0.0'
>
>   PROJECT_ID=YOUR-PROJECT-ID # TODO replace with your project id
>   SERVICE_ACCOUNT_NAME=lightlike-cli
>   SERVICE_ACCOUNT_EMAIL="$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"
>   # TODO store somewhere safe, or immediately remove from the machine after starting the cli.
>   KEY_FILE=~/lightlike-credentials.json
>
>   # Create a new service account.
>   gcloud iam service-accounts create \
>       "$SERVICE_ACCOUNT_NAME" \
>       --description="https://github.com/ayvi-0001/lightlike-cli" \
>       --display-name="lightlike-cli"
>
>   # Create a new key.
>   gcloud iam service-accounts keys create "$KEY_FILE" --iam-account="$SERVICE_ACCOUNT_EMAIL"
>
>   # Add the required permissions.
>   gcloud projects add-iam-policy-binding "$PROJECT_ID" \
>       --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
>       --role=roles/bigquery.user \
>       --role=roles/bigquery.metadataViewer \
>       --condition=None
>   ```

---

## Issues

This tool is still not 100% complete. It's recommended to keep frequent backups of your time entries. Please feel free to open an issue if you encounter bugs. If any uncaught exceptions raise, a traceback will save in the app directory and you'll see a message similar to the one below:

![error_logs](/docs/assets/png/error_logs.png)

If there is any loss of data without having created a recent snapshot, and you are *within the fail-safe period of the last 7 days*, there are methods to recover it.

If the table has not been dropped, you can query historical data by using the `FOR SYSTEM_TIME AS OF` clause.

```sql
SELECT
  *
FROM
  `lightlike_cli.timesheet`
FOR SYSTEM_TIME AS OF
  CURRENT_TIMESTAMP - INTERVAL 12 HOUR;
```

If the table has been dropped, you can recover it using the `bq` gcloud component.
Use the `cp` command, with the unix milliseconds of the snapshot time appended to the base table name with the `@` symbol.

```bash
bq cp lightlike_cli.timesheet@1723306791 lightlike_cli.timesheet
```

If you have `gcloud` installed but you run into the error `bq: command not found`, try running `gcloud components install bq`.
