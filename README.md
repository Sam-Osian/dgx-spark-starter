# Local AI on your DGX Spark

Chat with local Gemma models, then let them search notes and explore CSVs.
Everything runs on the Spark. Use its terminal and browser for these steps.
Allow about 40 GB of free space. Setup installs Docker too.

## 1. Install and start

```bash
# Install Git if needed
sudo apt-get update && sudo apt-get install -y git

# Download the project and enter its folder
git clone https://github.com/Sam-Osian/dgx-spark-starter.git
cd dgx-spark-starter

# Install Docker + Compose, Ollama, Gemma 4 E4B/26B, uv, ARM64 VS Code,
# and Python 3.12 with Pydantic AI
bash scripts/setup.sh

# Download/start Open WebUI and prepare the example notes and CSV
bash scripts/start-webui.sh
```

## 2. Open the chat

Open **http://localhost:8080** in your browser. First startup may take a minute.
Create your local account, then select **gemma4:26b** from the model dropdown.
You can now chat with the model.

## 3. Enable the example tools (should only need to do once)

1. Open **Workspace → Tools → Import Tools**.
2. Select **examples/openwebui-tools.json** inside the project folder and confirm the import.
3. Return to chat. Open **+ → Tools** and enable **Spark Workspace** for that chat.

This lets the model search/read local notes and call Python to analyse CSVs.
Enable **Spark Workspace** in each new chat where you want to use those tools.

## 4. Try it, then add your own files

Ask:

> Search my notes for latency. Which file mentions it?

> Inspect results.csv and calculate summary statistics for latency_seconds.

(The CSV has a mean latency of **1.6 seconds** and one
missing value, so you can check that the calculation worked)

Put your own **.txt**, **.md**, or **.csv** files in the project’s **workspace/**
folder, then ask about them by name. These tools only read files; they do not
change them. Your workspace files are excluded from Git. No restart is needed
when you add files.

## Quick intro to uv

**uv manages Python and its packages for this project.** 

`uv` is an infinitely better way of organising dependencies. It completely replaces `pip`. Unlike `pip` and `conda`, it's written entirely in Rust (which is very low level, which is what makes it ultra fast).

It keeps the project’s packages in its own `.venv` folder, separate from
other Python projects. With `uv run`, you don’t need to activate that folder manually.

Run these commands from the project folder:

| Command                             | What it does                                                              |
| ----------------------------------- | ------------------------------------------------------------------------- |
| `uv sync --locked`                | Installs the exact package versions saved for this project.               |
| `uv run --locked python agent.py` | Runs the agent with the project’s Python and packages.                   |
| `uv add pandas`                   | Example: adds pandas when you want to write your own data-analysis tools. |
| `uv remove pandas`                | Removes that package from the project’s dependencies.                    |

`pyproject.toml` lists the packages the project needs. `uv.lock` records their
exact versions so another machine can install the same set. `uv add` and
`uv remove` update both files for you. [More about uv](https://docs.astral.sh/uv/guides/projects/).
