const BASE = import.meta.env.VITE_API_BASE || "/api";
let TOKEN = localStorage.getItem("zkt_token") || null;

export function setToken(t) {
  TOKEN = t;
  if (t) localStorage.setItem("zkt_token", t);
  else localStorage.removeItem("zkt_token");
}
export function getToken() {
  return TOKEN;
}

async function req(path, { method = "GET", body, params } = {}) {
  let url = BASE + path;
  if (params) {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== "" && v != null)
    );
    url += "?" + q.toString();
  }
  const headers = {};
  if (body) headers["Content-Type"] = "application/json";
  if (TOKEN) headers["Authorization"] = "Bearer " + TOKEN;
  const r = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (r.status === 401) {
    setToken(null);
    window.dispatchEvent(new Event("zkt-unauthorized"));
    throw new Error("Session expired");
  }
  if (!r.ok) {
    let msg = r.statusText;
    try {
      msg = (await r.json()).detail || msg;
    } catch {}
    throw new Error(msg);
  }
  if (r.status === 204) return null;
  return r.json();
}

export function photoUrl(pin) {
  return `${BASE}/employees/${pin}/photo?t=${encodeURIComponent(TOKEN || "")}`;
}

export const api = {
  login: (username, password) =>
    req("/auth/login", { method: "POST", body: { username, password } }),
  me: () => req("/auth/me"),

  summary: () => req("/summary"),
  devices: () => req("/devices"),
  recentPunches: (limit = 20) => req("/recent-punches", { params: { limit } }),

  employees: (params) => req("/employees", { params }),
  employee: (pin) => req("/employees/" + pin),
  createEmployee: (body) => req("/employees", { method: "POST", body }),
  updateEmployee: (pin, body) =>
    req("/employees/" + pin, { method: "PUT", body }),
  deleteEmployee: (pin) => req("/employees/" + pin, { method: "DELETE" }),
  inactiveEmployees: (months = 3) => req("/employees/inactive", { params: { months } }),
  purgeEmployee: (pin) => req(`/employees/${pin}/purge`, { method: "POST" }),
  purgeBulk: (pins) => req(`/employees/purge-bulk`, { method: "POST", body: { pins } }),

  departments: () => req("/departments"),
  positions: () => req("/positions"),
  areas: () => req("/areas"),

  updateDevice: (sn, body) => req(`/devices/${sn}`, { method: "PUT", body }),

  // device orders (Phase 5)
  deviceCommands: (sn, limit = 50) => req(`/devices/${sn}/commands`, { params: { limit } }),
  clearPending: (sn) => req(`/devices/${sn}/commands/pending`, { method: "DELETE" }),
  enrollToDevice: (sn, pins, with_face = true) =>
    req(`/devices/${sn}/enroll`, { method: "POST", body: { pins, with_face } }),
  syncAllToDevice: (sn, with_face = true) =>
    req(`/devices/${sn}/sync-all`, { method: "POST", params: { with_face } }),
  deleteFromDevice: (sn, pins) =>
    req(`/devices/${sn}/delete-users`, { method: "POST", body: { pins } }),
  deviceMenu: (sn, command) =>
    req(`/devices/${sn}/menu`, { method: "POST", body: { command } }),

  // admin / system (Phase 6)
  adminUsers: () => req("/admin/users"),
  createUser: (b) => req("/admin/users", { method: "POST", body: b }),
  updateUser: (id, b) => req("/admin/users/" + id, { method: "PUT", body: b }),
  deleteUser: (id) => req("/admin/users/" + id, { method: "DELETE" }),
  adminAudit: (limit = 100) => req("/admin/audit", { params: { limit } }),
  changePassword: (current_password, new_password) =>
    req("/admin/change-password", { method: "POST", body: { current_password, new_password } }),
  exportEmployees: () => download("/employees/export.xlsx", {}, "employees.xlsx"),
  importEmployees: async (fileObj) => {
    const fd = new FormData();
    fd.append("file", fileObj);
    const headers = TOKEN ? { Authorization: "Bearer " + TOKEN } : {};
    const r = await fetch(BASE + "/employees/import", { method: "POST", headers, body: fd });
    if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch {} throw new Error(m); }
    return r.json();
  },

  attendance: (params) => req("/attendance", { params }),
  dailyReport: (date) => req("/reports/daily", { params: { date } }),

  // attendance engine + config
  rules: () => req("/attendance/rules"),
  saveRules: (body) => req("/attendance/rules", { method: "PUT", body }),
  timetables: () => req("/attendance/timetables"),
  createTimetable: (b) => req("/attendance/timetables", { method: "POST", body: b }),
  updateTimetable: (id, b) => req("/attendance/timetables/" + id, { method: "PUT", body: b }),
  deleteTimetable: (id) => req("/attendance/timetables/" + id, { method: "DELETE" }),
  shifts: () => req("/attendance/shifts"),
  createShift: (b) => req("/attendance/shifts", { method: "POST", body: b }),
  updateShift: (id, b) => req("/attendance/shifts/" + id, { method: "PUT", body: b }),
  deleteShift: (id) => req("/attendance/shifts/" + id, { method: "DELETE" }),
  breaks: () => req("/attendance/breaks"),
  createBreak: (b) => req("/attendance/breaks", { method: "POST", body: b }),
  deleteBreak: (id) => req("/attendance/breaks/" + id, { method: "DELETE" }),
  schedules: () => req("/attendance/schedules"),
  createSchedule: (b) => req("/attendance/schedules", { method: "POST", body: b }),
  deleteSchedule: (id) => req("/attendance/schedules/" + id, { method: "DELETE" }),
  computeDay: (date) => req("/attendance/compute", { method: "POST", params: { date } }),
  dailyGrid: (date) => req("/attendance/daily", { params: { date } }),

  // dashboard + reports
  dashboardStats: () => req("/dashboard/stats"),
  dashboardExceptions: (days = 14) => req("/dashboard/exceptions", { params: { days } }),
  dashboardHourly: () => req("/dashboard/hourly"),
  monthly: (params) => req("/reports/monthly", { params }),
  downloadDaily: (date) => download("/reports/daily.xlsx", { date }, `daily_${date}.xlsx`),
  downloadMonthly: (params, fname) => download("/reports/monthly.xlsx", params, fname || "report.xlsx"),
};

async function download(path, params, filename) {
  const q = "?" + new URLSearchParams(params).toString();
  const headers = TOKEN ? { Authorization: "Bearer " + TOKEN } : {};
  const r = await fetch(BASE + path + q, { headers });
  if (!r.ok) throw new Error("Download failed");
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
