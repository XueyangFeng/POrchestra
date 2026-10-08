"""
SWE-Agent ACI (Agent-Computer Interface) Tools.

This module implements the specialized command interface for SWE-Agent,
providing file navigation, editing, and search capabilities with state management.

Based on the real SWE-Agent's ACI design:
- open: Open file and display content with line numbers
- scroll_up/scroll_down: Navigate within opened file
- goto: Jump to specific line
- edit: Edit line range with syntax checking
- str_replace: Replace exact string in file (avoids line number issues)
- insert: Insert content at specific line
- create: Create or overwrite a file
- search_file: Search pattern in current file
- search_dir: Search pattern in directory
- find_file: Find files by name pattern
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, List
import re
import base64
import shlex


@dataclass
class ACIState:
    """State manager for ACI tools."""
    current_file: Optional[str] = None
    current_line: int = 1
    window_size: int = 100
    working_dir: str = "/testbed"
    
    def to_status_line(self) -> str:
        """Generate status line for observation."""
        file_info = self.current_file if self.current_file else "n/a"
        return f"(Open file: {file_info}) (Current directory: {self.working_dir})"


class ACIToolManager:
    """
    Manager for ACI tools that wraps an executor and maintains state.
    
    This provides the specialized SWE-Agent commands while delegating
    actual execution to the underlying executor (Docker, etc.).
    """
    
    def __init__(self, executor, window_size: int = 100):
        """
        Initialize ACI tool manager.
        
        Args:
            executor: The underlying executor (SWEBenchExecutor) for running commands
            window_size: Number of lines to display in file window
        """
        self.executor = executor
        self.state = ACIState(window_size=window_size)
        
        # Command registry
        self.commands = {
            "open": self.cmd_open,
            "scroll_up": self.cmd_scroll_up,
            "scroll_down": self.cmd_scroll_down,
            "goto": self.cmd_goto,
            "edit": self.cmd_edit,
            "str_replace": self.cmd_str_replace,
            "insert": self.cmd_insert,
            "create": self.cmd_create,
            "delete_lines": self.cmd_delete_lines,
            "search_file": self.cmd_search_file,
            "search_dir": self.cmd_search_dir,
            "find_file": self.cmd_find_file,
            "state": self.cmd_state,
        }
    
    async def execute(self, command_str: str) -> Tuple[str, int]:
        """
        Parse and execute an ACI command or fall back to bash.
        
        Args:
            command_str: The command string to execute
            
        Returns:
            Tuple of (output, exit_code)
        """
        command_str = command_str.strip()
        if not command_str:
            return "Error: Empty command", 1
        
        # Parse command name and arguments
        parts = command_str.split(maxsplit=1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # Check if it's an ACI command
        if cmd_name in self.commands:
            try:
                return await self.commands[cmd_name](args)
            except Exception as e:
                return f"Error executing {cmd_name}: {str(e)}", 1
        
        # Fall back to bash execution
        return await self._execute_bash(command_str)
    
    async def _execute_bash(self, command: str) -> Tuple[str, int]:
        """Execute a bash command via the executor."""
        output, exit_code = await self.executor.execute_command(command)
        return format_command_output(output, exit_code), exit_code
    
    async def cmd_open(self, args: str) -> Tuple[str, int]:
        """
        Open a file and display content with line numbers.
        
        Usage: open <file_path> [line_number]
        """
        parts = args.strip().split()
        if not parts:
            return "Usage: open <file_path> [line_number]", 1
        
        file_path = parts[0]
        line_number = 1
        if len(parts) > 1:
            try:
                line_number = int(parts[1])
            except ValueError:
                return f"Error: Invalid line number '{parts[1]}'", 1
        
        # Check if file exists
        check_cmd = f"test -f {file_path} && echo 'exists' || echo 'not_found'"
        output, _ = await self.executor.execute_command(check_cmd)
        if "not_found" in output:
            return f"Error: File '{file_path}' not found.", 1
        
        # Get file content
        self.state.current_file = file_path
        self.state.current_line = max(1, line_number)
        
        return await self._display_window()
    
    async def cmd_scroll_down(self, args: str) -> Tuple[str, int]:
        """Scroll down in the current file."""
        if not self.state.current_file:
            return "Error: No file open. Use 'open <file>' first.", 1
        
        # Parse optional line count
        lines = self.state.window_size
        if args.strip():
            try:
                lines = int(args.strip())
            except ValueError:
                pass
        
        self.state.current_line += lines
        return await self._display_window()
    
    async def cmd_scroll_up(self, args: str) -> Tuple[str, int]:
        """Scroll up in the current file."""
        if not self.state.current_file:
            return "Error: No file open. Use 'open <file>' first.", 1
        
        # Parse optional line count
        lines = self.state.window_size
        if args.strip():
            try:
                lines = int(args.strip())
            except ValueError:
                pass
        
        self.state.current_line = max(1, self.state.current_line - lines)
        return await self._display_window()
    
    async def cmd_goto(self, args: str) -> Tuple[str, int]:
        """
        Jump to a specific line in the current file.
        
        Usage: goto <line_number>
        """
        if not self.state.current_file:
            return "Error: No file open. Use 'open <file>' first.", 1
        
        if not args.strip():
            return "Usage: goto <line_number>", 1
        
        try:
            line_number = int(args.strip())
        except ValueError:
            return f"Error: Invalid line number '{args.strip()}'", 1
        
        if line_number < 1:
            return "Error: Line number must be positive", 1
        
        self.state.current_line = line_number
        return await self._display_window()
    
    async def cmd_str_replace(self, args: str) -> Tuple[str, int]:
        """
        Replace exact string in file. This is the PREFERRED edit method.
        
        Usage: str_replace <file_path>
        <<<<<<< SEARCH
        exact content to find (must be unique in file)
        =======
        new content to replace with
        >>>>>>> REPLACE
        
        The SEARCH block must match exactly and be unique in the file.
        """
        # Parse file path from first line
        lines = args.strip().split('\n')
        if not lines:
            return self._str_replace_usage(), 1
        
        file_path = lines[0].strip()
        if not file_path:
            file_path = self.state.current_file
        
        if not file_path:
            return "Error: No file specified and no file open.", 1
        
        # Find SEARCH and REPLACE markers
        content = '\n'.join(lines[1:]) if len(lines) > 1 else args
        
        # Parse the search/replace blocks
        search_match = re.search(
            r'<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE',
            content,
            re.DOTALL
        )
        
        if not search_match:
            # Try alternative format without file path on first line
            search_match = re.search(
                r'<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE',
                args,
                re.DOTALL
            )
            if search_match:
                file_path = self.state.current_file
                if not file_path:
                    return "Error: No file open. Specify file path or use 'open' first.", 1
        
        if not search_match:
            return self._str_replace_usage(), 1
        
        old_str = search_match.group(1)
        new_str = search_match.group(2)
        
        # Read current file content
        read_output, exit_code = await self.executor.execute_command(f"cat {file_path}")
        if exit_code != 0:
            return f"Error reading file: {read_output}", exit_code
        
        file_content = read_output
        
        # Check if old_str exists and is unique
        count = file_content.count(old_str)
        if count == 0:
            return f"Error: Search string not found in {file_path}.\nMake sure the search string matches exactly (including whitespace and indentation).", 1
        if count > 1:
            return f"Error: Search string found {count} times in {file_path}. It must be unique.\nAdd more context to make the search string unique.", 1
        
        # Perform replacement
        new_content = file_content.replace(old_str, new_str, 1)
        
        # Write back using Python to avoid shell escaping issues
        # Encode content as base64 to safely pass through shell
        encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('ascii')
        write_cmd = f"echo '{encoded_content}' | base64 -d > {file_path}"
        output, exit_code = await self.executor.execute_command(write_cmd)
        if exit_code != 0:
            return f"Error writing file: {output}", exit_code
        
        # Syntax check for Python files
        lint_result = ""
        if file_path.endswith('.py'):
            lint_output, lint_code = await self.executor.execute_command(
                f"python -m py_compile {file_path} 2>&1"
            )
            if lint_code != 0:
                lint_result = f"\n[Syntax Error]\n{lint_output}"
            else:
                lint_result = "\n[Syntax check passed]"
        
        # Find where the replacement occurred to show context
        # Find the line number of the new content
        new_lines = new_content.split('\n')
        for i, line in enumerate(new_lines):
            if new_str.split('\n')[0] in line:
                self.state.current_line = max(1, i + 1 - 3)  # Show a few lines before
                break
        
        self.state.current_file = file_path
        window_output, _ = await self._display_window()
        
        return f"Successfully replaced content in {file_path}.{lint_result}\n\n{window_output}", 0
    
    def _str_replace_usage(self) -> str:
        """Return usage for str_replace command."""
        return """Usage: str_replace <file_path>
