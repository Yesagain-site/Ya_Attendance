import React, { useEffect, useState, useCallback } from "react";
import {
  Card, DatePicker, Button, Space, Segmented, Input, Collapse, Table, Tag, Empty, message,
} from "antd";
import { DownloadOutlined, SearchOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../../api.js";

const hm = (m) => `${Math.floor((m || 0) / 60)}h ${(m || 0) % 60}m`;
const t = (v) => (v ? String(v).slice(11, 19) : "—");
const STATUS = { present: "green", absent: "red", halfday: "orange",
  incomplete: "gold", dayoff: "default", holiday: "blue" };

const dayColumns = [
  { title: "Date", dataIndex: "date", width: 110 },
  { title: "Day", dataIndex: "weekday", width: 55 },
  { title: "Check-in", dataIndex: "first_in", render: t, width: 90 },
  { title: "Check-out", dataIndex: "last_out", render: t, width: 90 },
  { title: "Worked", dataIndex: "worked_min", render: hm, width: 90 },
  { title: "Late", dataIndex: "late_min", render: (m) => (m ? <span style={{ color: "#ef4444" }}>{m}m</span> : "—"), width: 70 },
  { title: "OT-in", dataIndex: "ot_in", render: t, width: 90 },
  { title: "OT-out", dataIndex: "ot_out", render: t, width: 90 },
  { title: "OT", dataIndex: "ot_min", render: (m) => (m ? hm(m) : "—"), width: 80 },
  { title: "Status", dataIndex: "status", width: 100,
    render: (s) => <Tag color={STATUS[s] || "default"}>{s}</Tag> },
];

export default function MonthlyReport() {
  const [mode, setMode] = useState("Month");
  const [month, setMonth] = useState(dayjs());
  const [range, setRange] = useState([dayjs().startOf("month"), dayjs()]);
  const [search, setSearch] = useState("");
  const [emps, setEmps] = useState([]);
  const [period, setPeriod] = useState({});
  const [loading, setLoading] = useState(false);

  const params = () => ({
    ...(mode === "Month"
      ? { month: month.format("YYYY-MM") }
      : { from: range[0].format("YYYY-MM-DD"), to: range[1].format("YYYY-MM-DD") }),
    ...(search ? { search } : {}),
  });
  const label = () => (mode === "Month"
    ? month.format("YYYY-MM")
    : `${range[0].format("YYYY-MM-DD")}_${range[1].format("YYYY-MM-DD")}`);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.reportDetail(params());
      setEmps(r.employees); setPeriod({ from: r.from, to: r.to });
    } catch (e) { message.error(e.message); }
    finally { setLoading(false); }
  }, [mode, month, range, search]);
  useEffect(() => { load(); }, [load]);

  const items = emps.map((e) => {
    const s = e.summary;
    return {
      key: e.pin,
      label: (
        <Space wrap>
          <b>{e.name || e.pin}</b> <span style={{ color: "#999" }}>({e.pin}) · {e.department || "—"}</span>
          <Tag color="green">Present {s.present}</Tag>
          <Tag color="red">Absent {s.absent}</Tag>
          <Tag color="orange">Late {s.late}</Tag>
          <Tag>Worked {hm(s.worked_min)}</Tag>
          <Tag color="blue">OT {hm(s.ot_min)}</Tag>
        </Space>
      ),
      children: (
        <Table rowKey="date" size="small" columns={dayColumns} dataSource={e.days}
          pagination={false} scroll={{ x: 850 }} />
      ),
    };
  });

  return (
    <Card title="Monthly report — daily check-in/out per employee" extra={
      <Space wrap>
        <Input.Search allowClear placeholder="Search name or ID" prefix={<SearchOutlined />}
          onSearch={setSearch} style={{ width: 220 }} />
        <Segmented options={["Month", "Range"]} value={mode} onChange={setMode} />
        {mode === "Month"
          ? <DatePicker picker="month" value={month} onChange={(m) => m && setMonth(m)} allowClear={false} />
          : <DatePicker.RangePicker value={range} onChange={(r) => r && setRange(r)} allowClear={false} />}
        <Button type="primary" icon={<DownloadOutlined />} onClick={() =>
          api.downloadDetail(params(), `attendance_${label()}.xlsx`).catch((e) => message.error(e.message))}>
          Export Excel</Button>
      </Space>}>
      <p style={{ color: "#999", marginTop: 0 }}>
        {period.from} → {period.to} · {emps.length} employees · long-absent staff excluded ·
        the export matches exactly what you see here (period + search).
      </p>
      {emps.length === 0 && !loading
        ? <Empty description="No matching employees with attendance in this period" />
        : <Collapse items={items} accordion />}
    </Card>
  );
}
