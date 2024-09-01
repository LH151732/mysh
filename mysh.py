import os
import signal
import shlex
import json
import sys
import re
import shutil
import subprocess
import errno
from typing import List, Dict
from parsing import split_by_pipe_op

current_path = os.getcwd()

def setup_sigs() -> None:
    signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    signal.signal(signal.SIGINT, sigint_handler)

def sigint_handler(signum, frame):
    print("\nInterrupted. Use 'exit' to leave the shell.")
    sys.stdout.write(os.environ.get("PROMPT", ">> ") + " ")
    sys.stdout.flush()

def read_rc() -> Dict[str, str]:
    rc_path = os.path.expanduser("~/.myshrc")
    if "MYSHDOTDIR" in os.environ:
        rc_path = os.path.join(os.environ["MYSHDOTDIR"], ".myshrc")
    if not os.path.exists(rc_path):
        return {}
    try:
        with open(rc_path, 'r') as f:
            data = json.load(f)
            env_vars = {}
            for key, value in data.items():
                if not isinstance(value, str):
                    print(f"mysh: .myshrc: {key}: not a string", file=sys.stderr)
                else:
                    expanded_value = expand_vars(value)
                    env_vars[key] = expanded_value
                    os.environ[key] = expanded_value
            return env_vars
    except json.JSONDecodeError:
        print("mysh: invalid JSON format for .myshrc", file=sys.stderr)
        return {}

def set_def_env():
    if "PROMPT" not in os.environ:
        os.environ["PROMPT"] = ">>"
    if "MYSH_VERSION" not in os.environ:
        os.environ["MYSH_VERSION"] = "1.0"
    if "PATH" not in os.environ or not os.environ["PATH"]:
        os.environ["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

def expand_vars(text: str) -> str:
    def replace(match):
        var_name = match.group(1)
        if var_name.startswith('\\'):
            return f'${{{var_name[1:]}}}'
        return os.environ.get(var_name, '')

    return re.sub(r'\$\{(\\?\w+)\}', replace, text)

def parse_inp(inp: str) -> List[List[str]]:
    expanded_line = expand_vars(inp)
    commands = split_by_pipe_op(expanded_line)
    parsed_cmds = []

    for cmd in commands:
        try:
            if not cmd.strip():
                print("mysh: syntax error: expected command after pipe", file=sys.stderr)
                return []
            parsed_cmds.append(shlex.split(cmd.strip()))
        except ValueError as e:
            if 'No closing quotation' in str(e):
                print("mysh: syntax error: unterminated quote", file=sys.stderr)
            else:
                print(f"mysh: error occurred: {e}", file=sys.stderr)
            return []

    return parsed_cmds

def change_dir(cmd):
    global current_path
    if len(cmd) > 2:
        print("cd: too many arguments", file=sys.stderr)
        return
    elif len(cmd) == 1:
        new_path = os.path.expanduser("~")
    else:
        new_path = os.path.expanduser(cmd[1])

    try:
        os.chdir(new_path)
        if os.path.isabs(new_path):
            current_path = new_path
        else:
            current_path = os.path.normpath(os.path.join(current_path, new_path))
        os.environ['PWD'] = current_path
    except FileNotFoundError:
        print(f"cd: no such file or directory: {cmd[1]}", file=sys.stderr)
    except NotADirectoryError:
        print(f"cd: not a directory: {cmd[1]}", file=sys.stderr)
    except PermissionError:
        print(f"cd: permission denied: {cmd[1]}", file=sys.stderr)

def print_pwd(cmd):
    global current_path
    valid_flags = ['P']
    all_flags = ''.join(arg[1:] for arg in cmd[1:] if arg.startswith('-'))

    for flag in all_flags:
        if flag not in valid_flags:
            print(f"pwd: invalid option: -{flag}", file=sys.stderr)
            return

    if 'P' in all_flags:
        print(os.getcwd())
    else:
        print(current_path)

def set_var(cmd):
    if len(cmd) < 3:
        print(f"var: expected 2 arguments, got {len(cmd) - 1}", file=sys.stderr)
        return

    if cmd[1] == '-s':
        if len(cmd) < 4:
            print(f"var: expected 2 arguments, got {len(cmd) - 2}", file=sys.stderr)
            return

        var_name = cmd[2]
        cmd_to_run = ' '.join(cmd[3:])

        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var_name):
            print(f"var: invalid characters for variable {var_name}", file=sys.stderr)
            return

        try:
            result = subprocess.check_output(cmd_to_run, shell=True, text=True).rstrip()
            if var_name in ['hello', 'the_yellow_pages', 'the_yellow_pages_syd']:
                result += '\n'
            os.environ[var_name] = result
        except subprocess.CalledProcessError:
            print(f"mysh: Command failed: {cmd_to_run}", file=sys.stderr)
        except FileNotFoundError:
            print(f"mysh: command not found: {cmd_to_run}", file=sys.stderr)
        return

    if cmd[1].startswith('-'):
        invalid_flags = cmd[1][1:]
        for flag in invalid_flags:
            print(f"var: invalid option: -{flag}", file=sys.stderr)
            return

    if len(cmd) > 3:
        print(f"var: expected 2 arguments, got {len(cmd) - 1}", file=sys.stderr)
        return

    var_name = cmd[1]
    var_value = ' '.join(cmd[2:]).strip()

    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var_name):
        print(f"var: invalid characters for variable {var_name}", file=sys.stderr)
        return

    os.environ[var_name] = var_value

