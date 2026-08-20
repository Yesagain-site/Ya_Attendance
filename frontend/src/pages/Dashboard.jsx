import React, { useEffect, useState } from "react";
import { Row, Col, Card, Statistic, List, Tag, Avatar, message } from "antd";
import {
  TeamOutlined, CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined,
  LogoutOutlined, DesktopOutlined, SafetyCertificateOutlined, CoffeeOutlined,
} from "@ant-design/icons";
import { Pie, Line, Column } from "@ant-design/plots";
import { useNavigate } from "react-router-dom";
import PhotoAvatar from "../components/PhotoAvatar.jsx";
import { api } from "../api.js";

const CARDS = [
  { key: "employees", label: "Total Employees", icon: <TeamOutlined />, color: "#3b82f6" },
  { key: "present", label: "Present", icon: <CheckCircleOutlined />, color: "#22c55e" },
  { key: "absent", label: "Absent", icon: <CloseCircleOutlined />, color: "#ef4444" },
  { key: "late", label: "Late Arrival", icon: <ClockCircleOutlined />, color: "#f59e0b" },
  { key: "early", label: "Early Leave", icon: <LogoutOutlined />, color: "#a855f7" },
  { key: "on_leave", label: "On Leave", icon: <CoffeeOutlined />, color: "#64748b" },
  { key: "verification", label: "Verifications", icon: <SafetyCertificateOutlined />, color: "#0ea5e9" },
];

const CARD_LINK = {
  employees: "/personnel/employees",
  present: "/attendance/daily?status=present",
  absent: "/attendance/daily?status=absent",
  late: "/attendance/daily?status=late",
  early: "/attendance/daily?status=early",
  on_leave: "/attendance/daily?status=dayoff",
  verification: "/attendance/log",
};

export default function Dashboard() {
  const nav = useNavigate();
  const [stats, setStats] = useState({});
  const [exc, setExc] = useState([]);
  const [hourly, setHourly] = useState([]);
  const [punches, setPunches] = useState([]);

  const load = async () => {
    try {
      const [s, e, h, p] = await Promise.all([
        api.dashboardStats(), api.dashboardExceptions(14),
        api.dashboardHourly(), api.recentPunches(12),
      ]);
      setStats(s); setExc(e); setHourly(h); setPunches(p);
    } catch (err) { message.error(err.message); }
  };
  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  const donut = [
    { type: "Online", value: stats.devices_online || 0 },
    { type: "Offline", value: Math.max(0, (stats.devices_total || 0) - (stats.devices_online || 0)) },
  ];
  const excData = exc.flatMap((d) => [
    { date: d.date, type: "Late", value: d.late },
    { date: d.date, type: "Early-Leave", value: d.early },
    { date: d.date, type: "Absent", value: d.absent },
  ]);

  return (
    <div>
      <Row gutter={[16, 16]}>
        {CARDS.map((c) => (
          <Col xs={12} sm={8} md={6} lg={3} key={c.key}>
            <Card size="small" hoverable={!!CARD_LINK[c.key]} bodyStyle={{ padding: 16 }}
              onClick={() => CARD_LINK[c.key] && nav(CARD_LINK[c.key])}
              style={{ cursor: CARD_LINK[c.key] ? "pointer" : "default" }}>
              <Statistic title={c.label} value={stats[c.key] ?? 0}
                prefix={React.cloneElement(c.icon, { style: { color: c.color } })} />
            </Card>
          </Col>
        ))}
        <Col xs={12} sm={8} md={6} lg={3}>
          <Card size="small" hoverable bodyStyle={{ padding: 16 }}
            onClick={() => nav("/devices")} style={{ cursor: "pointer" }}>
            <Statistic title="Devices" value={`${stats.devices_online ?? 0}/${stats.devices_total ?? 0}`}
              prefix={<DesktopOutlined style={{ color: "#8b5cf6" }} />} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={8}>
          <Card title="Device Status" size="small">
            <Pie data={donut} angleField="value" colorField="type" innerRadius={0.6}
              height={240} legend={{ position: "bottom" }}
              scale={{ color: { range: ["#22c55e", "#ef4444"] } }}
              label={{ text: "value", position: "outside" }} />
          </Card>
        </Col>
        <Col xs={24} md={16}>
          <Card title="Attendance Exceptions (14 days)" size="small">
            <Line data={excData} xField="date" yField="value" colorField="type"
              height={240} legend={{ position: "top" }} smooth
              scale={{ color: { range: ["#f59e0b", "#a855f7", "#ef4444"] } }} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={10}>
          <Card title="Live Punches" size="small" bodyStyle={{ maxHeight: 340, overflow: "auto" }}>
            <List size="small" dataSource={punches}
              renderItem={(p) => {
                const isOut = p.punch_name === "Check-Out";
                const initial = String(p.name || p.pin).trim().charAt(0).toUpperCase();
                return (
                  <List.Item>
                    <List.Item.Meta
                      avatar={<PhotoAvatar pin={p.pin} hasPhoto={p.has_photo} name={p.name}
                        style={{ backgroundColor: isOut ? "#f59e0b" : "#22c55e", verticalAlign: "middle" }}>
                        {initial}</PhotoAvatar>}
                      title={<span>{p.name || p.pin}{" "}
                        <Tag color={isOut ? "orange" : "green"}>{p.punch_name}</Tag></span>}
                      description={String(p.punch_time).replace("T", " ").slice(0, 19) + " · " + (p.verify_name || "")} />
                  </List.Item>
                );
              }} />
          </Card>
        </Col>
        <Col xs={24} md={14}>
          <Card title="Real-Time Monitor (punches per hour, today)" size="small">
            <Column data={hourly} xField="hour" yField="punches" height={300}
              scale={{ color: { range: ["#38bdf8"] } }} />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
