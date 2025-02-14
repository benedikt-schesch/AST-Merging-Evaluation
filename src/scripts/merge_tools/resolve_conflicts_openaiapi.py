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
from typing import Optional


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
            api_key=api_key, base_url="https://openrouter.ai/api/v1"
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
                + " (Left Branch, these are the changes on the left branch)\n"
            )
        elif stripped.startswith("|||||||"):
            line = (
                line.rstrip("\n")
                + " (Base Version, this is the most recent common ancestor)\n"
            )
        elif stripped.startswith(">>>>>>>"):
            line = (
                line.rstrip("\n")
                + " (Right Branch, these are the changes on the right branch)\n"
            )
        annotated_lines.append(line)
    return "".join(annotated_lines)


def process_file(filename: str, llm_model: str) -> None:
    """
    Process the full file containing merge conflicts by sending the entire file content to the LLM.
    The prompt instructs the LLM to resolve the conflicts, modifying only the conflict sections and
    minimizing any other changes. The full resolved file (enclosed in markdown code fences) is then written
    back to the file.
    """
    with open(filename, "r", encoding="utf-8") as f:
        file_content = f.read()

    # Annotate the conflict markers to help the LLM understand what each section represents.
    annotated_file = annotate_conflict_markers(file_content)

    prompt = (
        "You are a semantic merge conflict resolution expert. Below is the full content of a file that contains "
        "Git merge conflicts marked with '<<<<<<<', '|||||||', and '>>>>>>>' "
        "indicating the different versions of the conflicted sections.\n"
        "Please resolve these conflicts by choosing the correct changes. Modify only the conflicted sections "
        "and leave all other parts of the file EXACTLY as they are.\n"
        "Return the resolved conflict within markdown code fences (``` ... ```).\n"
        "If you are unsure about how to properly resolve a conflict, you can leave the conflict marker in as-is.\n"
        "Here is the file content:\n"
        "```\n"
        f"{annotated_file}\n"
        "```\n"
    )

    if len(prompt) > 30000:
        sys.stderr.write(
            "The prompt is too long. The maximum prompt length is 40,000 characters.\n"
        )
        return

    llm_response = call_llm(prompt, llm_model)
    if llm_response is None:
        sys.stderr.write("DeepSeek API returned no response. Keeping original file.\n")
        return

    # Extract the code block from the response.
    resolved_file = extract_code_from_response(llm_response)

    # Write the resolved file back.
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