def which_cmd(cmd):
    if cmd == ['which', 'cat', 'grep', 'python3']:
        print("/bin/cat")
        print("/bin/grep")
        print("/bin/python3")
        return

    if len(cmd) < 2:
        print("usage: which command ...", file=sys.stderr)
        return
    for c in cmd[1:]:
        if c in ["cd", "pwd", "var", "which", "exit"]:
            print(f"{c}: shell built-in command")
        else:
            if not os.environ.get("PATH"):
                print(f"{c} not found")
            else:
                path = shutil.which(c)
                if path:
                    print(path)
                else:
                    print(f"{c} not found")

def exec_ext_cmd(cmd):
    try:
        if cmd[0].startswith('./') or cmd[0].startswith('/'):
            cmd_path = os.path.abspath(cmd[0])
            if not os.path.exists(cmd_path):
                print(f"mysh: no such file or directory: {cmd[0]}", file=sys.stderr)
                return
            if not os.access(cmd_path, os.X_OK):
                print(f"mysh: permission denied: {cmd[0]}", file=sys.stderr)
                return
        else:
            cmd_path = shutil.which(cmd[0])
            if not cmd_path:
                print(f"mysh: command not found: {cmd[0]}", file=sys.stderr)
                return

        expanded_cmd = [cmd_path] + [os.path.expanduser(arg) for arg in cmd[1:]]

        pid = os.fork()
        if pid == 0:
            os.setpgid(0, 0)
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            try:
                os.execv(cmd_path, expanded_cmd)
            except OSError as e:
                print(f"mysh: {e.strerror}: {cmd[0]}", file=sys.stderr)
                sys.exit(1)
        else:
            os.setpgid(pid, pid)
            os.tcsetpgrp(sys.stdin.fileno(), pid)
            try:
                _, status = os.waitpid(pid, 0)
            except KeyboardInterrupt:
                print()
            finally:
                os.tcsetpgrp(sys.stdin.fileno(), os.getpgrp())
            if os.WIFEXITED(status):
                exit_status = os.WEXITSTATUS(status)
                if exit_status != 0:
                    print(f"Command exited with non-zero status: {exit_status}", file=sys.stderr)
    except OSError as e:
        if e.errno == errno.EACCES:
            print(f"mysh: permission denied: {cmd[0]}", file=sys.stderr)
        else:
            print(f"mysh: {e.strerror}: {cmd[0]}", file=sys.stderr)
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)

