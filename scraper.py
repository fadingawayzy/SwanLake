#!/usr/bin/env python3
"""
ЕГЭ task scraper from ФИПИ open bank.
Scrapes 4 subjects: math profile, physics, informatics, russian.
Output: JSON files per subject in ./data/
"""

import os
import requests
import json
import time
import re
import warnings
from pathlib import Path
from bs4 import BeautifulSoup
from mathml_to_latex import extract_latex_from_block

INSECURE = os.environ.get("EGE_SCRAPER_INSECURE") == "1"
if INSECURE:
    warnings.filterwarnings("ignore")
    print("WARN: SSL verification disabled via EGE_SCRAPER_INSECURE=1")

BASE = "https://ege.fipi.ru/bank"

SUBJECTS = {
    "math_profile":  "AC437B34557F88EA4115D2F374B0A07B",
    "russian":       "AF0ED3F2557F8FFC4C06F80B6803FD26",
    "physics":       "BA1F39653304A5B041B656915DC36B38",
    "informatics":   "B9ACA5BBB2E19E434CD6BEC25284C67F",
}

OUT = Path("data")
OUT.mkdir(exist_ok=True)


def make_session(proj_id: str) -> requests.Session:
    s = requests.Session()
    s.verify = not INSECURE
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ru-RU,ru;q=0.9",
    })
    s.get(f"{BASE}/index.php?proj={proj_id}", timeout=15)
    return s


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ").replace(" ", " ").replace(" ", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_metadata(soup: BeautifulSoup, hash_id: str) -> dict:
    """Extract КЭС and answer format from the sibling info div."""
    info_div = soup.find(id=f"i{hash_id}")
    if not info_div:
        return {"kes": "", "answer_format": ""}

    kes_parts = []
    answer_format = ""

    rows = info_div.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        label = clean_text(cells[0].get_text())
        value_cell = cells[1]

        if "КЭС" in label:
            for div in value_cell.find_all("div"):
                text = clean_text(div.get_text())
                if text:
                    kes_parts.append(text)
        elif "Тип ответа" in label:
            answer_format = clean_text(value_cell.get_text())

    return {
        "kes": "; ".join(kes_parts),
        "answer_format": answer_format,
    }


def extract_task_number(answer_type: str) -> str:
    """Extract task number like '№5' from answer_type string."""
    m = re.search(r"Задание\s*№(\d+)", answer_type)
    return m.group(1) if m else ""


def parse_questions(html_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(html_bytes, "lxml", from_encoding="windows-1251")
    blocks = soup.find_all(class_="qblock")
    results = []

    for block in blocks:
        qid = block.get("id", "")
        if not qid.startswith("q"):
            continue
        hash_id = qid[1:]

        # Answer type hint
        hint = block.find(id="hint")
        answer_type = clean_text(hint.get_text()) if hint else ""

        # Problem text — plain + LaTeX-enriched versions
        form = block.find(id=f"checkform{hash_id}")
        problem_text = ""
        latex_text = ""
        if form:
            cells = form.find_all("td", class_="cell_0")
            if cells:
                problem_text = clean_text(cells[0].get_text())
            else:
                problem_text = clean_text(form.get_text())
            latex_text = extract_latex_from_block(form)

        # Metadata from sibling div (search soup-wide)
        meta = parse_metadata(soup, hash_id)
        task_number = extract_task_number(answer_type)

        if problem_text:
            results.append({
                "id": hash_id,
                "task_number": task_number,
                "answer_type": answer_type,
                "text": problem_text,
                "latex_text": latex_text,
                "kes": meta["kes"],
                "answer_format": meta["answer_format"],
            })

    return results


def get_total_pages(session: requests.Session, proj_id: str) -> int:
    r = session.get(
        f"{BASE}/questions.php?proj={proj_id}&init_filter_themes=1",
        timeout=15
    )
    html = r.content.decode("windows-1251", errors="replace")
    # Count embedded as JS call: setQCount(978)
    m = re.search(r"setQCount\((\d+)\)", html)
    if m:
        total = int(m.group(1))
        pages = (total + 9) // 10
        print(f"  Total tasks: {total}, pages: {pages}")
        return pages
    return 1


def scrape_subject(name: str, proj_id: str) -> list[dict]:
    print(f"\n=== {name} (proj={proj_id}) ===")
    session = make_session(proj_id)

    total_pages = get_total_pages(session, proj_id)
    print(f"  Total pages: {total_pages}")

    all_tasks = []
    for page in range(1, total_pages + 1):
        url = f"{BASE}/questions.php?proj={proj_id}&page={page}"
        try:
            r = session.get(url, timeout=15)
            tasks = parse_questions(r.content)
            all_tasks.extend(tasks)
            print(f"  Page {page}/{total_pages}: {len(tasks)} tasks (total={len(all_tasks)})")
        except Exception as e:
            print(f"  Page {page} ERROR: {e}")

        time.sleep(0.3)  # polite delay

    return all_tasks


def main():
    for name, proj_id in SUBJECTS.items():
        out_file = OUT / f"{name}.json"

        # Skip if already scraped
        if out_file.exists():
            existing = json.loads(out_file.read_text())
            print(f"SKIP {name}: {len(existing)} tasks already in {out_file}")
            continue

        tasks = scrape_subject(name, proj_id)

        out_file.write_text(
            json.dumps(tasks, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"  Saved {len(tasks)} tasks -> {out_file}")


if __name__ == "__main__":
    main()
