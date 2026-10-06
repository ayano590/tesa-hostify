# Running the service on Windows

For unattended operation on a Windows PC, use Task Scheduler to launch Uvicorn at startup. This lets the service run without an open terminal and can restart it if the process exits.

## Create the task

1. Open **Task Scheduler** and choose **Create Task**.
2. On **General**, give the task a name such as `Tesa Hostify`. Select the Windows account that can read the project and its `.env` file. Choose **Run whether user is logged on or not** if it should run without an interactive desktop session.
3. On **Triggers**, add **At startup**.
4. On **Actions**, add **Start a program**:
   - **Program/script:** the full path to the project's Python executable, for example `C:\path\to\tesa-hostify\venv\Scripts\python.exe`.
   - **Add arguments:** `-m uvicorn app.main:app --host 0.0.0.0 --port 8000`
   - **Start in:** the repository root, for example `C:\path\to\tesa-hostify`.
5. On **Settings**, enable **Restart the task if it fails** and choose a short restart delay. Disable **Stop the task if it runs longer than** so Windows does not terminate this long-running process.
6. Save the task and provide the selected account's password if Windows asks for it. Start the task once manually and check **Last Run Result** in Task Scheduler.

The `Start in` directory matters: the service uses package imports such as `app.config`, so it must be the repository root. The `.env` file should also be in the repository root, next to `README.md`. The relative paths for `hotel.db` and `app.log` place both files there as well. The account running the task must have access to the project directory, `.env`, and network.

Set up the Python environment and install `requirements.txt` before creating the task. Keep the `.env` file out of version control and ensure it is readable by the account running the task. If the machine sleeps or shuts down, the service will not run until Windows starts again.

## Logs

The application writes logs to `app.log` in the working directory and also writes to standard output. With Task Scheduler there may be no visible terminal, so use the file for persistent troubleshooting. The file handler keeps the active log plus four rotated files, with a 2 MiB rotation threshold per file; the oldest rotated file is discarded as new logs are rotated. This keeps application log storage to about 10 MiB.

To run interactively instead, open a terminal in the repository root and run:

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Closing that terminal stops the interactive process. Its console output is separate from the rotating `app.log`.
