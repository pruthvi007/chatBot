#!/usr/bin/env python3
"""
Unzip a .zip file, send each text file to OpenAI for code review,
and write the results to an Excel (.xlsx) file with columns:
fileName, review comments.
"""

import argparse
import os
import sys
import time
import zipfile
from typing import Iterable, List, Optional, Tuple

from openai import OpenAI
from openai import APIError, APITimeoutError, RateLimitError
from openpyxl import Workbook


DEFAULT_SYSTEM_PROMPT = "You are a senior software engineer performing a code review."
DEFAULT_USER_PROMPT = (
    "Review the file below and provide concise, actionable comments. "
    "Focus on correctness, security, performance, and maintainability. "
    "If no issues are found, respond with 'No issues found.'"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review code in a zip file using OpenAI and write results to Excel."
        )
    )
    parser.add_argument(
        "zip_path",
        help="Path to the .zip file containing code to review.",
    )
    parser.add_argument(
        "--output",
        default="code_review.xlsx",
        help="Output Excel file path (default: code_review.xlsx).",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model to use (default: gpt-4o-mini).",
    )
    parser.add_argument(
        "--max-file-chars",
        type=int,
        default=0,
        help=(
            "If set to a positive number, skip files with more characters "
            "than this limit."
        ),
    )
    parser.add_argument(
        "--sleep-between",
        type=float,
        default=0.0,
        help="Seconds to sleep between API requests (default: 0).",
    )
    return parser.parse_args()


def is_probably_binary(data: bytes) -> bool:
    if not data:
        return False
    if b"\x00" in data:
        return True

    sample = data[:2048]
    text_bytes = set(range(32, 127)) | {9, 10, 13}
    nontext = sum(1 for b in sample if b not in text_bytes)
    return (nontext / len(sample)) > 0.30


def decode_text(data: bytes) -> Optional[str]:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("latin-1")
        except UnicodeDecodeError:
            return None


def iter_zip_text_files(
    zip_path: str, max_file_chars: int
) -> Iterable[Tuple[str, Optional[str], Optional[str]]]:
    with zipfile.ZipFile(zip_path) as zip_file:
        for info in zip_file.infolist():
            if info.is_dir():
                continue

            file_path = info.filename
            if file_path.startswith("__MACOSX/"):
                continue
            if os.path.basename(file_path).startswith("."):
                continue

            with zip_file.open(info) as file_handle:
                data = file_handle.read()

            if is_probably_binary(data):
                yield file_path, None, "Skipped: binary or unsupported encoding."
                continue

            text = decode_text(data)
            if text is None:
                yield file_path, None, "Skipped: binary or unsupported encoding."
                continue

            if max_file_chars > 0 and len(text) > max_file_chars:
                yield file_path, None, "Skipped: file exceeds max-file-chars."
                continue

            yield file_path, text, None


def build_prompt(file_path: str, content: str) -> str:
    _, ext = os.path.splitext(file_path)
    lang_hint = ext.lstrip(".") if ext else ""
    return (
        f"{DEFAULT_USER_PROMPT}\n\nFile: {file_path}\n\n"
        f"```{lang_hint}\n{content}\n```"
    )


def call_openai_with_retries(
    client: OpenAI, model: str, prompt: str, max_retries: int = 3
) -> str:
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            return response.choices[0].message.content.strip()
        except (RateLimitError, APITimeoutError, APIError) as exc:
            if attempt >= max_retries:
                raise
            backoff = 2 ** attempt
            print(
                f"OpenAI error: {exc}. Retrying in {backoff}s...",
                file=sys.stderr,
            )
            time.sleep(backoff)

    raise RuntimeError("OpenAI request failed after retries.")


def write_excel(results: List[Tuple[str, str]], output_path: str) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Code Review"
    sheet.append(["fileName", "review comments"])
    for file_name, review in results:
        sheet.append([file_name, review])
    workbook.save(output_path)


def main() -> int:
    args = parse_args()
    if not os.path.isfile(args.zip_path):
        print(f"Zip file not found: {args.zip_path}", file=sys.stderr)
        return 1

    try:
        zipfile.ZipFile(args.zip_path).close()
    except zipfile.BadZipFile:
        print(f"Invalid zip file: {args.zip_path}", file=sys.stderr)
        return 1

    client = OpenAI()
    results: List[Tuple[str, str]] = []

    for file_path, content, skip_reason in iter_zip_text_files(
        args.zip_path, args.max_file_chars
    ):
        if skip_reason:
            results.append((file_path, skip_reason))
            continue

        print(f"Reviewing {file_path}...", file=sys.stderr)
        prompt = build_prompt(file_path, content)
        try:
            review = call_openai_with_retries(client, args.model, prompt)
        except Exception as exc:  # pragma: no cover - best effort reporting
            review = f"Error during review: {exc}"
        results.append((file_path, review))

        if args.sleep_between > 0:
            time.sleep(args.sleep_between)

    write_excel(results, args.output)
    print(f"Saved review results to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
