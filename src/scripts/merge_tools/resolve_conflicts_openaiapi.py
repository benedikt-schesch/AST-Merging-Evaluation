#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resolve_conflicts.py

Usage:
    ./resolve_conflicts.py <filename> <llm_model>

This script processes a file that contains Git merge conflicts (in diff3 style)
and attempts to resolve each conflict block individually using the DeepSeek API via the OpenAI SDK.
For each conflict, context is expanded upward and downward until a stopping condition is met:
  - The 3rd empty line (only spaces or tabs count as empty)
  - A line that contains a bracket '{' or '}'
  - A line that starts with "def " or "class "
  - Another conflict marker is encountered (e.g., <<<<<<<, |||||||, or >>>>>>>)
  - The file boundary is reached

If the LLM is not confident about a resolution, the original snippet is retained.
A caching mechanism is implemented so that if the same prompt is sent for the same model,
the script will use the cached response rather than making a new API call.
The cache is stored in the directory structure: queries_cache/<llm_model>/<prompt_hash>.cache

Requirements:
    - pip install openai
    - Set the environment variable DEEPSEEK_API_KEY with your DeepSeek API key.
"""

import os
import re
import sys
import hashlib
from openai import OpenAI
from typing import Optional, List, Tuple


def get_cache_filepath(prompt: str, llm_model: str) -> str:
    """
    Construct the file path for a cached response given the prompt and model.

    The path is structured as:
      queries_cache/<llm_model>/<prompt_hash>.cache

    Args:
        prompt (str): The prompt text.
        llm_model (str): The LLM model name.

    Returns:
        str: The full path to the cache file.
    """
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    cache_dir = os.path.join("queries_cache", llm_model)
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{prompt_hash}.cache")


def call_llm(prompt: str, llm_model: str) -> Optional[str]:
    """
    Call the DeepSeek API (compatible with the OpenAI API) with the provided prompt.
    Uses a file-based caching mechanism so that if the same prompt is sent to the same model,
    the cached response is returned.

    The API key must be set in the DEEPSEEK_API_KEY environment variable.

    Args:
        prompt (str): The prompt to send to the LLM.
        llm_model (str): The name of the LLM model to use.

    Returns:
        Optional[str]: The response content from the LLM, or None if an error occurred.
    """
    cache_filepath = get_cache_filepath(prompt, llm_model)
    print(f"Cache file path: {cache_filepath}")

    # Check for cached response.
    if os.path.exists(cache_filepath):
        sys.stdout.write("Cache hit for prompt.\n")
        try:
            with open(cache_filepath, "r", encoding="utf-8") as cache_file:
                cached_content = cache_file.read()
            # Extract the reply from the cached file.
            reply_match = re.search(
                r"---BEGIN REPLY---\n(.*?)\n---END REPLY---", cached_content, re.DOTALL
            )
            if reply_match:
                print("Using cached response.")
                return reply_match.group(1)
            else:
                sys.stderr.write("Cache file format incorrect. Ignoring cache.\n")
        except Exception as e:
            sys.stderr.write(f"Error reading cache file: {e}\n")

    # Ensure the API key is set.
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if api_key is None:
        sys.stderr.write("Please set the DEEPSEEK_API_KEY environment variable.\n")
        return None

    try:
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        response = client.chat.completions.create(
            model=llm_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a semantic merge conflict resolution expert.",
                },
                {"role": "user", "content": prompt},
            ],
            stream=False,
        )
        llm_response = response.choices[0].message.content

        # Cache the prompt and response.
        with open(cache_filepath, "w", encoding="utf-8") as cache_file:
            cache_file.write("---BEGIN PROMPT---\n")
            cache_file.write(prompt)
            cache_file.write("\n---END PROMPT---\n")
            cache_file.write("---BEGIN REPLY---\n")
            cache_file.write(llm_response)
            cache_file.write("\n---END REPLY---\n")

        return llm_response
    except Exception as e:
        sys.stderr.write(f"Error calling DeepSeek API: {e}\n")
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
    fence_match = re.search(r"```(?:[^\n]*\n)?(.*?)```", response, re.DOTALL)
    if fence_match:
        return fence_match.group(1)
    else:
        print("No code fence found in LLM response. Not modifying any code.")
        sys.exit(1)


def contains_conflict_marker(line: str) -> bool:
    return "<<<<<<<" in line or "|||||||" in line or ">>>>>>>" in line


def extract_conflict_with_context(
    lines: List[str], conflict_start: int, conflict_end: int
) -> Tuple[int, int]:
    """
    Expand upward and downward from a conflict block to include context lines,
    then compress away extraneous blank/brace-only lines.

    Stop expansion for each direction when encountering:
      1. The 3rd empty line (only spaces or tabs count as empty).
      2. The second occurrence of a bracket ('{' or '}'). (One bracket is allowed.)
      3. A line that starts with "def " or "class ".
      4. Another conflict marker (e.g., <<<<<<<, |||||||, or >>>>>>>).
      5. The file boundary is reached.

    After expansion:
      - Compress downward from the top boundary if the line is empty or just '{'.
      - Compress upward from the bottom boundary if the line is empty or just '{'.
      - Finally, remove the trailing newline from the bottom line.
    """

    # -----------------------
    # 1) Expand upward
    # -----------------------
    context_start = conflict_start
    empty_count = 0
    bracket_count = 0  # Count of encountered lines with a bracket.
    for i in range(conflict_start - 1, -1, -1):
        line = lines[i]
        # If we hit another conflict marker, stop
        if contains_conflict_marker(line):
            break
        # If line is empty
        if line.strip() == "":
            empty_count += 1
            if empty_count >= 3:
                break
        # If starts with def/class, stop
        if line.lstrip().startswith("def ") or line.lstrip().startswith("class "):
            break
        # If we see '{' or '}', and we've already encountered one, stop
        if "{" in line or "}" in line:
            if bracket_count >= 1:
                break
            else:
                bracket_count += 1

        context_start = i  # Expand the window

    # -----------------------
    # 2) Compress downward from the top boundary
    #    i.e., remove consecutive lines (up to conflict_start)
    #    that are empty or just '{'
    # -----------------------
    while context_start < conflict_start:
        top_line = lines[context_start].strip()
        if top_line == "" or top_line == "{":
            context_start += 1
        else:
            break

    # -----------------------
    # 3) Expand downward
    # -----------------------
    context_end = conflict_end
    empty_count = 0
    bracket_count = 0  # Reset for downward expansion.
    for i in range(conflict_end + 1, len(lines)):
        line = lines[i]
        # If we hit another conflict marker, stop
        if contains_conflict_marker(line):
            break
        # If line is empty
        if line.strip() == "":
            empty_count += 1
            if empty_count >= 3:
                break
        # If starts with def/class, stop
        if line.lstrip().startswith("def ") or line.lstrip().startswith("class "):
            break
        # If we see '{' or '}', and we've already encountered one, stop
        if "{" in line or "}" in line:
            if bracket_count >= 1:
                break
            else:
                bracket_count += 1

        context_end = i  # Expand the window

    # -----------------------
    # 4) Compress upward from the bottom boundary
    #    i.e., remove consecutive lines (down to conflict_end)
    #    that are empty or just '{'
    # -----------------------
    while context_end > conflict_end:
        bottom_line = lines[context_end].strip()
        if bottom_line == "" or bottom_line == "{":
            context_end -= 1
        else:
            break

    # -----------------------
    # 5) Strip trailing newline from the bottom line
    #    (so the final line in the snippet has no extra "\n")
    # -----------------------
    # We only do this if context_end is within bounds
    if 0 <= context_end < len(lines):
        lines[context_end] = lines[context_end].rstrip("\n")

    return context_start, context_end


def process_file(filename: str, llm_model: str) -> None:
    """
    Process the file containing merge conflicts.
    For each conflict in the file, extract a block with contextual lines,
    send it to the LLM for resolution, and replace the original block with the resolved block.
    """
    with open(filename, "r", encoding="utf-8") as f:
        file_content = f.read()

    lines = file_content.splitlines(keepends=True)
    conflict_blocks = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("<<<<<<<"):
            conflict_start = i
            # Find the end of the conflict block.
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith(">>>>>>>"):
                j += 1
            if j < len(lines):
                conflict_end = j
                conflict_blocks.append((conflict_start, conflict_end))
                i = j + 1
            else:
                # No end marker found; break out.
                break
        else:
            i += 1

    # Process conflicts from last to first to avoid index shifting.
    for conflict_start, conflict_end in reversed(conflict_blocks):
        context_start, context_end = extract_conflict_with_context(
            lines, conflict_start, conflict_end
        )
        conflict_block_with_context = "".join(lines[context_start : context_end + 1])

        prompt = (
            "You are a semantic merge conflict resolution expert. Below is a snippet of code "
            "with surrounding context that includes a merge conflict.\n"
            "Return the entire snippet (including full context) in markdown code fences as provided, make sure you do not modify the context at all and preserve the spacing as is.\n"
            "Think in terms of intent and semantics that both sides of the merge are trying to achieve.\n"
            "If you are not sure on how to resolve the conflict or if the intent is ambiguous, please return the same snippet with the conflict.\n"
            "Here is the code snippet:\n"
            "```java\n"
            f"{conflict_block_with_context}\n"
            "```\n"
        )

        # Check prompt length.
        if len(prompt) > 30000:
            sys.stderr.write("The prompt is too long. Skipping this conflict.\n")
            continue

        llm_response = call_llm(prompt, llm_model)
        if llm_response is None:
            sys.stderr.write(
                "DeepSeek API returned no response. Keeping original block.\n"
            )
            continue

        resolved_block = extract_code_from_response(llm_response)

        # If the resolved block still contains conflict markers, exit with code 1.
        if contains_conflict_marker(resolved_block):
            sys.stderr.write(
                "Conflict markers detected in the resolved block. Exiting with code 1.\n"
            )
            sys.exit(1)

        # Split the resolved block into lines (preserving newlines).
        resolved_lines = [line + "\n" for line in resolved_block.splitlines()]
        # Replace the original block in the lines list.
        lines = lines[:context_start] + resolved_lines + lines[context_end + 1 :]

    resolved_file = "".join(lines)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(resolved_file)


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
