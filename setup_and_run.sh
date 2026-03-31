#!/bin/bash
set -e

# Source conda so we can activate
source $(conda info --base)/etc/profile.d/conda.sh

# Create and activate environment
echo "Creating conda env rag_env..."
conda create -n rag_env python=3.10 -y
conda activate rag_env

# Install dependencies
echo "Installing dependencies..."
pip install sentence-transformers faiss-cpu numpy tqdm

# Step 0 - Upgrade
echo "Upgrading chunks..."
python upgrade_chunks.py

# Step 4,5,6 - Build index
echo "Building index..."
python build_index.py

# Step 8 - Test retrieval
echo "Testing retrieval..."
python test_retrieval.py
