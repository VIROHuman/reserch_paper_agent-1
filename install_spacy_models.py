#!/usr/bin/env python3
"""
Install spaCy models for reference extraction
"""
import subprocess
import sys

def install_spacy_models():
    """Install required spaCy models"""
    models = [
        "en_core_web_sm",  # Small model (faster, smaller)
        "en_core_web_trf"  # Transformer model (more accurate)
    ]
    
    for model in models:
        try:
            print(f"Installing {model}...")
            subprocess.run([sys.executable, "-m", "spacy", "download", model], check=True)
            print(f"✅ {model} installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {model}: {e}")
        except Exception as e:
            print(f"❌ Error installing {model}: {e}")

if __name__ == "__main__":
    print("Installing spaCy models for reference extraction...")
    install_spacy_models()
    print("Installation complete!")
