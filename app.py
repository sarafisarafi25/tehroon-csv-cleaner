"""Local CSV Cleaner. Python standard library only; no network requests."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import webbrowser


DELIMITERS = {"auto": None, "comma": ",", "semicolon": ";", "tab": "\t", "pipe": "|"}


def read_table(path: Path, encoding: str = "auto", delimiter: str = "auto"):
    raw = path.read_bytes()
    if not raw:
        raise ValueError("The selected file is empty.")
    codec = encoding
    if codec == "auto":
        codec = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    try:
        text = raw.decode(codec)
    except UnicodeError as exc:
        raise ValueError("Cannot decode this file. Choose its encoding, such as Windows Persian or Windows Turkish.") from exc
    if "\x00" in text:
        raise ValueError("The file contains binary data or uses a different encoding.")
    if delimiter not in DELIMITERS:
        raise ValueError("Unknown delimiter.")
    separator = DELIMITERS[delimiter]
    if separator is None:
        try:
            separator = csv.Sniffer().sniff(text[:65536], delimiters=",;\t|").delimiter
        except csv.Error:
            separator = ","
    try:
        csv.field_size_limit(25 * 1024 * 1024)
        rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=separator, strict=True))
    except csv.Error as exc:
        raise ValueError(f"CSV syntax error: {exc}") from exc
    if not rows or not rows[0]:
        raise ValueError("The first record must contain column names.")
    return raw, rows, separator, codec


def clean_file(source, output_parent=None, *, trim=True, deduplicate=True, encoding="auto", delimiter="auto"):
    source = Path(source).resolve()
    if not source.is_file():
        raise ValueError("Choose an existing CSV or TSV file.")
    if source.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("This starter version supports files up to 25 MB.")
    raw, rows, separator, codec = read_table(source, encoding, delimiter)
    original_header = rows[0]
    header = [value.strip() if trim else value for value in original_header]
    if any(not name.strip() for name in header):
        raise ValueError("Every column needs a name in the first record.")
    if len(set(header)) != len(header):
        raise ValueError("Duplicate column names found. Give each column a unique name.")
    kept, rejected, seen = [], [], set()
    changed_cells = sum(a != b for a, b in zip(original_header, header))
    empty_count = duplicate_count = 0
    for record_number, original in enumerate(rows[1:], 2):
        if not original or all(not value.strip() for value in original):
            empty_count += 1
            rejected.append(["empty", str(record_number), json.dumps(original, ensure_ascii=False)])
            continue
        if len(original) != len(header):
            raise ValueError(f"Record {record_number} has {len(original)} cells; expected {len(header)}. Check the separator and source file. No output was written.")
        cleaned = [value.strip() if trim else value for value in original]
        changed_cells += sum(a != b for a, b in zip(original, cleaned))
        key = tuple(cleaned)
        if deduplicate and key in seen:
            duplicate_count += 1
            rejected.append(["duplicate", str(record_number), json.dumps(original, ensure_ascii=False)])
            continue
        seen.add(key)
        kept.append(cleaned)
    parent = Path(output_parent).resolve() if output_parent else source.parent
    if not parent.is_dir():
        raise ValueError("The output folder does not exist.")
    folder = Path(tempfile.mkdtemp(prefix=source.stem[:50] + "-cleaned-", dir=parent))
    stats = {
        "source_name": source.name,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "input_rows": len(rows) - 1,
        "output_rows": len(kept),
        "columns": len(header),
        "removed_empty_rows": empty_count,
        "removed_duplicate_rows": duplicate_count,
        "trimmed_cells": changed_cells,
        "encoding_read": codec,
        "delimiter_read": separator,
        "trim_enabled": trim,
        "deduplicate_enabled": deduplicate,
        "missing_cells_by_column": {name: sum(not row[i].strip() for row in kept) for i, name in enumerate(header)},
    }
    try:
        for filename, table in [("cleaned.csv", [header, *kept]), ("removed_rows.csv", [["removal_reason", "source_record", "original_cells_json"], *rejected])]:
            with (folder / filename).open("w", encoding="utf-8-sig", newline="") as handle:
                csv.writer(handle).writerows(table)
        (folder / "summary.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
        (folder / "report.html").write_text(make_report(stats, header, kept), encoding="utf-8")
    except Exception:
        shutil.rmtree(folder)
        raise
    return folder, stats


def make_report(stats, header, rows):
    esc = lambda value: html.escape(str(value), quote=True)
    cards = "".join(f'<div class="card"><span>{label}</span><strong>{stats[key]:,}</strong></div>' for key, label in [
        ("input_rows", "Input rows"), ("output_rows", "Clean rows"),
        ("removed_duplicate_rows", "Duplicates removed"), ("removed_empty_rows", "Empty rows removed")])
    headings = "".join(f"<th>{esc(value)}</th>" for value in header)
    cells = "".join("<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>" for row in rows[:20])
    missing = "".join(f"<tr><td>{esc(name)}</td><td>{count}</td></tr>" for name, count in stats["missing_cells_by_column"].items())
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CSV cleaning report</title><style>
body{{font:16px/1.6 system-ui,sans-serif;margin:0;color:#202526;background:#f4f5f1}}main{{max-width:1080px;margin:auto;padding:42px 24px}}
.eyebrow{{color:#886726;font-size:12px;font-weight:700;letter-spacing:2px}}h1{{font-size:36px;line-height:1.2;margin:10px 0 12px}}
.muted{{color:#596260}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin:28px 0}}
.card{{background:white;border:1px solid #dfe3db;border-radius:12px;padding:20px}}.card span{{display:block;color:#596260;font-size:14px}}strong{{display:block;font-size:30px}}
section{{background:white;border:1px solid #dfe3db;border-radius:12px;padding:22px;margin-top:20px;overflow:auto}}h2{{font-size:20px;margin:0 0 14px}}
table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{text-align:start;border-bottom:1px solid #e5e7e0;padding:10px 12px;white-space:pre-wrap;min-width:85px}}th{{background:#f4f5f1}}code{{overflow-wrap:anywhere;font-size:12px}}
</style><main><div class="eyebrow">TEHROON / AUTOMATION TOOLS</div><h1>CSV cleaning report</h1>
<p class="muted">Source: {esc(stats['source_name'])}. First record treated as column names. All cell values retained as text.</p>
<div class="cards">{cards}</div><section><h2>Processing settings</h2>
<p>Trim outer whitespace: {esc(stats['trim_enabled'])}<br>Remove exact duplicate rows after optional trimming: {esc(stats['deduplicate_enabled'])}<br>Cells trimmed, including headers and removed rows: {stats['trimmed_cells']}</p>
<p>The input file was opened for reading only. Removed rows are available in removed_rows.csv.</p></section>
<section><h2>Cleaned data preview</h2><p class="muted">First {min(20, len(rows))} of {len(rows)} output rows.</p><table><thead><tr>{headings}</tr></thead><tbody>{cells}</tbody></table></section>
<section><h2>Missing cells in retained rows</h2><table><thead><tr><th>Column</th><th>Missing cells</th></tr></thead><tbody>{missing}</tbody></table></section>
<p class="muted">Input SHA-256: <code>{esc(stats['source_sha256'])}</code></p></main></html>'''


def launch_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    root = tk.Tk()
    root.title("Tehroon | CSV Cleaner")
    root.geometry("800x650")
    root.minsize(720, 610)
    root.configure(bg="#f4f5f1")
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TFrame", background="#f4f5f1")
    style.configure("TLabel", background="#f4f5f1", foreground="#202526", font=("Segoe UI", 11))
    style.configure("TCheckbutton", background="#f4f5f1", font=("Segoe UI", 10))
    style.configure("TButton", font=("Segoe UI", 10), padding=8)
    style.configure("Run.TButton", background="#202526", foreground="white", font=("Segoe UI", 11, "bold"))
    frame = ttk.Frame(root, padding=28)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="TEHROON / AUTOMATION TOOLS", foreground="#886726", font=("Segoe UI", 10, "bold")).pack(anchor="w")
    ttk.Label(frame, text="Clean CSV files. Keep a clear record.", font=("Segoe UI", 22, "bold")).pack(anchor="w", pady=(8, 4))
    ttk.Label(frame, text="Choose a file, review settings, then create a new output folder.").pack(anchor="w")
    source = tk.StringVar()
    destination = tk.StringVar()
    trim = tk.BooleanVar(value=True)
    dedupe = tk.BooleanVar(value=True)
    separator = tk.StringVar(value="auto")
    encoding_label = tk.StringVar(value="Auto (Unicode)")
    encodings = {"Auto (Unicode)": "auto", "UTF-8": "utf-8-sig", "Windows Persian": "cp1256", "Windows Turkish": "cp1254"}

    def choose_file():
        path = filedialog.askopenfilename(title="Choose CSV or TSV", filetypes=[("CSV / TSV files", "*.csv *.tsv"), ("All files", "*.*")])
        if path:
            source.set(path)
            destination.set(str(Path(path).parent))

    def choose_output():
        path = filedialog.askdirectory(title="Choose parent output folder")
        if path:
            destination.set(path)

    for label, variable, callback in [("1. Input file", source, choose_file), ("2. Save outputs inside", destination, choose_output)]:
        ttk.Label(frame, text=label).pack(anchor="w", pady=(16, 5))
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True, ipady=5)
        ttk.Button(row, text="Browse", command=callback).pack(side="left", padx=(8, 0))
    options = ttk.Frame(frame)
    options.pack(fill="x", pady=(16, 8))
    ttk.Label(options, text="Separator").grid(row=0, column=0, sticky="w", padx=(0, 12))
    ttk.Combobox(options, state="readonly", textvariable=separator, values=list(DELIMITERS), width=13).grid(row=0, column=1, sticky="w")
    ttk.Label(options, text="Encoding").grid(row=0, column=2, padx=(24, 12))
    ttk.Combobox(options, state="readonly", textvariable=encoding_label, values=list(encodings), width=22).grid(row=0, column=3, sticky="w")
    ttk.Checkbutton(frame, text="Trim whitespace at the start / end of cells", variable=trim).pack(anchor="w", pady=4)
    ttk.Checkbutton(frame, text="Remove exact duplicate rows (after optional trimming)", variable=dedupe).pack(anchor="w", pady=4)
    ttk.Label(frame, text="Empty rows are separated automatically. First row must contain column names.", font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 12))
    status = tk.StringVar(value="Tip: start with the included sample.csv.")
    last_output = {"folder": None}

    def open_report():
        if last_output["folder"]:
            webbrowser.open((last_output["folder"] / "report.html").as_uri())

    def run():
        if not source.get().strip() or not destination.get().strip():
            messagebox.showinfo("Choose files", "Choose an input file and output folder first.")
            return
        run_button.configure(state="disabled")
        status.set("Processing...")
        root.update_idletasks()
        try:
            folder, stats = clean_file(source.get(), destination.get(), trim=trim.get(), deduplicate=dedupe.get(), encoding=encodings[encoding_label.get()], delimiter=separator.get())
            last_output["folder"] = folder
            report_button.configure(state="normal")
            status.set(f"Done: {stats['input_rows']} input rows -> {stats['output_rows']} clean rows.\nRemoved: {stats['removed_empty_rows']} empty / {stats['removed_duplicate_rows']} duplicate.\nOutputs: {folder}")
            messagebox.showinfo("Complete", "Your new output folder is ready.\nClick Open report to view the result.")
        except (OSError, ValueError) as exc:
            status.set("Could not process this file.")
            messagebox.showerror("Check input", str(exc))
        finally:
            run_button.configure(state="normal")

    actions = ttk.Frame(frame)
    actions.pack(fill="x", pady=6)
    run_button = ttk.Button(actions, text="Clean file", style="Run.TButton", command=run)
    run_button.pack(side="left")
    report_button = ttk.Button(actions, text="Open report", command=open_report, state="disabled")
    report_button.pack(side="left", padx=10)
    ttk.Label(frame, textvariable=status, wraplength=700, justify="left", font=("Segoe UI", 10)).pack(anchor="w", fill="x", pady=(16, 0))
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", help="Input CSV / TSV; omit to open the desktop app")
    parser.add_argument("--demo", action="store_true", help="Clean the included sample.csv")
    parser.add_argument("--output", help="Existing parent folder for new outputs")
    parser.add_argument("--keep-duplicates", action="store_true")
    parser.add_argument("--keep-whitespace", action="store_true")
    parser.add_argument("--delimiter", choices=DELIMITERS, default="auto")
    parser.add_argument("--encoding", choices=["auto", "utf-8-sig", "cp1256", "cp1254"], default="auto")
    args = parser.parse_args()
    if args.file or args.demo:
        try:
            source = Path(__file__).with_name("sample.csv") if args.demo else args.file
            folder, stats = clean_file(source, args.output, trim=not args.keep_whitespace, deduplicate=not args.keep_duplicates, delimiter=args.delimiter, encoding=args.encoding)
            print(json.dumps({"output_folder": str(folder), **stats}, indent=2, ensure_ascii=True))
        except (OSError, ValueError) as exc:
            parser.exit(1, f"Error: {exc}\n")
    else:
        try:
            launch_gui()
        except ImportError:
            parser.exit(1, "The desktop app needs Tkinter from a full Python installation. You can still run: python app.py --demo\n")


if __name__ == "__main__":
    main()
