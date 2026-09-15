# GITBI Agent

Local GITBI agent for Windows. It connects the GITBI application to the
team's Git repositories and exposes the agent through a Pangolin tunnel
managed by Newt.

## Requirements

- Windows 10 or 11.
- Git installed and available in `PATH`.
- Python 3.12.x. The installer does not accept other major or minor versions.
- Internet access during installation to download dependencies and, if
  needed, `newt.exe`.
- Permissions to run PowerShell scripts and create a shortcut on the
  Desktop.

## Installation

1. Clone the repository and enter its folder:

   ```powershell
   git clone <REPOSITORY_URL>
   cd agent-local
   ```

2. Run the installer from PowerShell:

   ```powershell
   .\install.ps1
   ```

   The script checks for Python 3.12, creates `.venv`, installs the
   dependencies from `requirements.txt`, downloads `newt.exe` from the
   official releases, and creates the `GITBI Agent` shortcut on the Desktop.

3. **Run `newt.exe` once before starting the agent.** Open the `newt.exe`
   file located at the root of the project. When Windows Firewall asks for
   permission, allow access on the private network you use. This step
   registers the executable's authorization so the tunnel can work
   correctly. You can close the Newt window after clearing the firewall
   prompt; the agent will start it automatically.

> If Windows doesn't show the prompt, there is no need to open a port
> manually.
> If the tunnel doesn't connect, check the Windows Firewall inbound rules
> and allow `newt.exe` or `python.exe` on a private network.

## Configuration

On first launch, if `.env` doesn't exist, the agent opens the browser to
obtain the authorization configuration and saves it locally.

> **Warning:** Never commit `.env` to the repository or share its credentials.

## Usage

### Starting the agent

After configuring `.env`, start the agent one of these ways:

- Open the `GITBI Agent` shortcut on the Desktop.
- Run it manually:

  ```powershell
  .\.venv\Scripts\Activate.ps1
  python start.py
  ```

Keep the agent window open while using it. The process starts the local API
on the port configured in `AGENT_PORT` (default `8000`) and launches Newt in
the background for the tunnel.

### Stopping the agent

Close the process from Task Manager, or, with caution, run:

```powershell
taskkill /IM python.exe /F
```

> This command closes **all** running `python.exe` processes, not just the
> agent's.

## Licenses

- This project is licensed under the MIT license — see the `LICENSE` file
  for details.
- `newt.exe` is a third-party component from
  [Fossorial/Newt](https://github.com/fosrl/newt). Check the repository and
  its releases for current terms. Newt is offered under the **GNU Affero
  General Public License v3.0 (AGPLv3)**, and Fossorial also offers
  commercial terms. The copy of `newt.exe` must retain its notices and
  comply with the applicable license.
- Python dependencies have their own licenses, which should be reviewed
  before distributing a packaged application.

## Quick troubleshooting

- **Python not found:** install Python 3.12.x from
  [python.org](https://www.python.org/downloads/) and run `install.ps1`
  again.
- **`newt.exe` not found:** download it from the
  [official Newt releases](https://github.com/fosrl/newt/releases) and
  place it at the root of the project.
- **Configuration not received in the browser:** the temporary callback uses
  port `9999`. Temporarily allow `python.exe` or TCP port `9999` in the
  Windows Firewall during authorization.
- **Tunnel not connecting:** confirm `PANGOLIN_ID`, `PANGOLIN_SECRET`,
  `PANGOLIN_SERVER`, and `AGENT_PUBLIC_URL` in `.env`, and check
  `agent.log` and `newt_debug.log`.

Re-running `install.ps1` is safe: the process is idempotent and preserves
the existing configuration.
