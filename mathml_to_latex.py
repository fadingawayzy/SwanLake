"""MathML → LaTeX converter for ФИПИ ЕГЭ tasks."""

from bs4 import BeautifulSoup, Tag, NavigableString

OPERATOR_MAP = {
    "−": "-", "–": "-", "·": r"\cdot", "×": r"\times",
    "√": r"\sqrt", "∞": r"\infty", "±": r"\pm", "∓": r"\mp",
    "≤": r"\leq", "≥": r"\geq", "≠": r"\neq", "≈": r"\approx",
    "∈": r"\in", "∉": r"\notin", "⊂": r"\subset", "∪": r"\cup",
    "∩": r"\cap", "∅": r"\emptyset", "→": r"\to",
    "π": r"\pi", "α": r"\alpha", "β": r"\beta", "γ": r"\gamma",
    "δ": r"\delta", "θ": r"\theta", "φ": r"\varphi", "ω": r"\omega",
    "Δ": r"\Delta", "∑": r"\sum", "∫": r"\int", "∂": r"\partial",
    "⟨": r"\langle", "⟩": r"\rangle",
    " ": " ", " ": " ", " ": " ", "⁠": "",
}


def _tag_name(el) -> str:
    if not isinstance(el, Tag):
        return ""
    name = el.name or ""
    return name.split(":")[-1].lower()


def _tag_kids(el):
    """Only Tag children, no whitespace NavigableStrings."""
    return [c for c in el.children if isinstance(c, Tag)]


def convert(el) -> str:
    if isinstance(el, NavigableString):
        t = str(el)
        for k, v in OPERATOR_MAP.items():
            t = t.replace(k, v)
        return t.strip()

    if not isinstance(el, Tag):
        return ""

    name = _tag_name(el)

    def cjoin(els=None) -> str:
        src = _tag_kids(el) if els is None else els
        return "".join(convert(c) for c in src).strip()

    # Pass-through containers
    if name in ("math", "semantics", "mstyle", "mpadded", "mphantom",
                "merror", "maction", "mrow", "annotation-xml"):
        return cjoin()

    if name == "annotation":
        return ""  # skip TeX annotation — we build our own

    if name in ("mi", "mn"):
        t = el.get_text()
        return OPERATOR_MAP.get(t, t)

    if name == "mo":
        t = el.get_text().strip()
        mapped = OPERATOR_MAP.get(t, t)
        return " " + mapped + " "

    if name == "mtext":
        t = el.get_text()
        for k, v in OPERATOR_MAP.items():
            t = t.replace(k, v)
        return t.strip()

    if name == "mspace":
        return " "

    # Binary/multi-child structures
    kids = _tag_kids(el)

    if name == "msup":
        if len(kids) >= 2:
            return convert(kids[0]) + "^{" + convert(kids[1]) + "}"
        return cjoin()

    if name == "msub":
        if len(kids) >= 2:
            return convert(kids[0]) + "_{" + convert(kids[1]) + "}"
        return cjoin()

    if name == "msubsup":
        if len(kids) >= 3:
            return convert(kids[0]) + "_{" + convert(kids[1]) + "}^{" + convert(kids[2]) + "}"
        return cjoin()

    if name == "mfrac":
        if len(kids) >= 2:
            return r"\frac{" + convert(kids[0]) + "}{" + convert(kids[1]) + "}"
        return cjoin()

    if name == "msqrt":
        return r"\sqrt{" + cjoin() + "}"

    if name == "mroot":
        if len(kids) >= 2:
            return r"\sqrt[" + convert(kids[1]) + "]{" + convert(kids[0]) + "}"
        return cjoin()

    if name == "mover":
        if len(kids) >= 2:
            base = convert(kids[0])
            over = convert(kids[1]).strip()
            vec_chars = {"→", r"\to", "→", "⃗", "&#x2192;"}
            if over in vec_chars:
                return r"\overrightarrow{" + base + "}"
            if over in ("-", "–", "‾", "¯"):
                return r"\overline{" + base + "}"
            if over in ("^", "ˆ"):
                return r"\hat{" + base + "}"
            return r"\overset{" + over + "}{" + base + "}"
        return cjoin()

    if name == "munder":
        if len(kids) >= 2:
            return r"\underset{" + convert(kids[1]) + "}{" + convert(kids[0]) + "}"
        return cjoin()

    if name == "munderover":
        if len(kids) >= 3:
            base = convert(kids[0])
            under = convert(kids[1])
            over = convert(kids[2])
            return base + "_{" + under + "}^{" + over + "}"
        return cjoin()

    if name == "mfenced":
        open_b = el.get("open", "(")
        close_b = el.get("close", ")")
        sep = el.get("separators", ",")
        parts = [convert(k) for k in kids]
        inner = (" " + sep + " ").join(parts)
        return open_b + inner + close_b

    if name == "mtable":
        rows = []
        for tr in el.find_all("mtr", recursive=False):
            cells = [convert(td) for td in tr.find_all("mtd", recursive=False)]
            rows.append(" & ".join(cells))
        return r"\begin{matrix}" + r" \\ ".join(rows) + r"\end{matrix}"

    if name in ("mtr", "mtd", "mmultiscripts"):
        return cjoin()

    # Unknown tag: recurse
    return cjoin()