<<<<<<< SEARCH
exact content to find
=======
new content to replace with
>>>>>>> REPLACE

The SEARCH content must:
1. Match exactly (including whitespace and indentation)
2. Be unique in the file (add more context if needed)

Example:
str_replace /testbed/myfile.py
<<<<<<< SEARCH
def old_function():
    return 1
=======
def old_function():
    return 2
>>>>>>> REPLACE
"""
    
    async def cmd_insert(self, args: str) -> Tuple[str, int]:
        """
        Insert content after a specific line.
        
        Usage: insert <file_path> <line_number>
        <content to insert>
        end_of_insert
        """
        lines = args.strip().split('\n')
        if len(lines) < 2:
            return "Usage: insert <file_path> <line_number>\\n<content>\\nend_of_insert", 1
        
        # Parse first line for file path and line number
        first_line_parts = lines[0].strip().split()
        if len(first_line_parts) < 2:
            return "Usage: insert <file_path> <line_number>\\n<content>\\nend_of_insert", 1
        
        file_path = first_line_parts[0]
        try:
            line_number = int(first_line_parts[1])
        except ValueError:
            return f"Error: Invalid line number '{first_line_parts[1]}'", 1
        
        # Extract content to insert
        content_lines = []
        found_end = False
        for line in lines[1:]:
            if line.strip() == "end_of_insert":
                found_end = True
                break
            content_lines.append(line)
        
        if not found_end:
            return "Error: Missing 'end_of_insert' marker", 1
        
        insert_content = '\n'.join(content_lines)
        
        # Read current file
        read_output, exit_code = await self.executor.execute_command(f"cat {file_path}")
        if exit_code != 0:
            return f"Error reading file: {read_output}", exit_code
        
        file_lines = read_output.split('\n')
        
        if line_number < 0 or line_number > len(file_lines):
            return f"Error: Line number {line_number} out of range (file has {len(file_lines)} lines)", 1
        
        # Insert content after specified line
        new_file_lines = (
            file_lines[:line_number] +
            insert_content.split('\n') +
            file_lines[line_number:]
        )
        new_content = '\n'.join(new_file_lines)
        
        # Write back
        encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('ascii')
        write_cmd = f"echo '{encoded_content}' | base64 -d > {file_path}"
        output, exit_code = await self.executor.execute_command(write_cmd)
        if exit_code != 0:
            return f"Error writing file: {output}", exit_code
        
        # Syntax check
        lint_result = ""
        if file_path.endswith('.py'):
            lint_output, lint_code = await self.executor.execute_command(
                f"python -m py_compile {file_path} 2>&1"
            )
            if lint_code != 0:
                lint_result = f"\n[Syntax Error]\n{lint_output}"
            else:
                lint_result = "\n[Syntax check passed]"
        
        self.state.current_file = file_path
        self.state.current_line = max(1, line_number - 2)
        window_output, _ = await self._display_window()
        
        return f"Content inserted at line {line_number} in {file_path}.{lint_result}\n\n{window_output}", 0
    
    async def cmd_create(self, args: str) -> Tuple[str, int]:
        """
        Create or overwrite a file with content.
        
        Usage: create <file_path>
        <file content>
        end_of_create
        """
        lines = args.strip().split('\n')
        if not lines:
            return "Usage: create <file_path>\\n<content>\\nend_of_create", 1
        
        file_path = lines[0].strip()
        if not file_path:
            return "Error: File path required", 1
        
        # Extract content
        content_lines = []
        found_end = False
        for line in lines[1:]:
            if line.strip() == "end_of_create":
                found_end = True
                break
            content_lines.append(line)
        
        if not found_end:
            return "Error: Missing 'end_of_create' marker", 1
        
        content = '\n'.join(content_lines)
        
        # Write file using base64 encoding
        encoded_content = base64.b64encode(content.encode('utf-8')).decode('ascii')
        write_cmd = f"echo '{encoded_content}' | base64 -d > {file_path}"
        output, exit_code = await self.executor.execute_command(write_cmd)
        if exit_code != 0:
            return f"Error creating file: {output}", exit_code
        
        # Syntax check
        lint_result = ""
        if file_path.endswith('.py'):
            lint_output, lint_code = await self.executor.execute_command(
                f"python -m py_compile {file_path} 2>&1"
            )
            if lint_code != 0:
                lint_result = f"\n[Syntax Error]\n{lint_output}"
            else:
                lint_result = "\n[Syntax check passed]"
        
        self.state.current_file = file_path
        self.state.current_line = 1
        window_output, _ = await self._display_window()
        
        return f"File {file_path} created successfully.{lint_result}\n\n{window_output}", 0
    
    async def cmd_edit(self, args: str) -> Tuple[str, int]:
        """
        Edit a range of lines in the current file.
        
        Usage: edit <start_line>:<end_line>
        <new_content>
        end_of_edit
        
        The new content replaces lines from start_line to end_line (inclusive).
        
        NOTE: For large edits, prefer using str_replace command instead.
        """
        if not self.state.current_file:
            return "Error: No file open. Use 'open <file>' first.", 1
        
        # Parse the edit command
        # Format: edit <start>:<end>\n<content>\nend_of_edit
        lines = args.strip().split('\n')
        if not lines:
            return "Usage: edit <start_line>:<end_line>\\n<new_content>\\nend_of_edit", 1
        
        # Parse line range
        range_match = re.match(r'(\d+):(\d+)', lines[0].strip())
        if not range_match:
            return "Error: Invalid line range. Use format: edit <start>:<end>", 1
        
        start_line = int(range_match.group(1))
        end_line = int(range_match.group(2))
        
        if start_line > end_line:
            return "Error: Start line must be <= end line", 1
        
        # Extract new content (everything after the range line until end_of_edit)
        content_lines = []
        found_end = False
        for line in lines[1:]:
            if line.strip() == "end_of_edit":
                found_end = True
                break
            content_lines.append(line)
        
        if not found_end:
            return "Error: Missing 'end_of_edit' marker", 1
        
        new_content = '\n'.join(content_lines)
        
        # Read the file
        read_output, exit_code = await self.executor.execute_command(
            f"cat {self.state.current_file}"
        )
        if exit_code != 0:
            return f"Error reading file: {read_output}", exit_code
        
        # Split into lines and perform replacement
        file_lines = read_output.split('\n')
        
        # Validate line range
        if start_line > len(file_lines):
            return f"Error: Start line {start_line} exceeds file length ({len(file_lines)} lines)", 1
        
        # Replace the lines
        new_file_lines = (
            file_lines[:start_line - 1] + 
            new_content.split('\n') + 
            file_lines[end_line:]
        )
        new_file_content = '\n'.join(new_file_lines)
        
        # Write back using base64 encoding to avoid shell issues
        encoded_content = base64.b64encode(new_file_content.encode('utf-8')).decode('ascii')
        write_cmd = f"echo '{encoded_content}' | base64 -d > {self.state.current_file}"
        output, exit_code = await self.executor.execute_command(write_cmd)
        if exit_code != 0:
            return f"Error writing file: {output}", exit_code
        
        # Perform syntax check for Python files
        lint_result = ""
        if self.state.current_file.endswith('.py'):
            lint_output, lint_code = await self.executor.execute_command(
                f"python -m py_compile {self.state.current_file} 2>&1"
            )
            if lint_code != 0:
                lint_result = f"\n[Syntax Error]\n{lint_output}"
            else:
                lint_result = "\n[Syntax check passed]"
        
        # Show the edited section
        self.state.current_line = start_line
        window_output, _ = await self._display_window()
        
        return f"File updated successfully.{lint_result}\n\n{window_output}", 0
    
    async def cmd_delete_lines(self, args: str) -> Tuple[str, int]:
        """
        Delete a range of lines from a file.
        
        Usage: delete_lines <file_path> <start_line> <end_line>
        
        Deletes lines from start_line to end_line (inclusive).
        This is more efficient than using sed repeatedly.
        """
        parts = args.strip().split()
        if len(parts) < 3:
            return "Usage: delete_lines <file_path> <start_line> <end_line>", 1
        
        file_path = parts[0]
        try:
            start_line = int(parts[1])
            end_line = int(parts[2])
        except ValueError:
            return "Error: start_line and end_line must be integers", 1
        
        if start_line < 1 or end_line < start_line:
            return "Error: Invalid line range (start_line must be >= 1 and <= end_line)", 1
        
        # Read the file
        read_output, exit_code = await self.executor.execute_command(f"cat {file_path}")
        if exit_code != 0:
            return f"Error reading file: {read_output}", exit_code
        
        lines = read_output.split('\n')
        total_lines = len(lines)
        
        if start_line > total_lines:
            return f"Error: start_line ({start_line}) exceeds file length ({total_lines})", 1
        
        # Delete the lines (1-indexed to 0-indexed)
        del lines[start_line - 1:end_line]  # end_line is inclusive, but Python slice is exclusive
        
        new_content = '\n'.join(lines)
        
        # Write back using base64 encoding
        encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('ascii')
        write_cmd = f"echo '{encoded_content}' | base64 -d > {file_path}"
        output, exit_code = await self.executor.execute_command(write_cmd)
        if exit_code != 0:
            return f"Error writing file: {output}", exit_code
        
        deleted_count = min(end_line, total_lines) - start_line + 1
        
        # Syntax check for Python files
        lint_result = ""
        if file_path.endswith('.py'):
            lint_output, lint_code = await self.executor.execute_command(
                f"python -m py_compile {file_path} 2>&1"
            )
            if lint_code != 0:
                lint_result = f"\n[Syntax Error]\n{lint_output}"
            else:
                lint_result = "\n[Syntax check passed]"
        
        # Update state
        self.state.current_file = file_path
        self.state.current_line = max(1, start_line - 5)  # Show context around deleted area
        window_output, _ = await self._display_window()
        
        return f"Deleted {deleted_count} lines ({start_line}-{end_line}).{lint_result}\n\n{window_output}", 0
    
    async def cmd_search_file(self, args: str) -> Tuple[str, int]:
        """
        Search for a pattern in the current file.
        
        Usage: search_file <pattern> [file_path]
        """
        parsed, error = _parse_pattern_and_path(args, self.state.current_file)
        if error:
            return f"Error: {error}", 1
        pattern, file_path = parsed
        
        if not file_path:
            return "Error: No file specified and no file open.", 1
        
        # Use grep with line numbers, limit results
        cmd = (
            f"grep -n -- {shlex.quote(pattern)} {shlex.quote(file_path)} "
            "2>/dev/null | head -50"
        )
        output, exit_code = await self.executor.execute_command(cmd)
        
        if not output.strip():
            return f"No matches found for '{pattern}' in {file_path}", 0
        
        # Format output with line numbers
        lines = output.strip().split('\n')
        formatted_lines = []
        for line in lines:
            if ':' in line:
                line_num, content = line.split(':', 1)
                formatted_lines.append(f"{line_num}| {content}")
            else:
                formatted_lines.append(line)
        
        result = f"Found {len(formatted_lines)} matches in {file_path}:\n" + '\n'.join(formatted_lines)
        if len(lines) >= 50:
            result += "\n... (results truncated to 50 matches)"
        
        return result, 0
    
    async def cmd_search_dir(self, args: str) -> Tuple[str, int]:
        """
        Search for a pattern in directory files.
        
        Usage: search_dir <pattern> [directory]
        
        Returns only file names to avoid information overload.
        """
        parsed, error = _parse_pattern_and_path(args, self.state.working_dir)
        if error:
            return f"Error: {error}", 1
        pattern, directory = parsed
        
        # Use grep -l to only list file names, limit results
        cmd = (
            f"grep -rl -- {shlex.quote(pattern)} {shlex.quote(directory)} "
            "2>/dev/null | head -50"
        )
        output, exit_code = await self.executor.execute_command(cmd)
        
        if not output.strip():
            return f"No files found containing '{pattern}' in {directory}", 0
        
        files = output.strip().split('\n')
        result = f"Found {len(files)} files containing '{pattern}':\n" + '\n'.join(files)
        if len(files) >= 50:
            result += "\n... (results truncated to 50 files)"
        
        return result, 0
    
    async def cmd_find_file(self, args: str) -> Tuple[str, int]:
        """
        Find files by name pattern.
        
        Usage: find_file <name_pattern> [directory]
        """
        parts = args.strip().split(maxsplit=1)
        if not parts:
            return "Usage: find_file <name_pattern> [directory]", 1
        
        name_pattern = parts[0]
        directory = parts[1] if len(parts) > 1 else self.state.working_dir
        
        # Use find command, limit results
        cmd = f"find {directory} -type f -name '*{name_pattern}*' 2>/dev/null | head -50"
        output, exit_code = await self.executor.execute_command(cmd)
        
        if not output.strip():
            return f"No files found matching '*{name_pattern}*' in {directory}", 0
        
        files = output.strip().split('\n')
        result = f"Found {len(files)} files:\n" + '\n'.join(files)
        if len(files) >= 50:
            result += "\n... (results truncated to 50 files)"
        
        return result, 0
    
    async def cmd_state(self, args: str) -> Tuple[str, int]:
        """Display current state information."""
        return self.state.to_status_line(), 0

    async def _display_window(self) -> Tuple[str, int]:
        """Display the current window of the open file with line numbers."""
        if not self.state.current_file:
            return "Error: No file open.", 1
        
        start = self.state.current_line
        end = start + self.state.window_size - 1
        
        # Get file content for the window
        cmd = f"sed -n '{start},{end}p' {self.state.current_file}"
        output, exit_code = await self.executor.execute_command(cmd)
        
        if exit_code != 0:
            return f"Error reading file: {output}", exit_code
        
        # Format with line numbers
        formatted = format_file_content(output, start)
        
        # Get total line count
        count_cmd = f"wc -l < {self.state.current_file}"
        count_output, _ = await self.executor.execute_command(count_cmd)
        try:
            total_lines = int(count_output.strip())
        except ValueError:
            total_lines = "?"
        
        header = f"[File: {self.state.current_file} ({total_lines} lines total)]"
        footer = f"(showing lines {start}-{min(end, total_lines if isinstance(total_lines, int) else end)})"
        
        return f"{header}\n{formatted}\n{footer}", 0
    
    def get_command_docs(self) -> str:
        """Generate documentation for all ACI commands."""
        return """Available commands:

=== FILE VIEWING ===
open <file> [<line_number>]
    Opens the file at the given path. If line_number is provided, the window will start at that line.
    
scroll_down [<lines>]
    Moves the window down by the specified number of lines (default: window_size).
    
scroll_up [<lines>]
    Moves the window up by the specified number of lines (default: window_size).
    
goto <line_number>
    Moves the window to show the specified line number at the top.

=== FILE EDITING (use str_replace for best results) ===
str_replace <file_path>
<<<<<<< SEARCH
exact text to find (must be unique in file)
=======
replacement text
>>>>>>> REPLACE
    **PREFERRED METHOD** - Replaces exact text match. The search text must be unique.
    Use this for most edits - it's more reliable than line-based edit.
    
edit <start_line>:<end_line>
<replacement_text>
end_of_edit
    Replaces lines from start_line to end_line (inclusive) with the given text.
    For Python files, syntax checking is performed automatically.
    NOTE: For large edits, prefer str_replace to avoid command length limits.

delete_lines <file_path> <start_line> <end_line>
    Deletes lines from start_line to end_line (inclusive) in a single operation.
    **USE THIS** instead of running sed multiple times to delete a block of code.
    Example: delete_lines myfile.py 100 120  (deletes lines 100-120)

insert <file_path> <line_number>
<content to insert>
end_of_insert
    Inserts content after the specified line number.

