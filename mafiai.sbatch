#!/bin/bash
#SBATCH -J mafia-dev
#SBATCH -p debug-gpu
#SBATCH --gres=gpu:1
#SBATCH -t 00:15:00
#SBATCH -o slurm-%j.out
#SBATCH -e slurm-%j.err

set -euo pipefail

echo "Node: $(hostname)"
echo "Time: $(date)"

module load apptainer

# Your python venv
source "$HOME/.venv/bin/activate" 2>/dev/null || true

# Ollama model cache (persist across jobs)
export OLLAMA_MODELS="$PWD/ollama_models"
mkdir -p "$OLLAMA_MODELS"

# Run settings (bounded!)
export OLLAMA_HOST_HTTP=http://127.0.0.1:11434
export OLLAMA_MODEL=llama3.2:1b
export OLLAMA_TIMEOUT_S=60
export MAX_TURNS=3
export DISCUSSION_ROUNDS=1
export PLAYER_COUNT=7
export BOUNDARY=sloppy  # strict, sloppy, or broken
export SEED=42

# Start Ollama
apptainer exec --nv \
  --bind "$OLLAMA_MODELS:/root/.ollama" \
  ollama.sif \
  ollama serve > ollama.log 2>&1 &

# Wait for server
for i in {1..30}; do
  if curl -s http://127.0.0.1:11434/api/tags >/dev/null; then
    echo "Ollama is up"
    break
  fi
  sleep 1
done

# Pull model (will be fast if already cached in ollama_models/)
echo "Pulling model: $OLLAMA_MODEL"
apptainer exec --nv \
  --bind "$OLLAMA_MODELS:/root/.ollama" \
  ollama.sif \
  ollama pull "$OLLAMA_MODEL"

# Run your python
"$HOME/.venv/bin/python" mafiai_hpc.py

echo "Done: $(date)"

