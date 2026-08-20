import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { Spin } from "antd";
import { useAuth } from "./auth.jsx";
import AppLayout from "./components/AppLayout.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Employees from "./pages/Employees.jsx";
import { Departments, Positions, Areas } from "./pages/Org.jsx";
import Inactive from "./pages/Inactive.jsx";
import Devices from "./pages/Devices.jsx";
import DeviceCommands from "./pages/DeviceCommands.jsx";
import Users from "./pages/system/Users.jsx";
import Audit from "./pages/system/Audit.jsx";
import Settings from "./pages/system/Settings.jsx";
import GlobalRule from "./pages/attendance/GlobalRule.jsx";
import Timetables from "./pages/attendance/Timetables.jsx";
import Shifts from "./pages/attendance/Shifts.jsx";
import Schedules from "./pages/attendance/Schedules.jsx";
import Breaks from "./pages/attendance/Breaks.jsx";
import DailyReport from "./pages/attendance/DailyReport.jsx";
import MonthlyReport from "./pages/attendance/MonthlyReport.jsx";
import PunchLog from "./pages/attendance/PunchLog.jsx";

function Protected({ children }) {
  const { user, ready } = useAuth();
  if (!ready)
    return <div style={{ display: "grid", placeItems: "center", height: "100vh" }}><Spin size="large" /></div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Protected><AppLayout /></Protected>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />

        <Route path="personnel/employees" element={<Employees />} />
        <Route path="personnel/inactive" element={<Inactive />} />
        <Route path="personnel/departments" element={<Departments />} />
        <Route path="personnel/positions" element={<Positions />} />
        <Route path="personnel/areas" element={<Areas />} />

        <Route path="devices" element={<Devices />} />
        <Route path="devices/commands" element={<DeviceCommands />} />

        <Route path="attendance/rules" element={<GlobalRule />} />
        <Route path="attendance/timetables" element={<Timetables />} />
        <Route path="attendance/shifts" element={<Shifts />} />
        <Route path="attendance/schedules" element={<Schedules />} />
        <Route path="attendance/breaks" element={<Breaks />} />
        <Route path="attendance/daily" element={<DailyReport />} />
        <Route path="attendance/monthly" element={<MonthlyReport />} />
        <Route path="attendance/log" element={<PunchLog />} />

        <Route path="system/users" element={<Users />} />
        <Route path="system/audit" element={<Audit />} />
        <Route path="system/settings" element={<Settings />} />

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}
