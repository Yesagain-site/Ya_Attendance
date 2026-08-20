import React from "react";
import {
  DashboardOutlined, TeamOutlined, ApartmentOutlined, IdcardOutlined,
  EnvironmentOutlined, DesktopOutlined, CodeOutlined, ClockCircleOutlined,
  SettingOutlined, FieldTimeOutlined, CalendarOutlined, ScheduleOutlined,
  CoffeeOutlined, TableOutlined, UnorderedListOutlined, UserOutlined,
} from "@ant-design/icons";

// Top-nav sections; each carries its own left-sidebar items.
export const SECTIONS = [
  { key: "dashboard", label: "Dashboard", icon: <DashboardOutlined />, base: "/dashboard", items: [] },
  {
    key: "personnel", label: "Personnel", icon: <TeamOutlined />, base: "/personnel",
    items: [
      { path: "/personnel/employees", label: "Employees", icon: <TeamOutlined /> },
      { path: "/personnel/inactive", label: "Inactive", icon: <UserOutlined /> },
      { path: "/personnel/departments", label: "Departments", icon: <ApartmentOutlined /> },
      { path: "/personnel/positions", label: "Positions", icon: <IdcardOutlined /> },
      { path: "/personnel/areas", label: "Areas", icon: <EnvironmentOutlined /> },
    ],
  },
  {
    key: "devices", label: "Device", icon: <DesktopOutlined />, base: "/devices",
    items: [
      { path: "/devices", label: "Devices", icon: <DesktopOutlined /> },
      { path: "/devices/commands", label: "Device Commands", icon: <CodeOutlined /> },
    ],
  },
  {
    key: "attendance", label: "Attendance", icon: <ClockCircleOutlined />, base: "/attendance",
    items: [
      { path: "/attendance/rules", label: "Global Rule", icon: <SettingOutlined /> },
      { path: "/attendance/timetables", label: "Timetables", icon: <FieldTimeOutlined /> },
      { path: "/attendance/shifts", label: "Shifts", icon: <CalendarOutlined /> },
      { path: "/attendance/schedules", label: "Schedules", icon: <ScheduleOutlined /> },
      { path: "/attendance/breaks", label: "Breaks", icon: <CoffeeOutlined /> },
      { path: "/attendance/daily", label: "Daily Report", icon: <TableOutlined /> },
      { path: "/attendance/monthly", label: "Monthly Report", icon: <TableOutlined /> },
      { path: "/attendance/log", label: "Punch Log", icon: <UnorderedListOutlined /> },
    ],
  },
  {
    key: "system", label: "System", icon: <SettingOutlined />, base: "/system", adminOnly: true,
    items: [
      { path: "/system/users", label: "Users & Roles", icon: <UserOutlined /> },
      { path: "/system/audit", label: "Audit Log", icon: <UnorderedListOutlined /> },
      { path: "/system/settings", label: "Settings", icon: <SettingOutlined /> },
    ],
  },
];

export function sectionForPath(pathname) {
  return (
    SECTIONS.find((s) => pathname === s.base || pathname.startsWith(s.base + "/")) ||
    SECTIONS.find((s) => s.items.some((i) => i.path === pathname)) ||
    SECTIONS[0]
  );
}
