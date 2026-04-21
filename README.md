# CarbonCraft

> Interactive 3D molecular builder for hydrocarbon derivatives, powered by Ursina, RDKit, and PubChem.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Pre--release-orange)]

This project is open source and currently in pre-release.

## Overview

CarbonCraft is a visual molecule builder that lets you assemble structures in a live 3D scene, inspect atom and bond behavior, and generate chemically meaningful output such as SMILES and IUPAC names.

## Highlights

- Drag atoms onto existing atoms to grow a molecule
- Click bonds to cycle bond order
- Generate SMILES from the current structure
- Fetch IUPAC names from PubChem when online
- Render atoms and bonds in a stylized 3D interface

## Pre-Release Notes

- Controls, visuals, and behavior may change before a stable release
- Some molecules may fail sanitization or 3D embedding depending on valency and geometry constraints
- Error handling and test coverage are still evolving

## Download

### Clone with Git

```bash
git clone https://github.com/<your-org-or-user>/CarbonCraft.git
cd CarbonCraft
```

### Download ZIP

1. Open this repository on GitHub.
2. Click **Code** > **Download ZIP**.
3. Extract the archive.
4. Open the extracted folder in your terminal.

## Run the App

### Prerequisites

- Python 3.10+ (3.11 recommended)
- `pip`

### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

If launch is successful, a window titled **CarbonCraft** should appear.

## Development Setup

1. Fork the repository on GitHub.
2. Clone your fork locally.
3. Create and activate a virtual environment.
4. Install dependencies from [requirements.txt](requirements.txt).
5. Run the app with `python main.py`.

## Contributing

Contributions are welcome.

### Workflow

1. Create a branch from `main`.

```bash
git checkout -b feature/short-description
```

2. Make focused changes. One feature or fix per pull request is preferred.
3. Verify the app still runs.

```bash
python main.py
```

4. Include or update tests where practical.
5. Commit with a clear message.

```bash
git commit -m "feat: add <short feature description>"
```

6. Push your branch and open a pull request against `main`.

### Pull Request Checklist

- Code runs locally without errors
- Changes are scoped and documented
- UI changes include screenshots when relevant
- README or docs are updated when behavior changes

## Reporting Issues

Please open a GitHub issue and include:

- Operating system
- Python version
- Full error message or traceback
- Steps to reproduce
- Screenshot or short recording if the issue is visual

## Packaging (Windows executable via PyInstaller)

You can build a Windows executable using PyInstaller. This repository includes helper scripts in `scripts/` to run the exact command we use for packaging.

PowerShell

Open PowerShell in the repository root and run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force  # only if scripts are blocked
.\scripts\build_pyinstaller.ps1
```

Command Prompt (cmd)

Open a Command Prompt in the repository root and run:

```cmd
scripts\build_pyinstaller.bat
```

Notes and troubleshooting

- If PowerShell refuses to run scripts, setting the `CurrentUser` policy to `RemoteSigned` (as shown above) is a common, user-scoped solution.
- If PyInstaller fails to include a dependency at runtime, add it to the `--hidden-import` list in the build scripts.
- After a successful build, the executable will be under the `dist\CarbonCraft` folder.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for the full text.
