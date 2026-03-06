import os
import platform
import subprocess

def open_file(path: str):
    if platform.system() == 'Windows':
        os.startfile(path)  # pylint: disable=no-member
  # pylint: disable=no-member
  # pylint: disable=no-member
  # pylint: disable=no-member
  # pylint: disable=no-member
  # pylint: disable=no-member
  # pylint: disable=no-member
  # pylint: disable=no-member
  # pylint: disable=no-member
  # pylint: disable=no-member
  # pylint: disable=no-member
  # pylint: disable=no-member
  # pylint: disable=no-member
  # pylint: disable=no-member
  # pylint: disable=no-member
    elif platform.system() == 'Darwin':
        subprocess.run(['open', path])
    else:
        subprocess.run(['xdg-open', path])

def sanitize_filename(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in (' ', '.', '_')).rstrip()
