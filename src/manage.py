#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def _patch_import_string():
    """
    Patch django.utils.module_loading.import_string to use rsplit.
    This avoids failures with dotted paths like logging.config.dictConfig.
    """
    try:
        from importlib import import_module
        from django.utils import module_loading
    except Exception:
        return

    def import_string(dotted_path: str):
        try:
            module_path, class_name = dotted_path.rsplit(".", 1)
        except ValueError as err:
            raise ImportError(f"{dotted_path} doesn't look like a module path") from err

        try:
            return module_loading.cached_import(module_path, class_name)
        except AttributeError as err:
            raise ImportError(
                f'Module "{module_path}" does not define a "{class_name}" attribute/class'
            ) from err

    module_loading.import_string = import_string


def main():
    """Run administrative tasks."""
    # Default to dev settings; override DJANGO_SETTINGS_MODULE if needed.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    _patch_import_string()
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
