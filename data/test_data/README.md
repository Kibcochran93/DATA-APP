# Test Data Files

Test datasets for validating the SEATS Data Validation Application against SEATS Master Data Interface Specification V8.2.

## Clean Data Files (should pass validation)

### test_student_data.csv
- 10 student records
- All mandatory fields populated
- Correct date format (YYYY-MM-DD)
- Valid enum values (TITLE, GENDER, VISAREQUIRED, etc.)
- Leading zeros preserved in ID fields
- Cross-file matching IDs (COURSE_ID, MODULE_ID, SCHOOL_ID match timetable)
- Multi-value field example: Student 001234573 has multiple BADGE_NUMBERs (pipe-separated)

### test_timetable_data.csv
- 18 timetable event records
- Multiple students per event (shared EVENT_ID + DAY)
- Multi-value fields demonstrated (ROOM_ID, TUTOR_ID using forward-slash separator)
- Various LESSON_TYPEs (L, P, S, LA, ST, T, W)
- Location hierarchy complete (SITE_CODE, BUILDING_ID, ROOM_ID)
- CLASSLINK URL example for virtual attendance
- IS_MANDATORY both Y and N examples

### test_staff_data.csv
- 10 staff records
- All mandatory fields populated (STAFF_NUMBER, FORENAME, LAST_NAME, UNIVERSITY_EMAIL, LOGIN_ID)
- Various STAFF_TYPEs demonstrated
- TUTOR_IDs match those referenced in timetable file

## Error Data Files (should fail validation with specific errors)

### test_student_data_with_errors.csv
Contains intentional errors:
1. Row 1: Wrong date format (15/03/2024), lowercase enum values (ms, f, n)
2. Row 2: Missing STUDENT_LAST_NAME, invalid email format (james.williams), DD/MM/YYYY dates
3. Row 3: Missing STUDENT_ID (mandatory field)
4. Row 4: Invalid GENDER value (X), missing country code on phone
5. Row 5: Invalid FEE_CATEGORY, invalid ADMIN_AREA, missing MODULE_ID
6. Row 6: Invalid VISAREQUIRED value (MAYBE), missing SCHOOL_ID, missing STUDENT_LOGIN_ID

### test_timetable_data_with_errors.csv
Contains intentional errors:
1. Row 1: Wrong date format (16/09/2024)
2. Row 2: Invalid time values (25:00, 26:00)
3. Row 3: Missing EVENT_ID (mandatory)
4. Row 4: Missing ROOM_ID (mandatory)
5. Row 5: Missing ROOM_NAME, invalid LESSON_TYPE
6. Row 6: Missing SCHOOL_ID (mandatory)
7. Row 7: Missing COURSE_NAME, invalid IS_MANDATORY value (MAYBE)
8. Row 8: Invalid CLASSLINK URL format
9. Row 9: Non-matching COURSE_ID, missing STUDENT_ID, missing SITE_NAME

### test_staff_data_with_errors.csv
Contains intentional errors:
1. Row 1: Lowercase TITLE and GENDER (should auto-fix)
2. Row 2: Invalid STAFF_TYPE value
3. Row 3: Missing STAFF_NUMBER (mandatory)
4. Row 4: Missing LAST_NAME (mandatory), invalid GENDER (X)
5. Row 5: Invalid personal EMAIL format
6. Row 6: Invalid TELEPHONE format, invalid UNIVERSITY_EMAIL, missing LOGIN_ID
7. Row 7: Missing FORENAME (mandatory)

## Cross-File Consistency

The clean data files are designed to work together:

| Field | Student File | Timetable File | Staff File |
|-------|--------------|----------------|------------|
| COURSE_ID | CS101, BUS201, ENG301, ART101 | Same values | - |
| MODULE_ID | MOD001-MOD006 | Same values | - |
| SCHOOL_ID | SCH001-SCH004 | Same values | - |
| STUDENT_ID | 001234567-001234576 | Same values | - |
| TUTOR_ID | - | TUT001-TUT005 | TUT001-TUT010 |

## Usage

1. Use clean files to verify the application accepts valid data
2. Use error files to verify the application detects and reports issues
3. Check cross-file validation by loading student and timetable together
