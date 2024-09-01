# mysh - USYD_INFO1112 A1

`mysh` is a custom shell in Python that offers basic shell functionality including command execution, pipe handling, environment variable management, and signal handling.

## 📖 Getting Started

1. **Clone the Repository**:

   ```bash
   git clone https://github.com/yourusername/mysh.git
   cd mysh
   Run mysh:
   ```

   ```bash
   python mysh.py
   ```

# Try Commands:

    echo Hello, world! - Prints text.
    cd /path/to/directory - Changes the directory.
    pwd - Prints the current directory.
    var MY_VAR value - Sets a variable.
    exit - Exits the shell.

## 🔧 Key Features

1. Command Parsing and Execution
   mysh transforms input into commands through these steps:

Parsing: parse_inp() uses expand_vars() to handle variables and split_by_pipe_op() to separate commands by pipes.
Execution: Commands with pipes are handled by exec_pipe(), otherwise exec_cmd() runs single commands.

```python
cmds = parse_inp(user_inp)
if len(cmds) > 1:
exec_pipe(cmds)
else:
exec_cmd(cmds[0]) 2. Environment Variables
```

2. Handled by expand_vars(), it uses regex to match variables in ${VAR} format, replacing them with values from the environment, unless they’re escaped.

```python
def expand_vars(text: str) -> str:
def replace(match):
var_name = match.group(1)
return f'${{{var_name[1:]}}}' if var_name.startswith('\\') else os.environ.get(var_name, '')
return re.sub(r'\$\{(\\?\w+)\}', replace, text)
```

3. Pipe Handling
   exec_pipe() manages pipes by creating connections between commands, using fork and execvp() to execute commands in child processes.

```python
pipes = [os.pipe() for _ in range(len(cmds) - 1)]
for i, cmd in enumerate(cmds):
pid = os.fork()
if pid == 0: # Set up pipes and execute command
if i > 0: os.dup2(pipes[i-1][0], 0)
if i < len(cmds) - 1: os.dup2(pipes[i][1], 1)
os.execvp(cmd[0], cmd)
```

4. Built-in and External Commands

   Built-in Commands: Includes cd, pwd, var, which, and more.
   External Commands: exec_ext_cmd() handles commands not built-in by locating and executing them using execv().

## 🧪 Testing Strategy

1.  Tests are stored in tests/ and cover:

        Basic Commands: Tests for built-in commands and external commands.

    Environment Variables: Tests for setting and expanding variables.
    Pipes: Tests for piped commands.
    Error Handling: Tests for command errors and syntax issues.
    Configuration: Tests for .myshrc handling.
    Running Tests
    Run all tests using:

```bash
cd /home/test
./run_tests.sh
```

## 🎯 Conclusion

This guide provides an overview of mysh, from command parsing to execution and testing. For further adjustments, explore the codebase or tweak as needed!

`````````
　 　　/ﾞﾐヽ､,,_\_\_,,／ﾞヽ
　 　　i ノ　　 川　 ｀ヽ
　 　　/　｀　◉　 ．◉ i､
　 　彡,　　 ミ(_,人\_)彡ミ
∩, 　/　ヽ､,　　 　　　ノ
丶ニ|　　　 ````````´　ﾉ
　　∪⌒∪￣￣￣∪
`````````
