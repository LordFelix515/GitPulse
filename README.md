# ⚡ GitPulse

A smart Windows CLI utility that automatically verifies and synchronizes all your GitHub repositories (both Public and Private) every time you boot your computer. It performs automatic `git pull` updates on local repositories, detects new remote repositories, offers an interactive `dwnignore` download/ignore prompt, and safely protects local `.env` configuration files across updates.

---

## ✨ Key Features

1. **Automatic Synchronization of Local Repositories:**
   - Scans and compares all repositories owned by your GitHub account against your local directory.
   - Fetches upstream tracking branches (`git fetch origin`).
   - Pulls updates automatically (`git pull --ff-only` / `git pull`) when remote is ahead.
   - Detects dirty / uncommitted local changes and avoids conflicts by alerting you instead of overwriting.

2. **Smart `.env` File Protection (`env_guard`):**
   - Scans `.gitignore` and detects all `.env`, `.env.*` (e.g. `.env.local`, `.env.production`), and `*.env` files across projects.
   - Securely creates an in-memory byte backup before `git pull` runs.
   - Fully restores all `.env` files into their exact paths immediately after updates complete.
   - Your local environment secrets, ports, and database credentials remain intact and working without interruption.

3. **Missing Repositories & `dwnignore` Filtering:**
   - Detects newly created repositories on GitHub that do not yet exist on your machine.
   - Automatically skips repositories already listed in `dwnignore.txt`.
   - Prompts you with an interactive, numbered list for any un-ignored new repositories (`[1]`, `[2]`, `[3]`):
     - `1 3` or `1`: Clones only the selected repositories to your local directory.
     - `1 ignore` or `1 3 ignore`: Appends the selected repositories to `dwnignore.txt` (will not download and will not prompt again).
     - `all`: Clones all listed repositories.
     - `all ignore`: Adds all listed repositories to `dwnignore.txt`.
     - `Enter`: Skips for this session (will ask again on the next startup).

4. **Windows Boot Integration:**
   - Automatically launches in a console window when Windows boots up.
   - Handles network readiness delays with auto-retry.
   - Features a graceful countdown before closing.

5. **Full Private & Public Repository Support:**
   - Uses GitHub Personal Access Tokens (Classic or Fine-grained) to seamlessly access and clone private repositories without interactive credential prompts.

---

## 🚀 Quick Start

### 1. Requirements & Dependencies

Ensure you have Python 3.9+ and Git installed and available on your system `PATH`. Install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Configuration Setup

Run the interactive setup wizard:
```bash
python gitpulse.py --setup
```
Alternatively, copy `config.example.json` to `config.json` and configure your settings manually:
```json
{
    "github_token": "ghp_YourPersonalAccessTokenHere",
    "local_repos_dir": "C:\\Users\\Administrator\\Desktop\\code",
    "auto_pull_existing": true,
    "include_forks": true,
    "include_archived": false,
    "startup_countdown_seconds": 10
}
```

---

## 🔑 GitHub Personal Access Token (PAT) Setup

### Option A: Classic Token (Recommended - Permanent / No Expiration)
1. Go to [github.com/settings/tokens](https://github.com/settings/tokens).
2. Click **Generate new token** ➔ **Generate new token (classic)**.
3. Give it a descriptive name (e.g. `GitPulse`).
4. Set **Expiration** to **No expiration**.
5. Check the **`repo`** checkbox (grants full access to public and private repositories).
6. Click **Generate token** and copy the resulting string (`ghp_...`).

### Option B: Fine-Grained Token
1. Go to [github.com/settings/tokens?type=beta](https://github.com/settings/tokens?type=beta).
2. Click **Generate new token**.
3. Under **Repository access**, select **All repositories**.
4. Under **Permissions** ➔ **+ Add permissions**:
   - Choose **Contents** with **Read and write** (or **Read-only**) access.
5. Click **Generate token** and copy the resulting string (`github_pat_...`).

---

## 💻 Windows Startup Integration (Run on Boot)

### One-Click Setup:
Double-click the **`setup_startup.bat`** file in the project folder.

### Command Line:
To enable auto-run on Windows startup:
```bash
python gitpulse.py --add-startup
```

To remove GitPulse from Windows startup:
```bash
python gitpulse.py --remove-startup
```

To check current status:
```bash
python gitpulse.py --status
```

---

## 📋 Command Reference

| Command | Description |
|---|---|
| `python gitpulse.py` | Runs synchronization and prompts immediately |
| `python gitpulse.py --startup` | Runs in Windows boot mode (includes countdown before exit) |
| `python gitpulse.py --setup` | Interactively configures token and project directory |
| `python gitpulse.py --status` | Displays configuration details and Windows startup status |
| `python gitpulse.py --add-startup` | Registers GitPulse into the Windows Startup folder |
| `python gitpulse.py --remove-startup` | Unregisters GitPulse from the Windows Startup folder |
| `python gitpulse.py --list-ignored` | Lists all repositories currently in `dwnignore.txt` |
| `python gitpulse.py --unignore <REPO>` | Removes a repository from `dwnignore.txt` |

---

## 📁 Project Structure

```
GitPulse/
├── gitpulse.py                  # Main CLI application
├── config.py                    # Configuration manager
├── config.example.json          # Example configuration template
├── github_client.py             # GitHub REST API client (PAT authentication)
├── git_manager.py               # Local Git engine (fetch, pull, clone, dirty check)
├── env_guard.py                 # .env backup & restoration protector
├── ignore_manager.py            # dwnignore manager (reading & writing dwnignore.txt)
├── startup_manager.py           # Windows Startup folder integration
├── dwnignore.txt                # Repository ignore list
├── run.bat                      # Convenient double-click launcher
├── setup_startup.bat            # One-click Windows startup installer
├── ASD_STE100_PROJE_DOKUMANI.md # ASD-STE100 technical documentation
├── requirements.txt             # Python package dependencies
└── README.md                    # English documentation
```
