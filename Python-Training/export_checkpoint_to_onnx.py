#!/usr/bin/env python3
"""
Standalone ONNX Export Utility for DRQN Checkpoints

Use this script to convert existing .pth checkpoints to ONNX format,
even if they were created before the automatic export feature was added.

Usage:
    python export_checkpoint_to_onnx.py <checkpoint_path> [--output-dir checkpoints]
    
Example:
    python export_checkpoint_to_onnx.py checkpoints/drqn_ep1000_gamma0.99_eps0.10_mem76800.pth
    python export_checkpoint_to_onnx.py checkpoints/my_model.pth --output-dir models/
"""

import argparse
import os
import sys
import torch
from pathlib import Path

# Add parent directory to path to import drqn_model
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drqn_model import DRQN, export_model_to_onnx


def load_checkpoint(checkpoint_path, device="cpu"):
    """
    Load a trained DRQN model from a .pth checkpoint file.
    
    Args:
        checkpoint_path: Path to the .pth checkpoint
        device: Device to load model on (cpu or cuda)
    
    Returns:
        Loaded DRQN model in eval mode
    """
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    
    print(f"Loading checkpoint: {checkpoint_path}")
    
    # Load checkpoint
    checkpoint = torch.load(checkpoint_path, map_location=device)
    
    # Create model
    model = DRQN().to(device)
    
    # Load weights
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    # Print info
    if 'episode' in checkpoint:
        print(f"  Episode: {checkpoint['episode']}")
    if 'epsilon' in checkpoint:
        print(f"  Epsilon: {checkpoint['epsilon']:.4f}")
    
    print(f"✓ Model loaded successfully")
    return model


def export_checkpoint(checkpoint_path, output_dir="checkpoints", device="cpu"):
    """
    Export a checkpoint to ONNX format.
    
    Args:
        checkpoint_path: Path to the .pth checkpoint
        output_dir: Directory to save ONNX file
        device: Device to use for export
    
    Returns:
        Path to the exported ONNX file
    """
    # Load model
    model = load_checkpoint(checkpoint_path, device=device)
    
    # Generate output name from checkpoint filename
    checkpoint_name = Path(checkpoint_path).stem
    
    # Export to ONNX
    onnx_path = export_model_to_onnx(
        model,
        output_dir=output_dir,
        model_name=checkpoint_name
    )
    
    return onnx_path


def batch_export(checkpoint_dir="checkpoints", output_dir="checkpoints", device="cpu"):
    """
    Export all .pth checkpoints in a directory to ONNX format.
    
    Args:
        checkpoint_dir: Directory containing .pth files
        output_dir: Directory to save ONNX files
        device: Device to use for export
    
    Returns:
        List of exported ONNX file paths
    """
    if not os.path.isdir(checkpoint_dir):
        raise NotADirectoryError(f"Directory not found: {checkpoint_dir}")
    
    # Find all .pth files
    pth_files = sorted(Path(checkpoint_dir).glob("*.pth"))
    
    if not pth_files:
        print(f"No .pth files found in {checkpoint_dir}")
        return []
    
    print(f"Found {len(pth_files)} checkpoint(s) to export:\n")
    
    exported = []
    for i, pth_file in enumerate(pth_files, 1):
        print(f"[{i}/{len(pth_files)}] Exporting {pth_file.name}...")
        try:
            onnx_path = export_checkpoint(str(pth_file), output_dir, device)
            exported.append(onnx_path)
        except Exception as e:
            print(f"  ✗ Failed: {e}\n")
    
    print(f"\n{'='*60}")
    print(f"Export complete! {len(exported)}/{len(pth_files)} files exported.")
    print(f"{'='*60}\n")
    
    return exported


def main():
    parser = argparse.ArgumentParser(
        description="Export DRQN checkpoints to ONNX format for Unity Barracuda",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Export single checkpoint:
    python export_checkpoint_to_onnx.py checkpoints/drqn_ep1000.pth
  
  Export all checkpoints in directory:
    python export_checkpoint_to_onnx.py checkpoints/ --batch
  
  Specify output directory:
    python export_checkpoint_to_onnx.py checkpoints/drqn_ep1000.pth --output-dir models/
  
  Use GPU for faster export:
    python export_checkpoint_to_onnx.py checkpoints/drqn_ep1000.pth --device cuda
        """
    )
    
    parser.add_argument(
        "path",
        help="Path to .pth checkpoint file or directory (for --batch mode)"
    )
    
    parser.add_argument(
        "--output-dir",
        default="checkpoints",
        help="Output directory for ONNX files (default: checkpoints)"
    )
    
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Batch export all .pth files in the given directory"
    )
    
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda"],
        default="cpu",
        help="Device to use for export (default: cpu)"
    )
    
    args = parser.parse_args()
    
    # Validate device
    if args.device == "cuda" and not torch.cuda.is_available():
        print("⚠ CUDA not available, falling back to CPU")
        args.device = "cpu"
    
    try:
        if args.batch:
            # Batch export mode
            batch_export(
                checkpoint_dir=args.path,
                output_dir=args.output_dir,
                device=args.device
            )
        else:
            # Single file export
            if not os.path.isfile(args.path):
                raise FileNotFoundError(f"File not found: {args.path}")
            
            print(f"Exporting checkpoint to ONNX...\n")
            onnx_path = export_checkpoint(
                checkpoint_path=args.path,
                output_dir=args.output_dir,
                device=args.device
            )
            print(f"\n✓ Export successful!")
            print(f"  ONNX file: {onnx_path}")
            
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
