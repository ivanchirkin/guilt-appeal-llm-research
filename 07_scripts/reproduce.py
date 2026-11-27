"""Run the local, network-free validation and calculation pipeline."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-figures', action='store_true', help='Check existing figure provenance without rerendering')
    args = parser.parse_args()
    commands = [[sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v']]
    commands.extend([[sys.executable, f'07_scripts/{script}.py'] for script in
                     ('validate_corpus', 'validate_annotations', 'calculate_metrics')])
    if not args.no_figures:
        commands.append([sys.executable, '07_scripts/build_figures.py'])
    commands.append([sys.executable, '07_scripts/build_summary.py'])
    commands.append([sys.executable, '07_scripts/validate_results.py'])
    for command in commands:
        print('> ' + ' '.join(command[1:]), flush=True)
        result = subprocess.run(command, cwd=ROOT,
                                env=dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1'))
        if result.returncode:
            return result.returncode
    return 0


if __name__ == '__main__':
    sys.exit(main())
