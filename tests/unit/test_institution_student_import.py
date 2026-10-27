"""Reading student lists: Excel, CSV/TSV, headers or none, pasted text, and clear reports for rows that cannot be used."""

import io

import pytest
from openpyxl import Workbook

from modules.institutions.student_import import MAX_ROWS, StudentListError, parse_students


def _xlsx(rows) -> bytes:
    book = Workbook()
    sheet = book.active
    for row in rows:
        sheet.append(row)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def test_a_csv_with_a_header_maps_columns_by_name_in_any_order():
    text = "Mobile,Email ID,Student Name,Department,Year\n9876543210,Asha@Example.com,Asha Rao,CSE,3\n"
    parsed = parse_students(filename="list.csv", data=text.encode())
    assert [p.reason for p in parsed.problems] == []
    s = parsed.students[0]
    assert (s.name, s.email, s.phone) == ("Asha Rao", "asha@example.com", "9876543210")
    # the columns we do not model are kept, keyed by their header
    assert s.details == {"Department": "CSE", "Year": "3"}
    assert s.row == 2


def test_an_excel_file_is_read_and_numbers_become_text_without_a_trailing_point():
    data = _xlsx([["Name", "Email", "Phone"], ["Asha Rao", "asha@example.com", 9876543210.0], ["Meera", "meera@example.com", None]])
    parsed = parse_students(filename="students.xlsx", data=data)
    assert [(s.name, s.email, s.phone) for s in parsed.students] == [
        ("Asha Rao", "asha@example.com", "9876543210"),
        ("Meera", "meera@example.com", None),
    ]


def test_a_list_with_no_header_finds_the_email_and_phone_by_what_they_look_like():
    text = "Asha Rao\t9876543210\tasha@example.com\nMeera Iyer\tmeera@example.com\n"
    parsed = parse_students(text=text)
    assert [(s.name, s.email, s.phone) for s in parsed.students] == [
        ("Asha Rao", "asha@example.com", "9876543210"),
        ("Meera Iyer", "meera@example.com", None),
    ]
    assert parsed.students[0].row == 1


def test_pasted_lines_with_no_separator_at_all():
    parsed = parse_students(text="Asha Rao asha@example.com 9876543210\nMeera Iyer <meera@example.com>\n")
    assert [(s.name, s.email, s.phone) for s in parsed.students] == [
        ("Asha Rao", "asha@example.com", "9876543210"),
        ("Meera Iyer", "meera@example.com", None),
    ]


def test_semicolon_and_pipe_lists_and_a_byte_order_mark():
    assert parse_students(text="Name;Email\nAsha;asha@example.com").students[0].email == "asha@example.com"
    assert parse_students(text="Asha | asha@example.com").students[0].name == "Asha"
    bom = "﻿Name,Email\nAsha,asha@example.com".encode("utf-8")
    assert parse_students(filename="x.csv", data=bom).students[0].name == "Asha"


def test_rows_that_cannot_be_used_are_reported_with_their_row_number_and_the_rest_still_import():
    text = "Name,Email\nAsha,asha@example.com\nNo Email,\nBad,not-an-email\n,nameless@example.com\nMeera,meera@example.com\n"
    parsed = parse_students(text=text)
    assert [s.email for s in parsed.students] == ["asha@example.com", "meera@example.com"]
    by_row = {p.row: p.reason for p in parsed.problems}
    assert by_row[3] == "No email address."
    assert "not a valid email" in by_row[4]
    assert by_row[5] == "No name."


def test_extra_whitespace_in_names_is_collapsed_and_emails_are_lower_cased():
    s = parse_students(text="Name,Email\n  Asha    Rao ,  ASHA@Example.COM ").students[0]
    assert (s.name, s.email) == ("Asha Rao", "asha@example.com")


def test_a_file_that_cannot_be_read_says_why():
    with pytest.raises(StudentListError, match=r"\.xlsx"):
        parse_students(filename="old.xls", data=b"x")
    with pytest.raises(StudentListError, match="Excel"):
        parse_students(filename="notes.docx", data=b"x")
    with pytest.raises(StudentListError, match="could not be read"):
        parse_students(filename="broken.xlsx", data=b"this is not a zip")
    with pytest.raises(StudentListError, match="No students"):
        parse_students(text="  \n \n")
    with pytest.raises(StudentListError, match="too large"):
        parse_students(filename="big.csv", data=b"x" * (5 * 1024 * 1024 + 1))
    with pytest.raises(StudentListError, match="paste"):
        parse_students()


def test_a_list_over_the_row_limit_is_refused_instead_of_half_imported():
    text = "Name,Email\n" + "\n".join(f"S{i},s{i}@example.com" for i in range(MAX_ROWS + 1))
    with pytest.raises(StudentListError, match="more than"):
        parse_students(text=text)


def test_a_header_row_is_not_mistaken_for_a_student_and_an_email_in_row_one_means_no_header():
    assert parse_students(text="asha@example.com,Asha").students[0].row == 1
    assert len(parse_students(text="Name,Email\nA,a@example.com").students) == 1
