#!/usr/bin/env python3
"""
FIX P1: Remover Hardcoded Credentials
Script para automatizar el reemplazo de passwords hardcoded por os.getenv

Ejecutar desde la raíz del proyecto:
    python scripts/remove_hardcoded_credentials.py
"""

import os
import re
from pathlib import Path
from typing import List, Tuple

# Patrones de passwords hardcoded a buscar
HARDCODED_PATTERNS = [
    (r'password\s*=\s*["\']FuelCopilot2025!["\']', 'password=os.getenv("DB_PASSWORD")'),
    (r'password\s*=\s*["\']Tomas2025["\']', 'password=os.getenv("WIALON_MYSQL_PASSWORD")'),
]

# Archivos a excluir
EXCLUDE_PATTERNS = [
    'venv/', '__pycache__/', '.git/', 
    'scripts/remove_hardcoded_credentials.py',  # Este mismo script
    'MANUAL_AUDITORIA_COMPLETO.md',  # Documentación
    'CONFIDENCE_HELPERS_FOR_FRONTEND.ts',
]


def should_process_file(file_path: Path) -> bool:
    """Verifica si el archivo debe ser procesado"""
    file_str = str(file_path)
    
    # Excluir patrones
    for pattern in EXCLUDE_PATTERNS:
        if pattern in file_str:
            return False
    
    # Solo archivos .py
    return file_path.suffix == '.py'


def fix_file(file_path: Path) -> Tuple[bool, int]:
    """
    Reemplaza passwords hardcoded en un archivo
    
    Returns:
        (modified, num_replacements)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Error leyendo {file_path}: {e}")
        return False, 0
    
    original_content = content
    total_replacements = 0
    
    # Aplicar cada patrón
    for pattern, replacement in HARDCODED_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
            total_replacements += len(matches)
    
    # Si hubo cambios, escribir y asegurar import os
    if content != original_content:
        # Asegurar que tiene import os
        if 'import os' not in content and 'from os import' not in content:
            # Insertar después del docstring o al inicio
            lines = content.split('\n')
            insert_idx = 0
            
            # Buscar fin del docstring
            in_docstring = False
            for i, line in enumerate(lines):
                if '"""' in line or "'''" in line:
                    if not in_docstring:
                        in_docstring = True
                    else:
                        insert_idx = i + 1
                        break
            
            lines.insert(insert_idx, 'import os')
            content = '\n'.join(lines)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, total_replacements
        except Exception as e:
            print(f"❌ Error escribiendo {file_path}: {e}")
            return False, 0
    
    return False, 0


def main():
    """Proceso principal"""
    print("=" * 80)
    print("🔒 FIX P1: Removiendo Hardcoded Credentials")
    print("=" * 80)
    
    root = Path('.')
    python_files = list(root.rglob('*.py'))
    
    files_modified = 0
    total_replacements = 0
    
    for file_path in python_files:
        if not should_process_file(file_path):
            continue
        
        modified, num_replacements = fix_file(file_path)
        
        if modified:
            files_modified += 1
            total_replacements += num_replacements
            print(f"✅ {file_path}: {num_replacements} reemplazos")
    
    print("\n" + "=" * 80)
    print(f"📊 RESUMEN:")
    print(f"   Archivos modificados: {files_modified}")
    print(f"   Total de reemplazos: {total_replacements}")
    print("=" * 80)
    
    if files_modified > 0:
        print("\n⚠️  IMPORTANTE: Configurar variables de entorno:")
        print("   export DB_password=os.getenv("DB_PASSWORD")")
        print("   export WIALON_MYSQL_password=os.getenv("WIALON_MYSQL_PASSWORD")")
        print("\n   O añadir a .env:")
        print("   DB_PASSWORD=FuelCopilot2025!")
        print("   WIALON_MYSQL_PASSWORD=Tomas2025")


if __name__ == '__main__':
    main()
