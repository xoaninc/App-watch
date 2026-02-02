#!/usr/bin/env python3
"""Apply shape interpolations to GTFS shapes file.

This script takes the interpolated points from shapes_interpolated.json
and creates a new shapes.txt file with the corrections applied.

Usage:
    python scripts/apply_shape_interpolations.py --input shapes.txt --output shapes_fixed.txt
    python scripts/apply_shape_interpolations.py --input shapes.txt --in-place
"""

import argparse
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

INTERPOLATIONS_PATH = Path(__file__).parent.parent / "data" / "shapes_interpolated.json"


def load_interpolations(path: Path) -> dict:
    """Load interpolated points from JSON file."""
    if not path.exists():
        logger.warning(f"Interpolations file not found: {path}")
        return {}

    with open(path, 'r') as f:
        return json.load(f)


def apply_interpolations(input_path: Path, output_path: Path, interpolations: dict):
    """Apply interpolations to shapes file."""
    # Read original file
    lines = []
    with open(input_path, 'r') as f:
        lines = f.readlines()

    # Parse header
    header = lines[0].strip()

    # Group lines by shape_id
    shapes_data = {}  # shape_id -> list of (seq, line)
    for line in lines[1:]:
        parts = line.strip().split(',')
        if len(parts) < 4:
            continue

        shape_id = parts[0].strip()
        seq = int(parts[3].strip())

        if shape_id not in shapes_data:
            shapes_data[shape_id] = []
        shapes_data[shape_id].append((seq, line.strip()))

    # Apply interpolations
    total_added = 0
    for shape_id, interp_points in interpolations.items():
        if shape_id not in shapes_data:
            logger.warning(f"Shape {shape_id} not found in input file")
            continue

        logger.info(f"Applying {len(interp_points)} interpolations to {shape_id}")

        for point in interp_points:
            # Create new line in GTFS format
            # shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence
            new_line = f"{shape_id},{point['lat']},{point['lon']},{int(point['seq'] * 1000)}"
            shapes_data[shape_id].append((point['seq'], new_line))
            total_added += 1

        # Sort by sequence
        shapes_data[shape_id].sort(key=lambda x: x[0])

    # Renumber sequences to be integers
    logger.info("Renumbering sequences...")
    for shape_id in shapes_data:
        for i, (old_seq, line) in enumerate(shapes_data[shape_id]):
            parts = line.split(',')
            parts[3] = str(i + 1)  # New sequence starting from 1
            shapes_data[shape_id][i] = (i + 1, ','.join(parts))

    # Write output
    with open(output_path, 'w') as f:
        f.write(header + '\n')
        for shape_id in sorted(shapes_data.keys()):
            for seq, line in shapes_data[shape_id]:
                f.write(line + '\n')

    logger.info(f"Added {total_added} interpolated points")
    logger.info(f"Output written to {output_path}")

    return total_added


def main():
    parser = argparse.ArgumentParser(description='Apply shape interpolations to GTFS')
    parser.add_argument('--input', '-i', type=str, required=True, help='Input shapes.txt file')
    parser.add_argument('--output', '-o', type=str, help='Output shapes.txt file')
    parser.add_argument('--in-place', action='store_true', help='Modify input file in place')
    parser.add_argument('--interpolations', type=str, help='Path to interpolations JSON')
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return

    if args.in_place:
        output_path = input_path
    elif args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_name(input_path.stem + '_fixed.txt')

    interp_path = Path(args.interpolations) if args.interpolations else INTERPOLATIONS_PATH
    interpolations = load_interpolations(interp_path)

    if not interpolations:
        logger.error("No interpolations to apply")
        return

    apply_interpolations(input_path, output_path, interpolations)


if __name__ == "__main__":
    main()
