/* Node unit tests for the browser engine. Run: node standalone/engine.test.js
   (requires standalone/seats_data.json — generate it with `python standalone/build.py`). */
const assert = require("assert");
const fs = require("fs");
const path = require("path");

const DATA = JSON.parse(fs.readFileSync(path.join(__dirname, "seats_data.json"), "utf8"));
const E = require("./engine.js");

let pass = 0, fail = 0;
function t(name, fn) { try { fn(); pass++; } catch (e) { fail++; console.error("FAIL:", name, "-", e.message); } }

t("output is exactly spec-shaped, junk dropped", () => {
  const res = E.autoClean(["STUDENT_ID", "SOME_JUNK", "STUDENT_FORENAME"],
    [{ STUDENT_ID: "S1", SOME_JUNK: "x", STUDENT_FORENAME: "A" }], "Student", DATA);
  assert.deepStrictEqual(res.fields, DATA.specs.Student.fields);
  assert.ok(res.rows[0].hasOwnProperty("STUDENT_LOGIN_ID"));
  assert.ok(!res.rows[0].hasOwnProperty("SOME_JUNK"));
});

t("missing mandatory flagged, file still produced", () => {
  const res = E.autoClean(["STUDENT_ID"], [{ STUDENT_ID: "S1" }], "Student", DATA);
  assert.strictEqual(res.summary.importable, false);
  assert.ok(res.residual.some(i => i.type === "missing_mandatory" && i.column === "STUDENT_LOGIN_ID"));
});

t("SIS alias (SPRIDEN_ID) maps to STUDENT_ID", () => {
  const res = E.autoClean(["SPRIDEN_ID"], [{ SPRIDEN_ID: "S1" }], "Student", DATA);
  assert.strictEqual(res.rows[0].STUDENT_ID, "S1");
});

t("Canvas/LMS aliases map to Student fields", () => {
  const res = E.autoClean(
    ["sis_user_id", "first_name", "last_name", "sis_login_id", "course_id", "long_name"],
    [{ sis_user_id: "U1", first_name: "Grace", last_name: "Hopper", sis_login_id: "gh", course_id: "C1", long_name: "Intro" }],
    "Student", DATA);
  assert.strictEqual(res.rows[0].STUDENT_ID, "U1");
  assert.strictEqual(res.rows[0].STUDENT_LOGIN_ID, "gh");
  assert.strictEqual(res.rows[0].COURSE_NAME, "Intro");
});

t("does NOT mis-map a real COURSE_NAME column", () => {
  const res = E.autoClean(["STUDENT_ID", "COURSE_NAME"], [{ STUDENT_ID: "S1", COURSE_NAME: "Maths" }], "Student", DATA);
  assert.strictEqual(res.rows[0].COURSE_NAME, "Maths");
});

t("enum coercion GENDER Male -> M", () => {
  const res = E.autoClean(["STUDENT_ID", "GENDER"], [{ STUDENT_ID: "S1", GENDER: "Male" }], "Student", DATA);
  assert.strictEqual(res.rows[0].GENDER, "M");
});

t("within-file name/id conflict flagged", () => {
  const res = E.autoClean(["SCHOOL_ID", "SCHOOL_NAME", "STUDENT_ID"],
    [{ SCHOOL_ID: "1", SCHOOL_NAME: "Biz", STUDENT_ID: "a" }, { SCHOOL_ID: "2", SCHOOL_NAME: "Biz", STUDENT_ID: "b" }],
    "Student", DATA);
  assert.ok(res.residual.some(i => i.type === "integrity" && i.column === "SCHOOL_ID"));
});

t("timetable END before START flagged", () => {
  const res = E.autoClean(["EVENT_ID", "START_TIME", "END_TIME"],
    [{ EVENT_ID: "E1", START_TIME: "10:00", END_TIME: "09:00" }], "StudentTimetable", DATA);
  assert.ok(res.residual.some(i => i.type === "time_sequence"));
});

t("Canvas DAP join -> roster -> spec-shaped", () => {
  const tables = {
    "users.csv": [{ id: 1, name: "Grace Hopper", sortable_name: "Hopper, Grace", workflow_state: "active" }],
    pseudonyms: [{ id: 10, user_id: 1, unique_id: "gh", sis_user_id: "S1", workflow_state: "active" }],
    enrollments: [{ id: 100, user_id: 1, course_id: 500, course_section_id: 700, type: "StudentEnrollment", workflow_state: "active" }],
    courses: [{ id: 500, name: "Intro CS", account_id: 800, sis_source_id: "CRS" }],
    course_sections: [{ id: 700, course_id: 500, name: "Sec A" }],
    accounts: [{ id: 800, name: "Computing", sis_source_id: "ACC" }],
  };
  const r = E.buildRoster(tables, "Student");
  assert.strictEqual(r.rows.length, 1);
  assert.strictEqual(r.rows[0].STUDENT_ID, "S1");
  assert.strictEqual(r.rows[0].STUDENT_FORENAME, "Grace");
  assert.strictEqual(r.rows[0].COURSE_NAME, "Intro CS");
  const res = E.autoClean(r.headers, r.rows, "Student", DATA);
  assert.deepStrictEqual(res.fields, DATA.specs.Student.fields);
  assert.strictEqual(res.rows[0].STUDENT_ID, "S1");
});

t("CSV export has UTF-8 BOM", () => {
  const csv = E.toCSV(["A", "B"], [{ A: "1", B: "2" }]);
  assert.strictEqual(csv.charCodeAt(0), 0xFEFF);
});

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
