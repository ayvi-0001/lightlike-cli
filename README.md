<!-- markdownlint-disable MD033 MD046 -->

# Lightlike-CLI

![GitHub Release](https://img.shields.io/github/v/release/ayvi-0001/lightlike-cli?display_name=release&style=social&label=Latest%20Release)&nbsp;&nbsp;
![GitHub commits since latest release](https://img.shields.io/github/commits-since/ayvi-0001/lightlike-cli/latest?style=social)&nbsp;&nbsp;
![GitHub last commit](https://img.shields.io/github/last-commit/ayvi-0001/lightlike-cli?style=social)&nbsp;&nbsp;

A time-tracking REPL, using [Google BigQuery](https://cloud.google.com/bigquery?hl=en) as a backend.

![timer_run](/docs/assets/gifs/timer_run.gif)

For an overview of features, See [Features](#features).

For steps on installation & setup, See [Installation & Setup](#installation--setup).

For a full list of commands, see the [Command Guide](https://github.com/ayvi-0001/lightlike-cli/blob/main/docs/command_guide.md).

---

## Features

- **Aliased commands & Auto Completion.**
  
  The primary goal of this tool is to make logging hours as fast as possible.
  All commands are aliased - as long as it is unique, you can type the shortest prefix down to a single character to call that command.
  All options have a short flag and relevant autocompletions if applicable.
  Previously entered notes autocomplete if their respective projects are selected as an option.

  ```sh
  $ timer run
  $ t ru
  # no options starts a new time entry under "no-project"
  
  $ timer run --project lightlike-cli --note "readme" --start -1hr --billable False
  $ t ru -plightlike-cli -n"readme" -s-1hr -b0
  ```

- **Concurrent timers.**

  You can have multiple time entries running at once, pausing and resuming as needed.

  ![feature_concurrent_time_entries](/docs/assets/gifs/feature_concurrent_time_entries.gif)

- **Export timesheet summaries.**

  Export a timesheet summary as an `svg`/`csv`/`json`.

  ![feature_summary](/docs/assets/gifs/feature_summary.gif)

- **BigQuery Shell.**

  Write directly to BigQuery <span style="color:grey">(***Note**: This is a very minimal feature shell, as it's not main focus of this tool*)</span>.

  ![feature_bq_shell](/docs/assets/gifs/feature_bq_shell.gif)

- **Backup/restore snapshots.**

  Create and restore table snapshots using the `bq snapshot` command group.

- **System commands.**

  Any command not recognized by this cli will get passed to the shell.\
  Configure what shell is used with command `app:config:set:general:shell`.

  They can also be passed by typing the command and pressing `:!` or `esc`+`enter`,\
  or press `meta`+`shift`+`1` to enable a system prompt.
  
  `:c{1 | 2 | 3}` to add/remove completions from the global completer. `1`=commands, `2`=history, `3`=path

  Path autocompletion is automatic for `cd`.
  
  ![feature_system_commands](/docs/assets/gifs/feature_system_commands.gif)

---

## Installation & Setup

> [!IMPORTANT]  
> This CLI requires a connection to BigQuery. This can be either determined from the environment, or through a service account key.
>
> If the selected option is the latter, the service account key is encrypted using a user-provided password to avoid keeping a plain-text file on the local machine.
>
> Support for a local version is planned long-term.
>
> This package is not currently hosted on PyPI. It may be uploaded in the future.

---

> [!NOTE]  
> These examples are creating a virtual environment in the user's home directory called `lightlike_cli`.\
> This is optional but recommended. Update the target directories as needed.

---

### Linux

```sh
cd ~
virtualenv lightlike_cli
source lightlike_cli/bin/activate

pip install "lightlike @ git+https://github.com/ayvi-0001/lightlike-cli@v0.9.1"
```

### Git Bash/Cygwin on Windows

```sh
cd ~
virtualenv lightlike_cli
source lightlike_cli/Scripts/activate

pip install "lightlike @ git+https://github.com/ayvi-0001/lightlike-cli@v0.9.1"
```

### Windows

```sh
cd %USERPROFILE%
virtualenv lightlike_cli
lightlike_cli\Scripts\activate

pip install "lightlike @ git+https://github.com/ayvi-0001/lightlike-cli@v0.9.1"
```

As long as you are in the virutal environment, you should now be able to start the REPL by typing the command below:

```sh
lightlike
```

#### *Optional*: Create a symbolic link on `$PATH`

This step will only work if you're on Linux, or using Git Bash/Cygwin on Windows.\
The `mklink` command in Command Prompt will not work to create a symbolic link to an executable.

### Symbolic Link - Linux

```sh
cd /usr/local/bin
sudo ln -s ~/lightlike_cli/bin/lightlike
```

### Symbolic Link - Git Bash/Cygwin

```sh
cd ~/Appdata/Local/Programs/Python/Python311/Scripts
ln -s ~/lightlike_cli/Scripts/lightlike.exe
```

After running the commands above, you should be able to start the CLI using the command `$ lightlike` from anywhere, without needing to activate the virtual environment first.

There is a short initial setup the first time the CLI runs to configure default settings and set up authorization. This includes setting up the default timezone, and running scripts to build the required procedures/tables in BigQuery.

---

## Issues

This tool is not 100% complete and you may encounter bugs.
It's recommended to keep frequent backups of your time entries (primarily why the snapshot commands were added).

Please feel free to open an issue if you encounter any. If any uncaught exceptions raise, a traceback will save in the app directory and you'll see a message similar to the one below:

![error_logs](/docs/assets/png/error_logs.png)

If there is any loss of data without having created a recent snapshot, there are methods to recover it.

If the table has not been dropped, you can query historical data by using the `FOR SYSTEM_TIME AS OF` clause.

```sql
SELECT
  *
FROM
  `lightlike_cli.timesheet`
FOR SYSTEM_TIME AS OF
  CURRENT_TIMESTAMP - INTERVAL 12 HOUR;
```

If the table has been dropped, you can recover it from any point in time within the fail-safe period of the last 7 days using the `bq` command line tool.
Use the `cp` command, with the unix microseconds of the snapshot time appended to the base table name.

```sh
bq cp lightlike_cli.timesheet@1718174353373181 lightlike_cli.timesheet
```

---
