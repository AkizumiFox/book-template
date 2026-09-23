"""
Build System Utilities
======================
Helper functions for logging and formatting.
"""

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{msg}{Colors.ENDC}")

def print_step(msg):
    print(f"{Colors.BLUE}==>{Colors.ENDC} {Colors.BOLD}{msg}{Colors.ENDC}")

def print_success(msg):
    print(f"{Colors.GREEN}✓{Colors.ENDC} {msg}")

def print_info(msg):
    print(f"{Colors.CYAN}ℹ{Colors.ENDC} {msg}")

def print_warning(msg):
    print(f"{Colors.WARNING}⚠ {msg}{Colors.ENDC}")

def print_error(msg):
    print(f"{Colors.FAIL}✖ {msg}{Colors.ENDC}")

def print_file_action(action, src, dst=None):
    if dst:
        print(f"  {Colors.CYAN}{action}{Colors.ENDC} {src} {Colors.BOLD}→{Colors.ENDC} {dst}")
    else:
        print(f"  {Colors.CYAN}{action}{Colors.ENDC} {src}")


def run_with_crash_retry(cmd, attempts: int = 3, **kwargs):
    """
    Run a command with check=True, retrying if it is killed by a signal.
    Pandoc 3.1.x occasionally segfaults in Lua filters; a rerun succeeds.
    """
    import subprocess
    kwargs = {"capture_output": True, "text": True, **kwargs}
    for attempt in range(attempts):
        result = subprocess.run(cmd, **kwargs)
        if result.returncode >= 0 or attempt == attempts - 1:
            break
        print_warning(f"{cmd[0]} crashed (signal {-result.returncode}); retrying")
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return result
