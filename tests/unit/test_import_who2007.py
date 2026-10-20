"""Offline XLSX fixtures protect the reference-data importer without replacing real tables."""

import hashlib
import io
import json
from zipfile import ZipFile

import httpx
import pytest

import app.scripts.import_who2007 as importer


def workbook(age_header="month", shared=True, last=228):
    def inline(column, value):
        return f'<c r="{column}1" t="inlineStr"><is><t>{value}</t></is></c>'

    labels = [age_header, "L", "M", "S"]
    cells = "".join(
        f'<c r="{column}1" t="s"><v>{index}</v></c>' if shared else inline(column, label)
        for index, (column, label) in enumerate(zip("ABCD", labels, strict=True))
    )
    rows = [f'<row>{cells}<c r="E1"/></row>']
    for age in ["missing", "bad", "60.5", *range(61, last + 1)]:
        values = [age, "-0.3", "18.5", "0.2"]
        body = "".join(
            f'<c r="{column}2"><v>{value}</v></c>'
            for column, value in zip("ABCD", values, strict=True)
        )
        if age == "missing":
            body = '<c r="A2"><v>65</v></c>'
        rows.append(f"<row>{body}</row>")
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
            + "".join(rows)
            + "</sheetData></worksheet>",
        )
        if shared:
            archive.writestr(
                "xl/sharedStrings.xml",
                "<sst>" + "".join(f"<si><t>{label}</t></si>" for label in labels) + "</sst>",
            )
    return stream.getvalue()


def offline_client(monkeypatch, tmp_path, raw, page=None, status=200):
    links = (
        page
        if page is not None
        else "".join(
            f'<a href="https://www.who.int/fixtures/{sex}-exp-z.xlsx?download=1">XLSX</a>'
            for sex in ["girls", "boys"]
        )
    )
    client_class = httpx.Client

    def handle(request):
        return httpx.Response(
            status, request=request, content=raw if ".xlsx" in str(request.url) else links.encode()
        )

    monkeypatch.setattr(
        importer.httpx,
        "Client",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handle), **kwargs),
    )
    monkeypatch.setattr(importer, "__file__", str(tmp_path / "scripts" / "import_who2007.py"))
    return tmp_path / "data" / "who2007_lms.json"


@pytest.mark.parametrize("age_header,shared", [("month", True), ("months", False), ("age", False)])
def test_importer_writes_complete_numeric_tables_with_source_checksums(
    monkeypatch, tmp_path, age_header, shared, capsys
):
    raw = workbook(age_header, shared)
    target = offline_client(monkeypatch, tmp_path, raw)
    importer.main()
    output = json.loads(target.read_text(encoding="utf-8"))
    assert set(output["tables"]) == {
        f"{kind}_{sex}" for kind in ("bmi", "height", "weight") for sex in ("F", "M")
    }
    for key, table in output["tables"].items():
        assert list(table)[0] == "61"
        assert len(table) == (60 if key.startswith("weight") else 168)
        assert table["61"] == [-0.3, 18.5, 0.2]
    assert len(output["sources"]) == 6
    assert all(source["sha256"] == hashlib.sha256(raw).hexdigest() for source in output["sources"])
    assert "Saved" in capsys.readouterr().out


@pytest.mark.parametrize(
    "problem,message",
    [
        ("no_link", "No official table"),
        ("age_column", "Unknown age column"),
        ("incomplete", "Incomplete monthly table"),
    ],
)
def test_bad_reference_inputs_never_write_an_incomplete_output(
    monkeypatch, tmp_path, problem, message
):
    raw = workbook(
        age_header="unknown" if problem == "age_column" else "month",
        last=227 if problem == "incomplete" else 228,
    )
    target = offline_client(
        monkeypatch, tmp_path, raw, page="<p>Sin tabla</p>" if problem == "no_link" else None
    )
    with pytest.raises(RuntimeError, match=message):
        importer.main()
    assert not target.exists()


def test_download_failure_propagates_without_writing_output(monkeypatch, tmp_path):
    target = offline_client(monkeypatch, tmp_path, b"", status=503)
    with pytest.raises(httpx.HTTPStatusError):
        importer.main()
    assert not target.exists()


def test_link_parser_ignores_unrelated_domains_missing_links_and_non_anchor_tags():
    parser = importer.Links()
    parser.feed(
        '<p href="https://www.who.int/file.xlsx"></p><a>Empty</a>'
        '<a href="https://example.org/file.xlsx">Other</a>'
        '<a href="https://www.who.int/help">Help</a>'
    )
    assert parser.urls == []
