'''
Dynamic module dispatcher for miscTools.
Allows invoking any Python module in miscTools/ via: misc <script_name> <args>
'''
import argparse
import getpass
import importlib
import importlib.util
import os
from pathlib import Path
import sys

import bioinformatics_tools
from bioinformatics_tools.caragols.logger import LOGGER, config_logging_for_app


def get_available_scripts():
    """Get list of available Python modules in miscTools directory."""
    package_spec = importlib.util.find_spec("bioinformatics_tools.miscTools")
    package_path = package_spec.submodule_search_locations[0]

    scripts = []
    for f in os.listdir(package_path):
        if f.endswith('.py') and not f.startswith('__') and f != 'main.py':
            script_name = f.rsplit('.', 1)[0]
            scripts.append(script_name)

    return sorted(scripts)


def show_help():
    """Display help information."""
    available_scripts = get_available_scripts()

    print("Usage: misc <script_name> [args...]")
    print("\nAvailable scripts:")
    for script in available_scripts:
        print(f"  {script}")
    print("\nTo get help for a specific script:")
    print("  misc <script_name> --help")


def cli():
    """Main entry point for misc command."""
    # Configure logging
    config_logging_for_app()
    startup_info = {
        'cwd': Path.cwd(),
        'user': getpass.getuser(),
        'argv': sys.argv,
        'package_version': bioinformatics_tools.__version__
    }
    LOGGER.debug(f'\nStartup:\n{startup_info}', extra={'startup_info': startup_info})

    # Check if help is requested or no arguments provided
    if len(sys.argv) < 2 or sys.argv[1] in ['help', '--help', '-h']:
        show_help()
        return

    script_name = sys.argv[1]
    script_args = sys.argv[2:]  # Remaining arguments to pass to the script

    # Get available scripts
    available_scripts = get_available_scripts()

    # Check if script exists
    if script_name not in available_scripts:
        print(f"Error: Script '{script_name}' not found.")
        print(f"Available scripts: {', '.join(available_scripts)}")
        return 1

    try:
        # Import the module
        module_name = f"bioinformatics_tools.miscTools.{script_name}"
        LOGGER.info(f"Importing module: {module_name}")
        module = importlib.import_module(module_name)

        # Check if module has a typer app
        if hasattr(module, 'app') and hasattr(module.app, '__call__'):
            # Module has a typer app - use it directly
            LOGGER.info(f"Executing {script_name} typer app with args: {script_args}")
            try:
                # Set the program name to include 'misc script_name'
                module.app(script_args, prog_name=f"misc {script_name}")
                return 0
            except SystemExit as e:
                # Typer calls sys.exit() - capture the exit code
                return e.code if e.code is not None else 0
        elif hasattr(module, 'main'):
            # Module has a main function - call it the old way
            original_argv = sys.argv
            sys.argv = [script_name] + script_args

            try:
                LOGGER.info(f"Executing {script_name}.main() with args: {script_args}")
                result = module.main()
                return result if result is not None else 0
            finally:
                # Restore original sys.argv
                sys.argv = original_argv
        else:
            print(f"Error: Script '{script_name}' does not have a main() function or typer app.")
            return 1

    except ImportError as e:
        print(f"Error importing script '{script_name}': {e}")
        return 1
    except Exception as e:
        print(f"Error executing script '{script_name}': {e}")
        LOGGER.error(f"Error executing {script_name}: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    # print(f'Sys.argv: {sys.argv}')
    cli()
