#!/usr/bin/env python3
"""
Wrapper para executar o servidor standalone.

Execute com:
    uv run python run_server.py
    uv run python run_server.py --port 9009 --password 1234 -v
"""

import sys
from pathlib import Path

# Executa o __main__.py diretamente
if __name__ == "__main__":
    main_file = Path(__file__).parent / "custom_components" / "intelbras_amt" / "lib" / "__main__.py"
    
    # Lê e executa o arquivo diretamente
    with open(main_file) as f:
        code = compile(f.read(), main_file, 'exec')
        exec(code)