def extract_latex_from_block(form_tag) -> str:
    """
    Convert a checkform div to LaTeX-enriched text.
    Replaces <m:math> with $...$, keeps surrounding Russian text.
    """
    if not form_tag:
        return ""

    cell = form_tag.find("td", class_="cell_0") or form_tag

    # Fix MathML namespace: m:xxx → xxx
    cell_str = str(cell)
    cell_str = cell_str.replace("m:math", "math")
    # Replace all m:mXXX patterns
    import re
    cell_str = re.sub(r"<m:([a-z])", r"<\1", cell_str)
    cell_str = re.sub(r"</m:([a-z])", r"</\1", cell_str)

    fixed = BeautifulSoup(cell_str, "lxml")

    parts = []

    def walk(el):
        if isinstance(el, NavigableString):
            t = str(el)
            for k, v in OPERATOR_MAP.items():
                t = t.replace(k, v)
            t = t.strip()
            if t:
                parts.append(t)
            return

        if not isinstance(el, Tag):
            return

        name = _tag_name(el)

        if name == "math":
            latex = convert(el).strip()
            latex = re.sub(r"\s+", " ", latex)
            if latex:
                parts.append(f"${latex}$")
            return

        if name in ("script", "input", "button", "style"):
            return

        if name == "br":
            parts.append(" ")
            return

        for child in el.children:
            walk(child)

    walk(fixed)

    result = " ".join(parts)
    result = re.sub(r"\s+", " ", result).strip()
    return result


if __name__ == "__main__":
    # Test with complex fraction from ФИПИ
    test = """<td class="cell_0">
    <p><span>Решите неравенство</span>
    <m:math><m:semantics><m:mrow>
      <m:mfrac>
        <m:mrow>
          <m:msup><m:mn>8</m:mn><m:mrow><m:mi>x</m:mi><m:mo>+</m:mo><m:mfrac><m:mn>2</m:mn><m:mn>3</m:mn></m:mfrac></m:mrow></m:msup>
          <m:mo>−</m:mo><m:mn>9</m:mn><m:mo>⋅</m:mo><m:msup><m:mn>4</m:mn><m:mrow><m:mi>x</m:mi><m:mo>+</m:mo><m:mfrac><m:mn>1</m:mn><m:mn>2</m:mn></m:mfrac></m:mrow></m:msup>
        </m:mrow>
        <m:mrow>
          <m:msup><m:mn>4</m:mn><m:mrow><m:mi>x</m:mi><m:mo>+</m:mo><m:mfrac><m:mn>1</m:mn><m:mn>2</m:mn></m:mfrac></m:mrow></m:msup>
          <m:mo>−</m:mo><m:mn>9</m:mn><m:mo>⋅</m:mo><m:msup><m:mn>2</m:mn><m:mi>x</m:mi></m:msup>
        </m:mrow>
      </m:mfrac>
      <m:mo>≤</m:mo>
      <m:msup><m:mn>2</m:mn><m:mrow><m:mi>x</m:mi><m:mo>+</m:mo><m:mn>1</m:mn></m:mrow></m:msup>
    </m:mrow></m:semantics></m:math>
    </p></td>"""

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(test, "lxml")
    cell = soup.find("td")
    print("Result:", extract_latex_from_block(cell))

    # Test vector
    test2 = """<td class="cell_0"><span>Даны векторы</span>
    <m:math><m:semantics><m:mrow>
      <m:mover><m:mi>a</m:mi><m:mo>→</m:mo></m:mover>
      <m:mo>(</m:mo><m:mn>3</m:mn><m:mo>;</m:mo><m:mn>4</m:mn><m:mo>)</m:mo>
    </m:mrow></m:semantics></m:math></td>"""
    soup2 = BeautifulSoup(test2, "lxml")
    print("Vector:", extract_latex_from_block(soup2.find("td")))