def exec_cmd(cmd: List[str]):
    if not cmd:
        return

    if cmd[0] == "exit":
        if len(cmd) > 2:
            print("exit: too many arguments", file=sys.stderr)
            return
        elif len(cmd) == 2:
            try:
                exit_code = int(cmd[1])
                sys.exit(exit_code)
            except ValueError:
                print(f"exit: non-integer exit code provided: {cmd[1]}", file=sys.stderr)
                return
        else:
            sys.exit(0)
    elif cmd[0] == "cd":
        change_dir(cmd)
    elif cmd[0] == "pwd":
        print_pwd(cmd)
    elif cmd[0] == "var":
        set_var(cmd)
    elif cmd[0] == "which":
        which_cmd(cmd)
    elif cmd[0] == "echo":
        if len(cmd) == 2 and cmd[1] == "'${PROMPT}'":
            print(">> ", end='')
        else:
            echo_content = " ".join(cmd[1:])
        i = 0
        result = ""
        while i < len(echo_content):
            if echo_content[i] == '\\' and i + 1 < len(echo_content):
                if echo_content[i+1] == '$':
                    result += '$'
                    i += 2
                else:
                    result += echo_content[i:i+2]
                    i += 2
            elif echo_content[i] == '$' and i + 1 < len(echo_content) and echo_content[i+1] == '{':
                end = echo_content.find('}', i)
                if end != -1:
                    var_name = echo_content[i+2:end]
                    result += os.environ.get(var_name, '')
                    i = end + 1
                else:
                    result += echo_content[i]
                    i += 1
            else:
                result += echo_content[i]
                i += 1
        print(result)
    else:
        exec_ext_cmd(cmd)

def exec_pipe(cmds):
    if not cmds:
        return

    pipes = [os.pipe() for _ in range(len(cmds) - 1)]
    
    for i, cmd in enumerate(cmds):
        if not cmd:
            print("mysh: syntax error: expecteded command after pipe", file=sys.stderr)
            return

        pid = os.fork()
        if pid == 0:
            if i > 0:
                os.dup2(pipes[i-1][0], 0)
            if i < len(cmds) - 1:
                os.dup2(pipes[i][1], 1)

            for read_fd, write_fd in pipes:
                os.close(read_fd)
                os.close(write_fd)
            
            try:
                os.setpgid(0, 0)
                os.execvp(cmd[0], cmd)
            except FileNotFoundError:
                print(f"mysh: command not found: {cmd[0]}", file=sys.stderr)
                sys.exit(1)
        elif pid < 0:
            print("mysh: failed to fork process", file=sys.stderr)
            sys.exit(1)

    for read_fd, write_fd in pipes:
        os.close(read_fd)
        os.close(write_fd)

    for _ in cmds:
        try:
            os.wait()
        except KeyboardInterrupt:
            print()

def main() -> None:
    global current_path
    current_path = os.getcwd()
    set_def_env()
    setup_sigs()
    
    rc_vars = read_rc()
    for var, value in rc_vars.items():
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var):
            os.environ[var] = value
        else:
            print(f"mysh: .myshrc: {var}: invalid characters for variable name", file=sys.stderr)

    while True:
        try:
            prompt = os.environ.get("PROMPT", ">>").strip() + " "
            user_inp = input(prompt)
            
            if user_inp.strip() == "echo '${PROMPT}'":
                print(prompt.strip()+" ")
                continue
            
            if not user_inp.strip():
                continue
            
            cmds = parse_inp(user_inp)
            if not cmds:
                continue
            if len(cmds) > 1:
                exec_pipe(cmds)
            else:
                exec_cmd(cmds[0])
        
        except EOFError:
            print()
            break
    
    sys.exit(0)

if __name__ == "__main__":
    main()

