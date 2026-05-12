#!/usr/bin/env python3
"""
Cross-model solution verifier — re-solves task with a DIFFERENT model than
the one that generated it. Independent-model agreement = strong signal of
correctness. Disagreement → flag for human review.

Usage:
    python verifier.py <md_path>                     # verify single MD
    python verifier.py --dir vault/math_profile      # recursive
    python verifier.py --dir vault --flag-only       # print only mismatches
    python verifier.py --dir vault --model google/gemini-2.5-flash
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from llm import make_client, complete, complete_tracked, get_verifier_model
from db import connect

load_dotenv()


# === START_STRIP_CALLOUT_PREFIX_VERIFY ===
def _strip_callout(block: str) -> str:
    """Drop leading '> ' / '>' from each line of a callout body."""
    out = []
    for line in block.splitlines():
        if line.startswith("> "):
            out.append(line[2:])
        elif line.startswith(">"):
            out.append(line[1:])
        else:
            out.append(line)
    return "\n".join(out).strip()
# === END_STRIP_CALLOUT_PREFIX_VERIFY ===


# === START_PARSE_GENERATED_MD_VERIFY ===
def parse_md(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    result = {"task": "", "answer": "", "subject": "", "kes": ""}

    fm = re.match(r"---\n(.*?)\n---", text, re.DOTALL)
    if fm:
        for line in fm.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                result[k.strip()] = v.strip().strip('"')

    m = re.search(r"\[!question\][+\-]?\s*Условие\s*\n(.*?)(?=\n##|\n>\s*\[!|\Z)", text, re.DOTALL)
    if m:
        result["task"] = _strip_callout(m.group(1))
    else:
        m = re.search(r"## Задание\s*\n(.*?)## Решение", text, re.DOTALL)
        if m:
            result["task"] = _strip_callout(m.group(1))

    m = re.search(r"\[!success\]\s*Ответ\s*\n((?:>\s*.*\n?)+)", text)
    if m:
        result["answer"] = _strip_callout(m.group(1))
    else:
        m = re.search(r"\*\*Ответ:\*\*\s*(.+?)\n", text)
        if m:
            result["answer"] = m.group(1).strip()

    return result
# === END_PARSE_GENERATED_MD_VERIFY ===


# === START_NORMALIZE_VERIFY_ANSWER ===
def normalize(ans: str) -> str:
    a = ans.lower().strip()
    a = re.sub(r"[\s$\\]", "", a)
    a = a.replace(",", ".").replace(";", ",")
    a = re.sub(r"\\left|\\right|\\,|\\;", "", a)
    a = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"\1/\2", a)
    return a
# === END_NORMALIZE_VERIFY_ANSWER ===


# === START_ASK_VERIFIER_LLM ===
def verify(task_text: str, client, model: str) -> tuple[str, str, float | None, int]:
    prompt = f"""Реши задачу ЕГЭ. Сначала кратко реши, затем на отдельной строке дай финальный ответ.

Задача:
{task_text}

Формат:
<краткое решение>
ОТВЕТ: <ответ>"""

    result = complete_tracked(client, model, prompt, max_tokens=8192, temperature=0.1)
    m = re.search(r"ОТВЕТ:\s*(.+?)(?=\n|$)", result["text"])
    answer = m.group(1).strip() if m else ""
    return answer, result["text"], result["cost_usd"], result["latency_ms"]
# === END_ASK_VERIFIER_LLM ===


# === START_VERIFY_SINGLE_FILE ===
def verify_file(md: Path, client, model: str, flag_only: bool = False) -> bool:
    parsed = parse_md(md)
    if not parsed["task"] or not parsed["answer"]:
        if not flag_only:
            print(f"  SKIP {md.name}: missing task or answer")
        return True

    try:
        verified, raw, cost_usd, latency_ms = verify(parsed["task"], client, model)
    except Exception as e:
        print(f"  ERR  {md.name}: {e}")
        return True

    match = normalize(verified) == normalize(parsed["answer"])

    c = connect()
    c.execute(
        """INSERT OR REPLACE INTO verifications
           (md_path, ts, model, claimed_answer, verified_answer, match,
            verifier_output, cost_usd, latency_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (str(md.resolve()), datetime.now().isoformat(timespec="seconds"),
         model, parsed["answer"], verified, int(match), raw,
         cost_usd, latency_ms),
    )
    c.commit()
    c.close()

    flag = "✓" if match else "✗ MISMATCH"
    if not flag_only or not match:
        print(f"  {flag}  {md.name}")
        if not match:
            print(f"     claimed:  {parsed['answer'][:80]}")
            print(f"     verified: {verified[:80]}")
    return match
# === END_VERIFY_SINGLE_FILE ===


# === START_RUN_VERIFIER_CLI ===
def main():
    p = argparse.ArgumentParser()
    p.add_argument("path", nargs="?", help="Single MD file")
    p.add_argument("--dir", help="Verify all .md in dir recursively")
    p.add_argument("--flag-only", action="store_true")
    p.add_argument("--model", help="Override verifier model")
    p.add_argument("--skip-verified", action="store_true",
                   help="Skip files already in verifications table")
    args = p.parse_args()

    client = make_client()
    model = args.model or get_verifier_model()
    print(f"Verifier model: {model}")

    if args.skip_verified:
        c = connect()
        done = {r[0] for r in c.execute("SELECT md_path FROM verifications").fetchall()}
        c.close()
    else:
        done = set()

    if args.dir:
        files = sorted(Path(args.dir).rglob("*.md"))
        files = [f for f in files
                 if str(f.resolve()) not in done
                 and "_moc" not in f.parts
                 and "_templates" not in f.parts]
        print(f"Verifying {len(files)} files")
        ok = 0
        for f in files:
            if verify_file(f, client, model, args.flag_only):
                ok += 1
        print(f"\n{ok}/{len(files)} matched")
    elif args.path:
        verify_file(Path(args.path), client, model, args.flag_only)
    else:
        sys.exit("Provide path or --dir")


if __name__ == "__main__":
    main()
# === END_RUN_VERIFIER_CLI ===
