#!/usr/bin/env python3
"""
Script to comment out duplicate endpoints in main.py that have been migrated to routers.
This creates a backup before making changes.
"""

import re
import shutil
from pathlib import Path
from datetime import datetime

MAIN_PY = Path(__file__).parent.parent / "main.py"

# Patterns for endpoints that exist in routers
DUPLICATE_PATTERNS = [
    # Geofence router
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/geofence/',
    # Cost router
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/cost/per-mile',
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/cost/speed-impact',
    # Utilization router
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/utilization/',
    # Gamification router
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/gamification/',
    # Maintenance router (v3 and v5 endpoints)
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/maintenance/fleet-health',
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/maintenance/truck/',
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/v3/',
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/v5/',
    # Dashboard router (widgets, layout, and widget management)
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/dashboard/widgets',
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/dashboard/layout',
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/dashboard/widget/',
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/user/preferences',
    # Reports router
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/reports/schedule',
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/reports/generate',
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/reports/run',
    # GPS router
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/gps/',
    # Notifications router (all notification endpoints)
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/notifications',
    # Engine Health router (all engine-health endpoints)
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/engine-health/',
    # Export router
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/export/fleet-report',
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/export/refuels',
    # Predictions router (analytics endpoints)
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/analytics/next-refuel',
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/analytics/historical-comparison',
    r'@app\.(get|post|put|delete|patch)\s*\(\s*"/fuelAnalytics/api/analytics/trends',
]


def find_endpoint_blocks(lines):
    """Find all endpoint function blocks that match duplicate patterns."""
    blocks_to_comment = []
    i = 0

    # Join lines to handle multi-line decorators
    content = "\n".join(lines)

    while i < len(lines):
        line = lines[i]

        # Check if this line starts a decorator
        if line.strip().startswith("@app."):
            # Build the full decorator string (may span multiple lines)
            decorator_start = i
            decorator_lines = [line]
            j = i + 1

            # If the decorator continues (has open parenthesis without close)
            if "(" in line and ")" not in line:
                while j < len(lines) and ")" not in lines[j - 1]:
                    decorator_lines.append(lines[j])
                    if ")" in lines[j]:
                        j += 1
                        break
                    j += 1

            full_decorator = " ".join(decorator_lines)

            # Check if this decorator matches any duplicate pattern
            is_duplicate = False
            for pattern in DUPLICATE_PATTERNS:
                # Adjust pattern to match joined string
                adjusted_pattern = pattern.replace(r"\s*\(\s*", r"\s*\(\s*")
                if re.search(pattern, full_decorator, re.IGNORECASE):
                    is_duplicate = True
                    break

            if is_duplicate:
                # Found a duplicate endpoint decorator
                start_line = i
                i = j  # Move past decorator lines

                # Skip any additional decorators
                while i < len(lines) and lines[i].strip().startswith("@"):
                    i += 1

                # Now we should be at the function definition
                if i < len(lines) and (
                    lines[i].strip().startswith("async def")
                    or lines[i].strip().startswith("def")
                ):
                    # Get the indentation of the function
                    func_indent = len(lines[i]) - len(lines[i].lstrip())
                    i += 1

                    # Find where the function ends (next non-indented line or decorator)
                    while i < len(lines):
                        current_line = lines[i]
                        if current_line.strip() == "":
                            i += 1
                            continue

                        current_indent = len(current_line) - len(current_line.lstrip())

                        # If we hit a new decorator at the same or less indentation, we're done
                        if (
                            current_line.strip().startswith("@")
                            and current_indent <= func_indent
                        ):
                            break
                        # If we hit a new function/class at same or less indentation, we're done
                        if (
                            current_line.strip().startswith("def ")
                            or current_line.strip().startswith("async def ")
                            or current_line.strip().startswith("class ")
                        ) and current_indent <= func_indent:
                            break
                        # If we hit a comment at column 0, check if it's a section marker
                        if current_indent == 0 and current_line.strip().startswith("#"):
                            break

                        i += 1

                    end_line = i
                    blocks_to_comment.append((start_line, end_line))
                else:
                    i += 1
            else:
                i += 1
        else:
            i += 1

    return blocks_to_comment


def comment_blocks(lines, blocks):
    """Comment out the specified line blocks."""
    commented_lines = set()
    for start, end in blocks:
        for j in range(start, end):
            commented_lines.add(j)

    new_lines = []
    for i, line in enumerate(lines):
        if i in commented_lines:
            # Don't double-comment already commented lines
            if not line.strip().startswith("#"):
                new_lines.append("# MIGRATED_TO_ROUTER: " + line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    return new_lines


def main():
    print(f"Reading {MAIN_PY}...")

    with open(MAIN_PY, "r") as f:
        content = f.read()
        lines = content.split("\n")

    print(f"Total lines: {len(lines)}")

    # Find blocks to comment
    blocks = find_endpoint_blocks(lines)
    print(f"Found {len(blocks)} endpoint blocks to comment out")

    if not blocks:
        print("No duplicate endpoints found!")
        return

    # Show what will be commented
    print("\nEndpoints to be commented:")
    for start, end in blocks:
        # Find the decorator line for display
        for j in range(start, min(start + 5, end)):
            if "@app." in lines[j]:
                print(f"  Line {start+1}-{end}: {lines[j].strip()[:70]}...")
                break

    # Create backup
    backup_path = MAIN_PY.with_suffix(
        f'.py.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    )
    shutil.copy(MAIN_PY, backup_path)
    print(f"\nBackup created: {backup_path}")

    # Comment out the blocks
    new_lines = comment_blocks(lines, blocks)

    # Write the modified file
    with open(MAIN_PY, "w") as f:
        f.write("\n".join(new_lines))

    # Count lines commented
    total_commented = sum(end - start for start, end in blocks)
    print(
        f"\n✅ Commented out {total_commented} lines across {len(blocks)} endpoint functions"
    )
    print(f"✅ Modified {MAIN_PY}")


if __name__ == "__main__":
    main()