create <file_path>
<file content>
end_of_create
    Creates or overwrites a file with the given content.
    
=== SEARCHING ===
search_file <pattern> [<file>]
    Searches for CONTENT pattern in the current open file (or specified file).
    Shows matching lines with line numbers. Use this to find function definitions.
    
search_dir <pattern> [<directory>]
    Searches for CONTENT pattern in all files within the directory.
    Returns file names containing the pattern. Use this to find which file contains a function.
    
find_file <name_pattern> [<directory>]
    Finds files by FILE NAME pattern (not content). 
    Example: find_file test to find files with "test" in their name.

=== BASH COMMANDS ===
You can also run any bash command directly (e.g., ls, cat, grep, python, pytest, etc.)

TIP: For deleting code blocks, use "delete_lines <file> <start> <end>" instead of multiple sed commands.
"""


def _parse_pattern_and_path(
    args: str, default_path: Optional[str]
) -> Tuple[Optional[Tuple[str, str]], Optional[str]]:
    """Parse a quoted search pattern and optional path without retaining quotes."""
    try:
        parts = shlex.split(args.strip())
    except ValueError as exc:
        return None, f"Invalid quoting: {exc}"
    if not parts:
        return None, "A search pattern is required"
    if len(parts) == 1:
        pattern = parts[0]
        path = default_path
    else:
        # The optional path is the final token. Quoting allows a multi-word
        # pattern to remain unambiguous, e.g. search_file "def foo" file.py.
        pattern = " ".join(parts[:-1])
        path = parts[-1]
    if not path:
        return None, "No path specified and no default path is available"
    return (pattern, path), None


def format_file_content(content: str, start_line: int = 1) -> str:
    """
    Format file content with line numbers.
    
    Args:
        content: The file content to format
        start_line: The starting line number
        
    Returns:
        Formatted content with line numbers like "1| def foo():"
    """
    if not content:
        return ""
    
    lines = content.split('\n')
    # Remove trailing empty line if present (from trailing newline)
    if lines and lines[-1] == '':
        lines = lines[:-1]
    
    formatted_lines = []
    for i, line in enumerate(lines):
        line_num = start_line + i
        formatted_lines.append(f"{line_num}| {line}")
    
    return '\n'.join(formatted_lines)


def format_command_output(output: str, exit_code: int) -> str:
    """
    Format command output with proper messaging.
    
    Args:
        output: The command output
        exit_code: The command exit code
        
    Returns:
        Formatted output, or success message if output is empty
    """
    if not output.strip() and exit_code == 0:
        return "Command ran successfully. No output."
    return output
