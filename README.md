# DGX Spark local LLM starter

Ollama, Gemma 4 E4B and 26B, uv, ARM64 VS Code, and Pydantic AI examples.
Run these commands on the Spark as your normal user. Allow about 40 GB of free space.

## Install

```bash
# Install Git if it isn't already installed.
sudo apt-get update && sudo apt-get install -y git

# Download the project and open its folder.
git clone https://github.com/Sam-Osian/dgx-spark-starter.git
cd dgx-spark-starter

# Install the software, set up Python, and download both Gemma models.
bash scripts/setup.sh

# Make uv available in this terminal after installation.
export PATH="$HOME/.local/bin:$PATH"

# Check the installation.
bash scripts/doctor.sh

# Open the project in VS Code. Accept its recommended Python extensions.
code .
```

## Try the models

```bash
# Start an interactive chat. Type /bye to exit.
ollama run gemma4:e4b

# Run a prompt through Pydantic AI using the smaller model.
uv run --locked python examples/local_agent.py chat "Suggest three local LLM prototypes."

# Run the same prompt using the larger model.
uv run --locked python examples/local_agent.py chat "Suggest three local LLM prototypes." --model gemma4:26b

# Turn text into a structured JSON project brief.
uv run --locked python examples/local_agent.py extract "Build a meeting-note assistant. Collect sample notes, then evaluate action-item extraction. The success metric is undecided."

# Let the agent call a Python tool and use its result in an answer.
uv run --locked python examples/local_agent.py tools "Use your tool to estimate how many minutes a 17 GB model takes to download at 100 Mbps."
```

## Update

```bash
# Download repository updates.
git pull

# Install the Python dependencies specified by the updated lockfile.
uv sync --locked
```

## Useful extras

```bash
# Install uv and set up Python only, without system installs or model downloads.
bash scripts/setup.sh --python-only

# Run setup without installing VS Code, e.g. when using Remote SSH.
bash scripts/setup.sh --skip-vscode

# List downloaded models.
ollama list

# Show loaded models and whether they are running on the GPU.
ollama ps
```
