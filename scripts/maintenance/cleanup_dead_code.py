#!/usr/bin/env python3
"""
cleanup_dead_code.py - Eliminar código muerto de main.py
═══════════════════════════════════════════════════════════════════════════════

AUDITORÍA DIC 25, 2025:
- main.py tiene 7,764 líneas
- 3,172 líneas (41%) están comentadas con 'MIGRATED_TO_ROUTER'

USO:
    python cleanup_dead_code.py main.py --analyze
    python cleanup_dead_code.py main.py --clean
"""

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


def analyze_file(filepath: Path) -> dict:
    """Analizar archivo para código muerto"""
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    stats = {
        "total_lines": len(lines),
        "migrated_lines": 0,
        "dead_blocks": [],
    }

    migrated_pattern = re.compile(r"#\s*MIGRATED_TO_ROUTER", re.IGNORECASE)

    in_block = False
    block_start = None
    block_size = 0

    for i, line in enumerate(lines):
        if migrated_pattern.search(line):
            if not in_block:
                in_block = True
                block_start = i
                block_size = 0
            stats["migrated_lines"] += 1
            block_size += 1
        elif in_block and (line.strip().startswith("#") or not line.strip()):
            block_size += 1
        else:
            if in_block and block_size > 5:
                stats["dead_blocks"].append(
                    {"start": block_start, "end": i - 1, "size": block_size}
                )
            in_block = False
            block_size = 0

    return stats


def clean_file(filepath: Path) -> tuple:
    """Limpiar código muerto"""
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    migrated_pattern = re.compile(r"#\s*MIGRATED_TO_ROUTER", re.IGNORECASE)

    cleaned_lines = []
    removed = 0
    i = 0

    while i < len(lines):
        line = lines[i]

        if migrated_pattern.search(line):
            # Marcar inicio de bloque muerto
            block_start = i

            # Consumir todo el bloque
            while i < len(lines) and (
                migrated_pattern.search(lines[i])
                or (lines[i].strip().startswith("#") and "MIGRATED" in lines[i])
                or not lines[i].strip()
            ):
                removed += 1
                i += 1

            # Agregar marcador
            if removed > 10:
                cleaned_lines.append(
                    f"# [CLEANED {datetime.now().strftime('%Y-%m-%d')}] Removed {removed} lines of migrated code"
                )
                cleaned_lines.append("")
        else:
            cleaned_lines.append(line)
            i += 1

    return removed, "\n".join(cleaned_lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Clean dead code")
    parser.add_argument("file", help="Path to file")
    parser.add_argument("--analyze", action="store_true", help="Analyze only")
    parser.add_argument("--clean", action="store_true", help="Clean file")

    args = parser.parse_args()

    filepath = Path(args.file).resolve()

    if not filepath.exists():
        print(f"❌ Archivo no encontrado: {filepath}")
        sys.exit(1)

    # Analizar
    stats = analyze_file(filepath)

    print(f"\n📊 Análisis de {filepath.name}:")
    print(f"   Total líneas:       {stats['total_lines']:,}")
    print(f"   Líneas MIGRATED:    {stats['migrated_lines']:,}")
    print(f"   Bloques muertos:    {len(stats['dead_blocks'])}")

    pct = (
        (stats["migrated_lines"] / stats["total_lines"]) * 100
        if stats["total_lines"] > 0
        else 0
    )
    print(f"\n⚠️  {pct:.1f}% del archivo es código muerto!")

    # Limpiar
    if args.clean:
        print(f"\n⚙️  Limpiando {filepath.name}...")

        # Backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = filepath.with_suffix(f".py.backup_{timestamp}")
        shutil.copy2(filepath, backup)
        print(f"   📦 Backup: {backup.name}")

        removed, cleaned = clean_file(filepath)
        filepath.write_text(cleaned, encoding="utf-8")

        new_lines = len(cleaned.split("\n"))
        reduction = ((stats["total_lines"] - new_lines) / stats["total_lines"]) * 100

        print(f"\n✅ Limpieza completada!")
        print(f"   Líneas removidas:   {stats['total_lines'] - new_lines:,}")
        print(f"   Tamaño nuevo:       {new_lines:,} líneas")
        print(f"   Reducción:          {reduction:.1f}%")


if __name__ == "__main__":
    main()
