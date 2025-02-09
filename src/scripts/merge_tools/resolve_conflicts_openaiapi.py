#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resolve_conflicts.py

Usage:
    ./resolve_conflicts.py <filename> <llm_model>

This script processes a file that contains Git merge conflicts (in diff3 style)
and attempts to resolve each conflict block using the DeepSeek API via the OpenAI SDK.
If the LLM is not confident about a resolution, the original snippet (which now
includes additional context) is retained.

A caching mechanism is implemented so that if the same prompt is sent for the same model,
the script will use the cached response rather than making a new API call.
The cache is stored in the directory structure: cache/queries/<model_name>/<prompt_hash>.cache

Requirements:
    - pip install openai
    - Set the environment variable DEEPSEEK_API_KEY with your DeepSeek API key.
"""

import os
import re
import sys
import hashlib
from openai import OpenAI
from typing import List, Optional


def get_cache_filepath(prompt: str, llm_model: str) -> str:
    """
    Construct the file path for a cached response given the prompt and model.

    The path is structured as:
      cache/queries/<llm_model>/<prompt_hash>.cache

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
        llm_model (str): The name of the LLM model to use (e.g., "deepseek-chat" or "deepseek-reasoner").

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
            # The cache file is in plain text and has both the prompt and reply.
            # We extract the reply between the markers.
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

    # Use the DeepSeek API endpoint (compatible with OpenAI's API)
    # TODO: The 'openai.api_base' option isn't read in the client API. You will need to pass it when you instantiate the client, e.g. 'OpenAI(base_url="https://api.deepinfra.com/v1/openai")'
    # openai.api_base = "https://api.deepinfra.com/v1/openai"

    try:
        client = OpenAI(
            api_key=api_key, base_url="https://api.deepinfra.com/v1/openai"
        )  # Make sure to install via: pip install openai

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

        # Save the prompt and response to the cache file in plain text with markers.
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
    # Try to find a markdown code fence block.
    fence_match = re.search(r"```(?:[^\n]*\n)?(.*?)```", response, re.DOTALL)
    if fence_match:
        return fence_match.group(1)
    else:
        print("No code fence found in LLM response. Not modifying any code.")
        sys.exit(1)


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
    Process a file containing merge conflicts, attempt to resolve each conflict using the DeepSeek API,
    and write the modified content back to the file.

    For each conflict, the script now extracts a snippet containing the conflict block plus
    n (default 5) lines of context before and after. The snippet is passed to the LLM with an
    instruction to resolve the merge conflict and output the entire snippet (including context)
    in markdown code fences. The entire snippet (as returned by the LLM) then replaces the original
    snippet in the file.

    Args:
        filename (str): The path to the file to process.
        llm_model (str): The DeepSeek model to use for conflict resolution (e.g., "deepseek-chat" or "deepseek-reasoner").
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

            # If the snippet's trailing context includes the start of another conflict block,
            # trim it so that only one conflict is included in the snippet.
            for j in range(conflict_block_end_index, snippet_end):
                if conflict_start_re.match(lines[j]):
                    snippet_end = j
                    break

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
                "Please resolve the merge conflict and output the entire snippet (including the context lines but nothing more) with the conflict resolved, "
                "enclosed in markdown code fences. If you are uncertain about the correct resolution, please explain the ambiguity and do not output any code.\n"
                "```\n"
                f"{annotated_snippet}"
                "```\n"
            )

            llm_response = call_llm(prompt, llm_model)
            if llm_response is None:
                sys.stderr.write(
                    "DeepSeek API returned no response. Keeping original snippet.\n"
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
