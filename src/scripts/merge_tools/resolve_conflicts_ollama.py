#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resolve_conflicts.py

Usage:
    ./resolve_conflicts.py <filename> <llm_model>

This script processes a file that contains Git merge conflicts (in diff3 style)
and attempts to resolve each conflict block using an LLM via the Ollama CLI.
If the LLM is not confident about a resolution, the original snippet (which now
includes additional context) is retained.
Additionally, each query sent to the LLM along with its response is logged in a
directory named "queries" for later inspection.
"""

import os
import re
import sys
import subprocess
from datetime import datetime
from typing import List, Optional


def call_llm(prompt: str, llm_model: str) -> Optional[str]:
    """
    Call the LLM using the Ollama CLI with the provided prompt.

    Args:
        prompt (str): The prompt to send to the LLM.
        llm_model (str): The name of the LLM model to use.

    Returns:
        Optional[str]: The response from the LLM, or None if an error occurred.
    """
    try:
        result = subprocess.run(
            ["ollama", "run", llm_model, prompt],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"Error calling LLM: {e}\n")
        return None


def extract_code_from_response(response: str) -> str:
    """
    Extracts only the code part from the LLM response.

    It first checks for markdown code fences. If found, only the content within
    the first code fence is returned. Otherwise, it will look for a section
    starting with something like "merged result:" and return what follows.
    If none of these patterns match, the entire response is returned as-is.

    Args:
        response (str): The LLM response.

    Returns:
        str: The extracted code.
    """
    # Try to find a markdown code fence block.
    fence_match = re.search(r"```(?:[^\n]*\n)?(.*?)```", response, re.DOTALL)
    if fence_match:
        return fence_match.group(1)
    else:
        print("No code fence found in LLM response. Not modifying any code.")
        sys.exit(1)


def log_query_response(query: str, response: str, conflict_id: str) -> None:
    """
    Log the query and response to a file in the 'queries' directory.

    Args:
        query (str): The query sent to the LLM.
        response (str): The response received from the LLM.
        conflict_id (str): A unique identifier for the conflict block.
    """
    log_dir = "queries"
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(log_dir, f"{conflict_id}_{timestamp}.log")
    with open(filename, "w", encoding="utf-8") as f:
        f.write("QUERY:\n")
        f.write(query)
        f.write("\n\nRESPONSE:\n")
        f.write(response)
    sys.stdout.write(f"Logged query/response to {filename}\n")


def get_common_indentation(lines: List[str]) -> str:
    """
    Compute the common leading whitespace of the first non-empty line in a list.
    """
    for line in lines:
        if line.strip():
            m = re.match(r"(\s*)", line)
            if m:
                return m.group(1)
    return ""


def reindent(text: str, indent: str) -> str:
    """
    Reapply the given indentation to every non-empty line in the text.

    Args:
        text (str): The text to reindent.
        indent (str): The indentation string (e.g. spaces) to prepend.

    Returns:
        str: The reindented text.
    """
    lines = text.splitlines()
    reindented_lines = [(indent + line) if line.strip() else line for line in lines]
    return "\n".join(reindented_lines)


def annotate_conflict_markers(text: str) -> str:
    """
    Annotate the conflict markers in the provided text so that they are more explicit.

    For every line that begins with:
      - "<<<<<<<" it appends " (Current Change)"
      - "|||||||" it appends " (base)"
      - ">>>>>>>" it appends " (Incoming Change)"

    This helps the LLM clearly understand the source of each conflict segment.

    Args:
        text (str): The text containing merge conflicts.

    Returns:
        str: The annotated text.
    """
    annotated_lines = []
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("<<<<<<<"):
            line = (
                line.rstrip("\n")
                + " (Current Change, these are the current changes in your branch)\n"
            )
        elif stripped.startswith("|||||||"):
            line = (
                line.rstrip("\n")
                + " (Base Version, this is the most recent common ancestor)\n"
            )
        elif stripped.startswith(">>>>>>>"):
            line = (
                line.rstrip("\n")
                + " (Incoming Change, these are the changes from the branch you are merging)\n"
            )
        annotated_lines.append(line)
    return "".join(annotated_lines)


def process_file(filename: str, llm_model: str) -> None:
    """
    Process a file containing merge conflicts, attempt to resolve each conflict using an LLM,
    and write the modified content back to the file.

    For each conflict, the script now extracts a snippet containing the conflict block plus
    n (default 5) lines of context before and after. The snippet is passed to the LLM with an
    instruction to resolve the merge conflict and output the entire snippet (including context)
    in markdown code fences. The entire snippet (as returned by the LLM) then replaces the original
    snippet in the file.

    Args:
        filename (str): The path to the file to process.
        llm_model (str): The LLM model to use for conflict resolution.
    """
    with open(filename, "r", encoding="utf-8") as f:
        lines: List[str] = f.readlines()

    # Regular expressions for detecting conflict markers.
    conflict_start_re = re.compile(r"^<<<<<<< ")
    conflict_end_re = re.compile(r"^>>>>>>> ")

    new_lines: List[str] = []
    n = 5  # Number of context lines before and after the conflict block.
    conflict_count = 0
    last_appended_index = 0
    i = 0

    while i < len(lines):
        if conflict_start_re.match(lines[i]):
            # Found a conflict block. Identify the full block.
            conflict_block_start_index = i
            conflict_block: List[str] = []
            while i < len(lines) and not conflict_end_re.match(lines[i]):
                conflict_block.append(lines[i])
                i += 1
            if i < len(lines):
                conflict_block.append(lines[i])
                # Include the conflict end marker line.
                conflict_block_end_index = i + 1
                i += 1
            else:
                conflict_block_end_index = i

            # Determine the snippet range including n lines of context before and after.
            snippet_start = max(last_appended_index, conflict_block_start_index - n)
            snippet_end = min(len(lines), conflict_block_end_index + n)

            # Append unchanged lines from the last index up to the snippet start.
            new_lines.extend(lines[last_appended_index:snippet_start])
            snippet_lines = lines[snippet_start:snippet_end]
            snippet = "".join(snippet_lines)

            # Annotate conflict markers in the snippet.
            annotated_snippet = annotate_conflict_markers(snippet)

            # Build the prompt instructing the LLM to resolve the conflict and output the entire snippet.
            prompt: str = (
                "You are a semantic merge conflict resolution expert. Below is a code snippet that includes several lines of context "
                "before and after a merge conflict. The context is provided to help you understand the semantics of the code. "
                "Please resolve the merge conflict and output the entire snippet (including the context lines) with the conflict resolved, "
                "enclosed in markdown code fences. If you are uncertain about the correct resolution, please explain the ambiguity and do not output any code.\n"
                f"{annotated_snippet}"
            )

            llm_response = call_llm(prompt, llm_model)
            if llm_response is None:
                sys.stderr.write(
                    "LLM returned no response. Keeping original snippet.\n"
                )
                new_lines.extend(snippet_lines)
            else:
                # Extract the code portion from the LLM response.
                merged_result = extract_code_from_response(llm_response)
                merged_lines = merged_result.splitlines()

                # Compute common indentation from the original snippet.
                common_indent = get_common_indentation(snippet_lines)
                for line in merged_lines:
                    if line.strip():
                        if re.match(r"^\S", line):
                            merged_result = reindent(merged_result, common_indent)
                        break

                # If the merged result is identical to the original snippet, leave it unchanged.
                if merged_result.rstrip("\n") == snippet.rstrip("\n"):
                    new_lines.extend(snippet_lines)
                else:
                    if not merged_result.endswith("\n"):
                        merged_result += "\n"
                    new_lines.append(merged_result)

            conflict_count += 1
            safe_filename = os.path.basename(filename).replace(" ", "_")
            conflict_id = f"{safe_filename}_conflict_{conflict_count}"
            log_query_response(
                prompt, llm_response if llm_response is not None else "", conflict_id
            )

            last_appended_index = snippet_end
        else:
            i += 1

    # Append any remaining lines after the last processed snippet.
    if last_appended_index < len(lines):
        new_lines.extend(lines[last_appended_index:])

    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def main() -> None:
    """
    Main entry point of the script.
    """
    if len(sys.argv) != 3:
        sys.stderr.write("Usage: ./resolve_conflicts.py <filename> <llm_model>\n")
        sys.exit(2)
    filename = sys.argv[1]
    llm_model = sys.argv[2]
    process_file(filename, llm_model)


if __name__ == "__main__":
    main()
