#!/usr/bin/env python3
"""
Generate demo/test input files for the SEATS Data Validator.

Each file exercises a specific scenario so you can see the tool's behaviour:
mapping messy headers, coercing values, flagging what it can't fix, and joining
Canvas DAP tables. Run:  python standalone/sample_data/make_samples.py
"""
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAP = HERE / "canvas_dap"


def write(path: Path, headers, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    print(f"  {path.relative_to(HERE.parent)}  ({len(rows)} rows)")


def student_clean():
    # Canonical SEATS names, all mandatory filled, valid -> should be IMPORTABLE.
    headers = ["STUDENT_ID", "STUDENT_FORENAME", "STUDENT_LAST_NAME", "COURSE_ID",
               "COURSE_NAME", "MODULE_ID", "MODULE_NAME", "SCHOOL_ID", "SCHOOL_NAME",
               "STUDENT_LOGIN_ID", "GENDER", "STUDENT_EMAIL"]
    rows = [
        ["S1001", "Grace", "Hopper", "CS", "Computer Science", "CS101", "Intro Programming", "1", "School of Computing", "ghopper", "F", "g.hopper@uni.edu"],
        ["S1002", "Alan", "Turing", "CS", "Computer Science", "CS102", "Algorithms", "1", "School of Computing", "aturing", "M", "a.turing@uni.edu"],
        ["S1003", "Ada", "Lovelace", "MATH", "Mathematics", "MA101", "Calculus", "2", "School of Mathematics", "alovelace", "F", "a.lovelace@uni.edu"],
    ]
    write(HERE / "student_clean.csv", headers, rows)


def student_messy_sis():
    # SIS-style headers that need mapping; messy values; a junk column; a missing
    # login (blocking); a School name<->ID conflict (warning); text genders.
    headers = ["Student Number", "First Name", "Last Name", "Gender", "Email Address",
               "Login ID", "Course Code", "Course Title", "Module Code", "Module Title",
               "School ID", "School Name", "Enrolment Notes"]
    rows = [
        ["10012345", "Grace", "Hopper", "Female", "g.hopper@uni.edu", "ghopper", "CS", "Computer Science", "CS101", "Intro Programming", "1", "School of Computing", "enrolled"],
        ["10012346", " Alan ", "Turing", "Male", "a.turing@uni.edu", "aturing", "CS", "Computer Science", "CS102", "Algorithms", "1", "School of Computing", "enrolled"],
        ["10012347", "Ada", "Lovelace", "female", "not-an-email", "", "MATH", "Mathematics", "MA101", "Calculus", "2", "School of Mathematics", "missing login"],
        ["10012348", "Katherine", "Johnson", "F", "k.johnson@uni.edu", "kjohnson", "MATH", "Mathematics", "MA101", "Calculus", "7", "School of Mathematics", "school id conflict"],
    ]
    write(HERE / "student_messy_sis.csv", headers, rows)


def student_canvas_users():
    # Canvas SIS-format users export (LMS). Maps identity, but a single users file
    # has no course/module/school -> those blank -> shown in the issues report.
    headers = ["user_id", "sis_user_id", "login_id", "first_name", "last_name", "email", "status"]
    rows = [
        ["101", "S1001", "ghopper", "Grace", "Hopper", "g.hopper@uni.edu", "active"],
        ["102", "S1002", "aturing", "Alan", "Turing", "a.turing@uni.edu", "active"],
        ["103", "S1003", "alovelace", "Ada", "Lovelace", "a.lovelace@uni.edu", "active"],
    ]
    write(HERE / "student_canvas_users.csv", headers, rows)


def staff_messy():
    headers = ["Staff Number", "Forename", "Surname", "Email", "Username", "Staff Type"]
    rows = [
        ["E900", "Tim", "Berners-Lee", "t.bl@uni.edu", "tbl", "LECTRR"],
        ["E901", "Radia", "Perlman", "r.perlman@uni.edu", "rperlman", "PRFSRV"],
        ["E902", "Barbara", "Liskov", "", "bliskov", "LECTRR"],  # missing email (mandatory)
    ]
    write(HERE / "staff_messy.csv", headers, rows)


def timetable_messy():
    headers = ["EVENT_ID", "DAY", "START_TIME", "END_TIME", "ROOM_ID", "ROOM_NAME",
               "COURSE_ID", "COURSE_NAME", "MODULE_ID", "MODULE_NAME", "SCHOOL_ID",
               "SCHOOL_NAME", "STUDENT_ID", "LESSON_TYPE"]
    rows = [
        ["E1", "2026-01-12", "09:00", "10:00", "R1", "Room 1", "CS", "Computer Science", "CS101", "Intro Programming", "1", "School of Computing", "S1001", "L"],
        ["E1", "2026-01-12", "09:00", "10:00", "R1", "Room 1", "CS", "Computer Science", "CS101", "Intro Programming", "1", "School of Computing", "S1002", "L"],
        ["E1", "2026-01-12", "09:00", "10:00", "R9", "Room 9", "CS", "Computer Science", "CS101", "Intro Programming", "1", "School of Computing", "S1001", "L"],  # dup student + room differs
        ["E2", "2026-01-13", "14:00", "13:00", "R2", "Room 2", "CS", "Computer Science", "CS102", "Algorithms", "1", "School of Computing", "S1002", "L"],  # END before START
        ["E3", "2026-01-14", "", "", "", "", "CS", "Computer Science", "CS103", "Databases", "1", "School of Computing", "S1003", "V"],  # virtual: room/time exempt
    ]
    write(HERE / "timetable_messy.csv", headers, rows)


def canvas_dap_set():
    # Minimal Canvas DAP tables that JOIN into a Student roster.
    write(DAP / "users.csv",
          ["id", "name", "sortable_name", "workflow_state"],
          [["1", "Grace Hopper", "Hopper, Grace", "active"],
           ["2", "Alan Turing", "Turing, Alan", "active"],
           ["3", "Ada Lovelace", "Lovelace, Ada", "active"],
           ["9", "Tim Berners-Lee", "Berners-Lee, Tim", "active"]])
    write(DAP / "pseudonyms.csv",
          ["id", "user_id", "unique_id", "sis_user_id", "workflow_state"],
          [["11", "1", "ghopper", "S1001", "active"],
           ["12", "2", "aturing", "S1002", "active"],
           ["13", "3", "alovelace", "S1003", "active"],
           ["19", "9", "tbl", "E900", "active"]])
    write(DAP / "enrollments.csv",
          ["id", "user_id", "course_id", "course_section_id", "type", "workflow_state"],
          [["100", "1", "500", "700", "StudentEnrollment", "active"],
           ["101", "2", "500", "700", "StudentEnrollment", "active"],
           ["102", "3", "501", "710", "StudentEnrollment", "active"],
           ["103", "9", "500", "700", "TeacherEnrollment", "active"],
           ["104", "1", "500", "700", "StudentEnrollment", "deleted"]])  # skipped (not active)
    write(DAP / "courses.csv",
          ["id", "name", "account_id", "sis_source_id"],
          [["500", "Computer Science", "800", "CS"],
           ["501", "Mathematics", "801", "MATH"]])
    write(DAP / "course_sections.csv",
          ["id", "course_id", "name"],
          [["700", "500", "Section A"], ["710", "501", "Section A"]])
    write(DAP / "accounts.csv",
          ["id", "name", "sis_source_id"],
          [["800", "School of Computing", "1"], ["801", "School of Mathematics", "2"]])


def main():
    print("Generating sample data:")
    student_clean()
    student_messy_sis()
    student_canvas_users()
    staff_messy()
    timetable_messy()
    print("Canvas DAP tables:")
    canvas_dap_set()
    print("Done.")


if __name__ == "__main__":
    main()
