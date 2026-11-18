# DGX Spark local LLM starter

Set up Ollama, two Gemma models, VS Code for **Linux ARM64**, and a small
[Pydantic AI](https://pydantic.dev/docs/ai/) project on a DGX Spark.

## First install

Use a normal user account with sudo access on DGX OS (Ubuntu-based Linux ARM64).
Complete NVIDIA's initial setup and apply any recommended DGX OS updates first.
If an update requires a reboot, do that before running the installer. `nvidia-smi`
must work. Allow about **40 GB of free disk space** for the default setup and
more for optional models; download times depend on your connection.

On the Spark, open a terminal:

```bash
# If Git is missing: sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/Sam-Osian/dgx-spark-starter.git
cd dgx-spark-starter
bash scripts/setup.sh
bash scripts/doctor.sh
```

The repository is private initially. Use authenticated Git/SSH with an account
that has access (browser sign-in alone does not authenticate `git clone`), or
download and extract the repository ZIP using GitHub's website.
The owner must give their supervisor repository access before they can clone it.

The installer installs prerequisite apt packages, uses the official Ollama
installer if Ollama is missing, enables its startup service when available,
installs Microsoft's ARM64 VS Code package if `code` is missing, creates `.venv`,
and installs the hash-locked Python dependencies. It then downloads:

| Model | Purpose | Approximate model download |
| --- | --- | --- |
| `gemma4:e4b` | Smaller model for chat and structured extraction | 6.6–9.5 GB |
| `gemma4:26b` | Larger mixture-of-experts model; tool-calling demo | 16–19 GB |

These are the default quantized Ollama tags. Sizes and tag contents can change;
runtime memory also includes context and inference overhead. Start with short
prompts rather than allocating the advertised maximum context.

Run the installer **without sudo**; it asks for sudo for system steps. Existing
Ollama, VS Code, and model data are reused. It does not upgrade existing Ollama
or VS Code installations, change the firewall, or run an OS-wide upgrade.
The upstream Ollama installer is downloaded over HTTPS and run with its normal
privileges; review [that installer](https://ollama.com/install.sh) if desired.
It is only invoked after a working NVIDIA driver is detected, to avoid its
automatic missing-driver installation path.

Useful options:

```bash
bash scripts/setup.sh                    # Gemma 4 pair, including tool calling
bash scripts/setup.sh --skip-vscode      # Editor on another computer via SSH
bash scripts/setup.sh --skip-models      # Install software; download models later
bash scripts/setup.sh --skip-ollama      # Use an existing Ollama server
bash scripts/setup.sh --python-only      # Python environment only, no sudo/downloaded models
bash scripts/pull-models.sh gemma3:4b gemma3:12b  # Optional Gemma 3 comparison
bash scripts/pull-models.sh qwen3:8b             # Optional alternative tool model
```

Python-only setup requires Python 3.11+ with venv/pip available. All other setup
modes install system prerequisites and require sudo. Rerunning setup is useful
after a partial failure; it reuses downloaded model blobs.

## Try the examples

Run from the repository directory. No paid API key is needed. The examples
connect to Ollama on loopback, with no cloud provider configured.

```bash
ollama run gemma4:e4b
# Type /bye to leave the interactive chat.

.venv/bin/python examples/local_agent.py chat \
  "Suggest three small research prototypes using a local LLM."

.venv/bin/python examples/local_agent.py chat \
  "Suggest three small research prototypes using a local LLM." --model gemma4:26b

.venv/bin/python examples/local_agent.py extract \
  "We want a local assistant to turn meeting notes into action items. First collect sample notes, then evaluate extraction quality. We have not chosen a success metric."

.venv/bin/python examples/local_agent.py tools \
  "Use your tool to estimate how many minutes a 17 GB model takes to download at 100 Mbps."
```

`chat` returns text. `extract` returns a validated `ProjectBrief` JSON object.
`tools` lets Gemma 4 26B request a Python calculation, passes the result back to the
model, and prints its answer. The expected calculation is about **22.67 minutes**;
the example also prints the tool call so you can see whether it really happened.
The tool only calculates a number; it has no filesystem, shell, or network access.
Runs are limited to six model requests, with a five-minute per-request timeout.

**Gemma 4 supports native tool calling**, so no separate model family is needed
for the agent demo. If you compare with Gemma 3, its Ollama package does not
advertise native tool calling. Pydantic AI normally uses a tool call for typed
output; this extraction example explicitly uses `NativeOutput` (Ollama's
JSON-schema response format), which also works with Gemma 3. A schema-valid
result still needs evaluation for factual correctness. Gemma and Gemini are
different model families; these examples use the local Gemma weights.

For your own prototype, replace `ProjectBrief` with your task's Pydantic schema,
or add narrowly scoped Python functions to the `tools` list in
`examples/local_agent.py`. Start with read-only tools and evaluate on a small
set of examples before adding write actions.

To change defaults, set environment variables, or copy `.env.example` to `.env`
and load it explicitly with `set -a; source .env; set +a`. `.env` is not loaded
automatically and is ignored by Git. `OLLAMA_MODEL` selects the chat/extraction
model; `OLLAMA_TOOL_MODEL` selects the tools model. `--model` overrides either.

## VS Code on Spark

Spark uses an ARM64 CPU. A Linux **x64/amd64** VS Code download will not work;
choose **.deb → Arm64** on the download page. The script selects the explicit
[ARM64 stable download](https://update.code.visualstudio.com/latest/linux-deb-arm64/stable),
checks the package architecture, and enables Microsoft's apt repository for
subsequent package-manager updates. An existing VS Code install is left alone.

```bash
code .
```

Accept the recommended Python extensions in VS Code. The workspace points to
`.venv/bin/python`; use **Python: Select Interpreter** if it does not pick it up.
Extension installation is left to VS Code so it happens under the correct user
and remote/local editor session.

For a headless Spark, install VS Code on your laptop and use Microsoft's
[Remote - SSH](https://code.visualstudio.com/docs/remote/ssh) extension. Connect
to `your-user@your-spark`, open the cloned repository on the Spark, and run its
terminal commands there. This keeps both Python and Ollama on the Spark.

If you instead run Python on a laptop, first install the Python dependencies
there with `bash scripts/setup.sh --python-only`, then forward Ollama over SSH:

```bash
ssh -N -L 11435:127.0.0.1:11434 your-user@your-spark
# In another laptop terminal, from the repository:
OLLAMA_BASE_URL=http://127.0.0.1:11435/v1 \
  .venv/bin/python examples/local_agent.py chat "Hello from my laptop"
```

Leave Ollama on its default loopback binding. Its local API has no built-in
authentication; SSH forwarding avoids opening that API to the network.
`OLLAMA_BASE_URL` is for the Python examples and **includes `/v1`**. The Ollama
CLI instead uses `OLLAMA_HOST`, for example `http://127.0.0.1:11435` through the
same tunnel. Set both consistently if using model-download scripts remotely.
The examples reject non-loopback endpoints and model tags ending in `-cloud`.
Initial software/model downloads require internet access; inference uses the
chosen local model. VS Code extensions and other software have their own
network behavior.

## Troubleshooting and verification

```bash
bash scripts/doctor.sh
sudo systemctl status ollama --no-pager
sudo journalctl -u ollama -n 60 --no-pager
ollama list
ollama ps
```

Run `ollama ps` just after an example to see the loaded model's **PROCESSOR**
placement. A successful response alone does not prove GPU acceleration. An empty
list is normal when no model is loaded. Spark's unified memory may also make
`nvidia-smi` memory reporting look different from a conventional discrete GPU.

If the API is unavailable, try `sudo systemctl start ollama`. If you have a manual
installation without a service, run `ollama serve` in another terminal. If port
11434 belongs to an existing container or manually launched Ollama, reuse that
server with `--skip-ollama` instead of starting a second one.

If the model runs on CPU, first check DGX OS updates and reboot as needed, then
check Ollama's service logs and version. Upgrade an old Ollama installation using
its official Linux instructions during a suitable maintenance window. Avoid
installing generic Ubuntu CUDA/NVIDIA drivers over the Spark's supplied stack.

If you see `model not found`, pull the exact tag shown in the command. If the
tools demo says the model does not support tools, use `gemma4:26b`; a temperature
of zero does not guarantee every model will choose the correct tool. The
script reports failure if the model answers without calling the example tool.

The Python dependencies are fully pinned with hashes in `requirements.txt`.
The system packages, vendor installer, and Ollama model tags track their
upstream releases, so the entire machine setup is not bit-for-bit reproducible.
For experiments, record `ollama --version`, `ollama list` (including model IDs),
the GPU driver version, and your repository commit alongside the results.

Developer checks (no GPU, cloud credentials, or model downloads needed):

```bash
.venv/bin/python -m unittest discover -s tests -v
for script in scripts/*.sh; do bash -n "$script"; done
```

Validated on 18 November 2026 on an ARM64 Spark with Python 3.11.15 and Ollama
0.22.0: Python-only setup, dependency consistency, all 11 automated tests, and
ShellCheck passed. Live Gemma 3 27B chat/typed extraction and Gemma 4 26B tool
calling also passed against already installed models. A fresh-machine apt,
Ollama, and VS Code installation has not been run; system-install behavior was
tested with fake commands. The E4B model was not downloaded during verification.

To intentionally update Python dependencies, edit `requirements.in`, regenerate
with `uv pip compile --universal --generate-hashes requirements.in -o requirements.txt`,
then rerun setup and the tests. Runtime setup does not require uv.

## References

- [Ollama Linux installation](https://docs.ollama.com/linux)
- [Ollama hardware support](https://docs.ollama.com/gpu)
- [Gemma 3 model tags and sizes](https://ollama.com/library/gemma3)
- [Gemma 4 model tags, sizes, and tool support](https://ollama.com/library/gemma4)
- [Qwen 3 8B and tool support](https://ollama.com/library/qwen3:8b)
- [Pydantic AI with Ollama](https://pydantic.dev/docs/ai/models/ollama/)
- [Pydantic AI output modes](https://pydantic.dev/docs/ai/core-concepts/output/)
- [Microsoft's Linux installation guide](https://code.visualstudio.com/docs/setup/linux)
- [NVIDIA's Ollama/Open WebUI playbook](https://build.nvidia.com/spark/open-webui)

This kit uses native Ollama and a Python environment; NVIDIA's linked playbook
provides a separate container-based browser UI option. Model licenses remain
those of their publishers; check the relevant model's terms for your intended use.
