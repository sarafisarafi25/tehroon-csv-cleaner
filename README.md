# Tehroon CSV Cleaner

A small Python automation portfolio project. It cleans CSV/TSV records and creates an HTML report using only Python's standard library. The Windows desktop interface uses Tkinter.

## Windows quick start

1. Extract the ZIP fully.
2. Open the extracted folder and double-click `START_WINDOWS.bat`.
3. Click the first **Browse** button and choose the included `sample.csv`.
4. Leave the default options selected and click **Clean file**.
5. Click **Open report**.

The sample has 8 input records: 4 are retained, 2 empty records and 2 duplicate records are separated.

## Outputs

Each run makes a uniquely named output folder next to the input file, or inside the selected parent folder:

- `cleaned.csv`: retained records, UTF-8 with BOM, comma-delimited.
- `removed_rows.csv`: removed records with reasons, original logical record numbers and each original row as a JSON list of cell values. Numbers count CSV records, including the header, rather than physical lines in multiline files.
- `summary.json`: counts, settings, missing-cell counts and the input SHA-256.
- `report.html`: a local HTML summary and a preview of up to 20 retained rows.

## Processing contract

- The first record is always treated as column names. Empty or duplicate names are rejected.
- Input files are opened read-only. Every run writes to a new folder.
- Outer whitespace is trimmed by default. Disable this for whitespace-sensitive data.
- An exact duplicate means every cell matches after the optional trimming step. Disable deduplication when repeated records are meaningful.
- Entirely blank / whitespace-only records are always separated.
- Data cells remain strings: identifiers, leading zeroes, dates and amounts are not converted or recalculated.
- Malformed CSV or nonblank records with a different cell count stop processing before any output is written. Missing values remain missing.
- Automatic encoding handles UTF-8 and BOM-marked UTF-16. Select Windows Persian (cp1256) or Windows Turkish (cp1254) explicitly for legacy files.
- Automatic delimiter detection supports comma, semicolon, tab and pipe. Choose a delimiter manually if detection fails. Output is always comma-delimited.
- This starter edition is designed for small files, with a 25 MB input cap, and reads the file into memory. It does not read XLSX workbooks.
- The app makes no network requests. The report opens locally in your browser.

## Command line

```text
python app.py --demo
python app.py input.csv
python app.py input.csv --keep-duplicates --keep-whitespace
python app.py input.csv --encoding cp1254 --delimiter semicolon
python -m unittest discover -s tests -v
```

Python 3.10 or newer. Processing and CLI verified with Python 3.12. Desktop GUI requires a full Python installation with Tkinter;The Windows desktop interface and included sample workflow were verified with Python 3.14.7.

This is a demonstration / portfolio project. It is not a paid client assignment and does not provide automatic earnings.
