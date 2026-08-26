import React, { useEffect, useState, useCallback } from "react";
import { Card, DatePicker, Button, Space, Tag, message, Statistic, Row, Col, Segmented, Input } from "antd";
import { ReloadOutlined, DownloadOutlined, SearchOutlined } from "@ant-design/icons";
import { useSearchParams } from "react-router-dom";
import dayjs from "dayjs";
import DataGrid from "../../components/DataGrid.jsx";
import { api } from "../../api.js";
import { useAuth } from "../../auth.jsx";

const FILTERS = ["All", "Present", "Absent", "Half day", "Day off", "Late", "Early"];
const matchFilter = (r, f) => {
  switch (f) {
    case "Present": return ["present", "incomplete", "halfday"].includes(r.status);
    case "Absent": return r.status === "absent";
    case "Half day": return r.status === "halfday";
    case "Day off": return r.status === "dayoff";
    case "Late": return r.late_min > 0;
    case "Early": return r.early_min > 0;
    default: return true;
  }
};
const PARAM_TO_FILTER = { present: "Present", absent: "Absent", halfday: "Half day",
  dayoff: "Day off", late: "Late", early: "Early" };

const STATUS = {
  present: "green", absent: "red", halfday: "orange",
  incomplete: "gold", dayoff: "default", holiday: "blue",
};
const hm = (min) => `${Math.floor((min || 0) / 60)}h ${(min || 0) % 60}m`;

export default function DailyReport() {
  const { isAdmin } = useAuth();
  const [params] = useSearchParams();
  const [date, setDate] = useState(dayjs());
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState(PARAM_TO_FILTER[params.get("status")] || "All");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(await api.dailyGrid(date.format("YYYY-MM-DD"))); }
    catch (e) { message.error(e.message); }
    finally { setLoading(false); }
  }, [date]);
  useEffect(() => { load(); }, [load]);

  const recompute = async () => {
    setLoading(true);
    try { await api.computeDay(date.format("YYYY-MM-DD")); await load(); message.success("Recomputed"); }
    catch (e) { message.error(e.message); }
    finally { setLoading(false); }
  };

  const counts = rows.reduce((a, r) => { a[r.status] = (a[r.status] || 0) + 1; return a; }, {});
  const lateN = rows.filter((r) => r.late_min > 0).length;
  const earlyN = rows.filter((r) => r.early_min > 0).length;
  const q = search.trim().toLowerCase();
  const shown = rows
    .filter((r) => matchFilter(r, filter))
    .filter((r) => !q || String(r.pin).includes(q) || (r.name || "").toLowerCase().includes(q));

  const columns = [
    { title: "PIN", dataIndex: "pin", width: 80 },
    { title: "Name", dataIndex: "name", render: (n) => n || "—" },
    { title: "Department", dataIndex: "department", render: (d) => d || "—" },
    { title: "Status", dataIndex: "status", render: (s) => <Tag color={STATUS[s] || "default"}>{s}</Tag> },
    { title: "Check-in", dataIndex: "first_in", render: (t) => (t ? String(t).slice(11, 19) : "—") },
    { title: "Check-out", dataIndex: "last_out", render: (t) => (t ? String(t).slice(11, 19) : "—") },
    { title: "Worked", dataIndex: "worked_min", render: hm },
    { title: "Late", dataIndex: "late_min", render: (m) => (m ? <span style={{ color: "#ef4444" }}>{m}m</span> : "—") },
    { title: "OT in", dataIndex: "ot_in", render: (t) => (t ? String(t).slice(11, 19) : "—") },
    { title: "OT out", dataIndex: "ot_out", render: (t) => (t ? String(t).slice(11, 19) : "—") },
    { title: "OT", dataIndex: "ot_min", render: (m) => (m ? <span style={{ color: "#22c55e" }}>{hm(m)}</span> : "—") },
  ];

  return (
    <Card title="Daily attendance" extra={
      <Space>
        <DatePicker value={date} onChange={(d) => d && setDate(d)} allowClear={false} />
        <Button icon={<DownloadOutlined />} onClick={() =>
          api.downloadDaily(date.format("YYYY-MM-DD")).catch((e) => message.error(e.message))}>
          Export Excel</Button>
        {isAdmin && <Button icon={<ReloadOutlined />} onClick={recompute}>Recompute</Button>}
      </Space>}>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col><Statistic title="Present" value={counts.present || 0} valueStyle={{ color: "#22c55e" }} /></Col>
        <Col><Statistic title="Absent" value={counts.absent || 0} valueStyle={{ color: "#ef4444" }} /></Col>
        <Col><Statistic title="Half day" value={counts.halfday || 0} valueStyle={{ color: "#f59e0b" }} /></Col>
        <Col><Statistic title="Late" value={lateN} valueStyle={{ color: "#ef4444" }} /></Col>
        <Col><Statistic title="Early" value={earlyN} valueStyle={{ color: "#a855f7" }} /></Col>
        <Col><Statistic title="Day off" value={counts.dayoff || 0} /></Col>
      </Row>
      <Space style={{ marginBottom: 12 }} wrap>
        <Segmented options={FILTERS} value={filter} onChange={setFilter} />
        <Input allowClear prefix={<SearchOutlined />} placeholder="Search name or ID"
          value={search} onChange={(e) => setSearch(e.target.value)} style={{ width: 240 }} />
      </Space>
      <DataGrid rowKey="pin" loading={loading} columns={columns} dataSource={shown}
        pagination={{ showTotal: (t) => `${t} of ${rows.length} employees` }} />
    </Card>
  );
}
