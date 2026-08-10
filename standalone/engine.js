/*
 * SEATS Validator — browser engine (pure JS, no DOM).
 *
 * Mirrors the Python utils.auto_clean + utils.canvas_dap logic so the standalone
 * HTML tool behaves like the server engine. Runs in the browser (attaches to
 * window.SeatsEngine) and under Node (module.exports) for unit tests.
 *
 * All data (specs, column mappings, enum expansions) is passed in as `DATA`,
 * generated from the same spec/mapping JSONs by standalone/build.py.
 */
(function (root) {
  "use strict";

  function norm(s) {
    return String(s == null ? "" : s).toLowerCase().replace(/[^a-z0-9]/g, "");
  }
  function clean(v) {
    if (v == null) return "";
    if (typeof v === "number" && isNaN(v)) return "";
    return String(v).trim();
  }
  function canonType(t) {
    var k = norm(t);
    if (k === "timetable" || k === "studenttimetable") return "StudentTimetable";
    if (k === "staff") return "Staff";
    return "Student";
  }

  function distance(a, b) {
    var m = a.length, n = b.length;
    if (!m) return n; if (!n) return m;
    var prev = [], i, j;
    for (j = 0; j <= n; j++) prev[j] = j;
    for (i = 1; i <= m; i++) {
      var cur = [i];
      for (j = 1; j <= n; j++) {
        cur[j] = a[i - 1] === b[j - 1] ? prev[j - 1]
          : 1 + Math.min(prev[j - 1], prev[j], cur[j - 1]);
      }
      prev = cur;
    }
    return prev[n];
  }

  function buildAliasIndex(specFields, columnMappingsList) {
    var upper = {}; specFields.forEach(function (f) { upper[f.toUpperCase()] = 1; });
    var index = {};
    (columnMappingsList || []).forEach(function (cm) {
      Object.keys(cm).forEach(function (field) {
        if (!upper[field.toUpperCase()]) return;
        if (index[norm(field)] === undefined) index[norm(field)] = field;
        var systems = cm[field];
        if (systems && typeof systems === "object") {
          Object.keys(systems).forEach(function (k) {
            var arr = systems[k];
            if (!Array.isArray(arr)) return; // skip "description" strings
            arr.forEach(function (a) { if (index[norm(a)] === undefined) index[norm(a)] = field; });
          });
        }
      });
    });
    specFields.forEach(function (f) { if (index[norm(f)] === undefined) index[norm(f)] = f; });
    return index;
  }

  // headers: array of source column names. Returns {sourceHeader: seatsField}.
  function autoMap(headers, spec, DATA, userMapping) {
    var index = buildAliasIndex(spec.fields, DATA.columnMappings);
    var specNorm = {}; spec.fields.forEach(function (f) { specNorm[norm(f)] = 1; });
    var specUpper = {}; spec.fields.forEach(function (f) { specUpper[f.toUpperCase()] = 1; });
    var existingUpper = {}; headers.forEach(function (h) { existingUpper[String(h).toUpperCase()] = 1; });
    var claimed = {}, rename = {};

    if (userMapping) {
      Object.keys(userMapping).forEach(function (src) {
        var t = userMapping[src];
        if (t && headers.indexOf(src) >= 0) { rename[src] = t; claimed[t.toUpperCase()] = 1; }
      });
    }
    headers.forEach(function (col) {
      if (rename[col]) return;
      var target = index[norm(col)];
      if (!target) return;
      var tu = target.toUpperCase();
      if (String(col).toUpperCase() === tu) { if (col !== target) { rename[col] = target; claimed[tu] = 1; } return; }
      if (existingUpper[tu] || claimed[tu]) return;
      rename[col] = target; claimed[tu] = 1;
    });
    // Fuzzy fallback; never move a column that is already a valid spec field.
    headers.forEach(function (col) {
      if (rename[col] || specNorm[norm(col)]) return;
      var best = null, bestD = 1e9;
      spec.fields.forEach(function (f) {
        var tu = f.toUpperCase();
        if (existingUpper[tu] || claimed[tu]) return;
        var d = distance(norm(col), norm(f));
        if (d < bestD) { bestD = d; best = f; }
      });
      if (best && bestD <= Math.max(2, Math.floor(norm(col).length * 0.34))) {
        rename[col] = best; claimed[best.toUpperCase()] = 1;
      }
    });
    return rename;
  }

  function healHeaders(headers) {
    var h = headers.map(function (x) { return clean(x); });
    for (var i = 0; i < h.length; i++) {
      if (h[i].toUpperCase() === "VISAREQUIRED" && i + 2 < h.length) {
        var mid = h[i + 1];
        if ((mid === "" || /^unnamed:\s*\d+$/i.test(mid)) && h[i + 2].toUpperCase() === "COURSE_ID") h[i + 1] = "BADGENUMBER";
      }
    }
    return h;
  }

  function forceShape(rows, rename, spec) {
    return rows.map(function (r) {
      var o = {};
      spec.fields.forEach(function (f) { o[f] = ""; });
      Object.keys(r).forEach(function (src) {
        var target = rename[src];
        if (!target) {
          for (var i = 0; i < spec.fields.length; i++) {
            if (spec.fields[i].toUpperCase() === String(src).toUpperCase()) { target = spec.fields[i]; break; }
          }
        }
        if (target && o.hasOwnProperty(target) && o[target] === "") o[target] = clean(r[src]);
      });
      return o;
    });
  }

  function coerce(rows, spec, DATA) {
    var enums = spec.enums || {};
    var expansions = (DATA && DATA.enumExpansions) || {};
    return rows.map(function (r) {
      var o = {};
      spec.fields.forEach(function (f) {
        var v = clean(r[f]);
        if (enums[f] && v) {
          var vals = enums[f].map(function (x) { return String(x).toUpperCase(); });
          var up = v.toUpperCase();
          if (vals.indexOf(up) >= 0) { v = up; }
          else if (expansions[f] && expansions[f][up]) { v = expansions[f][up]; }
          else if (vals.indexOf(up.charAt(0)) >= 0) { v = up.charAt(0); }
        }
        o[f] = v;
      });
      return o;
    });
  }

  function validate(rows, spec) {
    var issues = [];
    var enums = spec.enums || {};
    var hasTime = spec.fields.indexOf("START_TIME") >= 0 && spec.fields.indexOf("END_TIME") >= 0;
    rows.forEach(function (r, i) {
      var rowNum = i + 2;
      spec.mandatory.forEach(function (f) {
        if (clean(r[f]) === "") issues.push({ row: rowNum, column: f, severity: "error", type: "missing_mandatory", message: f + " is mandatory and cannot be empty" });
      });
      spec.fields.forEach(function (f) {
        if (/email/i.test(f)) {
          var v = clean(r[f]);
          if (v && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) issues.push({ row: rowNum, column: f, severity: "warning", type: "email", message: "Email format may be invalid" });
        }
      });
      Object.keys(enums).forEach(function (f) {
        var v = clean(r[f]).toUpperCase();
        if (v) {
          var vals = enums[f].map(function (x) { return String(x).toUpperCase(); });
          if (vals.indexOf(v) < 0) issues.push({ row: rowNum, column: f, severity: "warning", type: "enum", message: '"' + r[f] + '" is not a valid ' + f + " value" });
        }
      });
      if (hasTime) {
        var s = clean(r.START_TIME), e = clean(r.END_TIME);
        if (/^\d{2}:\d{2}$/.test(s) && /^\d{2}:\d{2}$/.test(e)) {
          var sm = +s.slice(0, 2) * 60 + +s.slice(3), em = +e.slice(0, 2) * 60 + +e.slice(3);
          if (em <= sm) issues.push({ row: rowNum, column: "END_TIME", severity: "warning", type: "time_sequence", message: "END_TIME must be after START_TIME" });
        }
      }
    });
    return issues;
  }

  var NAME_ID_PAIRS = [
    ["School", ["SCHOOL_ID"], ["SCHOOL_NAME"]], ["Course", ["COURSE_ID"], ["COURSE_NAME"]],
    ["Module", ["MODULE_ID"], ["MODULE_NAME"]], ["Programme", ["PROGRAMME_ID"], ["PROGRAMME_NAME"]],
    ["Faculty", ["FACULTY_ID"], ["FACULITY_NAME", "FACULTY_NAME"]], ["Room", ["ROOM_ID"], ["ROOM_NAME"]],
    ["Site", ["SITE_ID", "SITE_CODE"], ["SITE_NAME"]], ["Building", ["BUILDING_ID"], ["BUILDING_NAME"]]
  ];
  function firstField(fields, cands) { for (var i = 0; i < cands.length; i++) if (fields.indexOf(cands[i]) >= 0) return cands[i]; return null; }

  function integrity(rows, spec) {
    var issues = [], fields = spec.fields;
    NAME_ID_PAIRS.forEach(function (p) {
      var idF = firstField(fields, p[1]), nameF = firstField(fields, p[2]);
      if (!idF || !nameF) return;
      var byName = {};
      rows.forEach(function (r, i) {
        var id = clean(r[idF]), name = clean(r[nameF]); if (!id || !name) return;
        var key = name.toLowerCase(); (byName[key] = byName[key] || { name: name, ids: {} });
        if (!byName[key].ids[id]) byName[key].ids[id] = i + 2;
      });
      Object.keys(byName).forEach(function (key) {
        var g = byName[key], ids = Object.keys(g.ids); if (ids.length < 2) return;
        ids.sort(function (a, b) { return g.ids[a] - g.ids[b]; });
        issues.push({ row: g.ids[ids[1]], column: idF, severity: "warning", type: "integrity", message: p[0] + ' name "' + g.name + '" is linked to multiple ' + p[0] + " IDs: " + ids.map(function (id) { return id + " (row " + g.ids[id] + ")"; }).join(", ") });
      });
    });
    if (fields.indexOf("STUDENT_ID") >= 0 && fields.indexOf("STUDENT_LOGIN_ID") >= 0) {
      var logins = {};
      rows.forEach(function (r, i) { var s = clean(r.STUDENT_ID), l = clean(r.STUDENT_LOGIN_ID); if (!s || !l) return; (logins[s] = logins[s] || {})[l] = logins[s][l] || i + 2; });
      Object.keys(logins).forEach(function (s) { var ls = Object.keys(logins[s]); if (ls.length > 1) issues.push({ row: Math.min.apply(null, ls.map(function (l) { return logins[s][l]; })), column: "STUDENT_LOGIN_ID", severity: "warning", type: "integrity", message: "Student " + s + " has multiple login IDs: " + ls.sort().join(", ") }); });
    }
    if (fields.indexOf("EVENT_ID") >= 0) {
      var CONSIST = ["DAY", "START_TIME", "END_TIME", "ROOM_ID", "ROOM_NAME", "COURSE_ID", "COURSE_NAME", "MODULE_ID", "MODULE_NAME", "SCHOOL_ID", "SCHOOL_NAME"].filter(function (f) { return fields.indexOf(f) >= 0; });
      var seen = {}, firstRow = {};
      rows.forEach(function (r, i) {
        var rn = i + 2, ev = clean(r.EVENT_ID); if (!ev) return;
        if (fields.indexOf("STUDENT_ID") >= 0) { var st = clean(r.STUDENT_ID); if (st) { var k = ev + " " + st; if (seen[k]) issues.push({ row: rn, column: "STUDENT_ID", severity: "warning", type: "integrity", message: "Student already listed for this event on row " + seen[k] }); else seen[k] = rn; } }
        if (!firstRow[ev]) firstRow[ev] = { row: rn, data: r };
        else CONSIST.forEach(function (f) { var c = clean(r[f]), o = clean(firstRow[ev].data[f]); if (c && o && c !== o) issues.push({ row: rn, column: f, severity: "warning", type: "integrity", message: "Value differs from the first row for event " + ev + " (row " + firstRow[ev].row + ")" }); });
      });
    }
    return issues;
  }

  function autoClean(headers, rows, datasetType, DATA, userMapping) {
    var spec = DATA.specs[canonType(datasetType)];
    headers = healHeaders(headers);
    var rename = autoMap(headers, spec, DATA, userMapping);
    var shaped = forceShape(rows, rename, spec);
    var coerced = coerce(shaped, spec, DATA);
    var residual = validate(coerced, spec).concat(integrity(coerced, spec));
    var mandatoryBlank = 0;
    coerced.forEach(function (r) { spec.mandatory.forEach(function (f) { if (clean(r[f]) === "") mandatoryBlank++; }); });
    var errors = residual.filter(function (i) { return i.severity === "error"; });
    return {
      fields: spec.fields, rows: coerced, rename: rename, residual: residual,
      summary: { rows: coerced.length, columns: spec.fields.length, mandatoryBlankCells: mandatoryBlank, errorCount: errors.length, warningCount: residual.length - errors.length, importable: errors.length === 0 }
    };
  }

  // ---- Canvas DAP join (mirrors utils.canvas_dap) ----
  function stripPrefix(name) { var n = String(name).trim().toLowerCase(); return n.replace(/^(value|key|meta)\./, ""); }
  function colmapOf(sample) { var m = {}; if (sample) Object.keys(sample).forEach(function (c) { var n = stripPrefix(c); if (m[n] === undefined) m[n] = c; }); return m; }
  function getv(row, cm, cands) { for (var i = 0; i < cands.length; i++) { var a = cm[cands[i]]; if (a !== undefined) return clean(row[a]); } return ""; }
  function normTableName(name) {
    var k = String(name).trim().toLowerCase().replace(/\\/g, "/").split("/").pop();
    k = k.replace(/\.(csv|jsonl|json|parquet|tsv)$/, "");
    if (k.indexOf("canvas.") === 0) k = k.slice(7);
    return k;
  }
  function splitName(sortable, name) {
    sortable = clean(sortable); name = clean(name);
    if (sortable.indexOf(",") >= 0) { var p = sortable.split(","); return [clean(p.slice(1).join(",")), clean(p[0])]; }
    if (name) { var t = name.split(/\s+/); return t.length === 1 ? ["", t[0]] : [t.slice(0, -1).join(" "), t[t.length - 1]]; }
    return ["", ""];
  }
  function indexBy(rows, idField) {
    var out = {}, cm = colmapOf(rows && rows[0]); var idc = cm[idField];
    if (idc === undefined) return { idx: out, cm: cm };
    rows.forEach(function (r) { var k = clean(r[idc]); if (k && !out[k]) out[k] = r; });
    return { idx: out, cm: cm };
  }
  var STUDENT_ENR = { studentenrollment: 1 };
  var STAFF_ENR = { teacherenrollment: 1, taenrollment: 1, designerenrollment: 1 };

  function buildRoster(tables, datasetType) {
    var T = {}; Object.keys(tables || {}).forEach(function (k) { T[normTableName(k)] = tables[k] || []; });
    var enr = T.enrollments, users = T.users;
    if (!enr || !users) throw new Error("Canvas DAP roster needs at least 'enrollments' and 'users' tables.");
    var isStaff = /staff/i.test(datasetType), want = isStaff ? STAFF_ENR : STUDENT_ENR;
    var U = indexBy(users, "id");
    var pseudo = bestPseudonym(T.pseudonyms);
    var C = indexBy(T.courses || [], "id"), S = indexBy(T.course_sections || [], "id"), A = indexBy(T.accounts || [], "id");
    var emails = emailByUser(T.communication_channels);
    var ec = colmapOf(enr[0]), notes = [], rows = [], skipped = 0;
    enr.forEach(function (e) {
      if (ec.type && !want[clean(e[ec.type]).toLowerCase()]) return;
      if (ec.workflow_state) { var ws = clean(e[ec.workflow_state]).toLowerCase(); if (ws && ws !== "active") { skipped++; return; } }
      var uid = clean(e[ec.user_id]);
      var u = U.idx[uid] || {}, ps = pseudo.idx[uid] || {};
      var course = ec.course_id ? (C.idx[clean(e[ec.course_id])] || {}) : {};
      var section = ec.course_section_id ? (S.idx[clean(e[ec.course_section_id])] || {}) : {};
      var acctId = getv(course, C.cm, ["account_id"]);
      var account = acctId ? (A.idx[acctId] || {}) : {};
      var nm = splitName(getv(u, U.cm, ["sortable_name"]), getv(u, U.cm, ["name"]));
      var sisUser = getv(ps, pseudo.cm, ["sis_user_id"]), login = getv(ps, pseudo.cm, ["unique_id"]);
      var email = emails[uid] || getv(u, U.cm, ["email"]);
      var courseId = getv(course, C.cm, ["sis_source_id"]) || getv(course, C.cm, ["id"]);
      var pid = sisUser || uid;
      if (isStaff) rows.push({ STAFF_NUMBER: pid, FORENAME: nm[0], LAST_NAME: nm[1], UNIVERSITY_EMAIL: email, LOGIN_ID: login });
      else rows.push({
        STUDENT_ID: pid, STUDENT_FORENAME: nm[0], STUDENT_LAST_NAME: nm[1], STUDENT_LOGIN_ID: login,
        STUDENT_EMAIL: email, UNIVERSITY_EMAIL: email, COURSE_ID: courseId, COURSE_NAME: getv(course, C.cm, ["name"]),
        SCHOOL_ID: getv(account, A.cm, ["sis_source_id"]) || getv(account, A.cm, ["id"]), SCHOOL_NAME: getv(account, A.cm, ["name"]),
        MODULE_GROUP: getv(section, S.cm, ["name"])
      });
    });
    ["pseudonyms", "courses", "course_sections", "accounts"].forEach(function (t) { if (!T[t] || !T[t].length) notes.push("'" + t + "' table not provided — related fields left blank."); });
    if (skipped) notes.push("Skipped " + skipped + " non-active enrollment(s).");
    notes.push("Built " + rows.length + " " + (isStaff ? "staff" : "student") + " row(s) from " + enr.length + " enrollment(s).");
    var headers = rows.length ? Object.keys(rows[0]) : [];
    return { headers: headers, rows: rows, notes: notes };
  }
  function bestPseudonym(rows) {
    var out = {}, cm = colmapOf(rows && rows[0]); if (!rows || cm.user_id === undefined) return { idx: out, cm: cm };
    var rank = {};
    rows.forEach(function (r) {
      var uid = clean(r[cm.user_id]); if (!uid) return;
      var a = cm.workflow_state && clean(r[cm.workflow_state]).toLowerCase() === "active" ? 1 : 0;
      var s = cm.sis_user_id && clean(r[cm.sis_user_id]) ? 1 : 0, sc = a * 2 + s;
      if (out[uid] === undefined || sc > rank[uid]) { out[uid] = r; rank[uid] = sc; }
    });
    return { idx: out, cm: cm };
  }
  function emailByUser(rows) {
    var out = {}, cm = colmapOf(rows && rows[0]); if (!rows || cm.user_id === undefined || cm.path === undefined) return out;
    rows.forEach(function (r) { if (cm.path_type && clean(r[cm.path_type]).toLowerCase() !== "email") return; var u = clean(r[cm.user_id]), p = clean(r[cm.path]); if (u && p && !out[u]) out[u] = p; });
    return out;
  }

  function toCSV(fields, rows) {
    var esc = function (v) { v = v == null ? "" : String(v); return /[",\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
    var out = [fields.map(esc).join(",")];
    rows.forEach(function (r) { out.push(fields.map(function (f) { return esc(r[f]); }).join(",")); });
    return "﻿" + out.join("\r\n");
  }
  function issuesCSV(residual) {
    var cols = ["row", "column", "severity", "type", "message"];
    return toCSV(cols, residual);
  }

  var API = { norm: norm, canonType: canonType, distance: distance, buildAliasIndex: buildAliasIndex, autoMap: autoMap, healHeaders: healHeaders, autoClean: autoClean, buildRoster: buildRoster, toCSV: toCSV, issuesCSV: issuesCSV };
  root.SeatsEngine = API;
  if (typeof module !== "undefined" && module.exports) module.exports = API;
})(typeof window !== "undefined" ? window : globalThis);
