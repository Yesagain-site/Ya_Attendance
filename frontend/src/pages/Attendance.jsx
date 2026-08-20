import React, { useEffect, useState, useCallback } from "react";
import { Card, Tabs, Table, DatePicker, Input, Space, Tag, message } from "antd";
import dayjs from "dayjs";
import { api } from "../api.js";

function PunchLog() {
  const [rows, setRows] = useState([]);
  const [pin, setPin] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(await api.attendance({ pin, limit: 500 })); }
    catch (e) { message.error(e.message); }
    finally { setLoading(false); }
  }, [pin]);
  useEffect(() => { load(); }, []); // initial

  return (
    <>
      <Space style={{ marginBottom: 12 }}>
        <Input.Search placeholder="PIN" allowClear onSearch={(v) => setPin(v)}
          style={{ width: 200 }} enterButton />
      </Space>
      <Table rowKey="id" size="middle" loading={loading} dataSource={rows}
        columns={[
          { title: "PIN", dataIndex: "pin", width: 90 },
          { title: "Name", dataIndex: "name", render: (n) => n || "—" },
          { title: "Time", dataIndex: "punch_time",
            render: (t) => String(t).replace("T", " ").slice(0, 19) },
          { title: "Punch", dataIndex: "punch_name",
            render: (p) => <Tag color={p === "Check-Out" ? "orange" : "green"}>{p}</Tag> },
          { title: "Verify", dataIndex: "verify_name" },
        ]}
        pagination={{ pageSize: 20, showTotal: (t) => `${t} punches` }} />
    </>
  );
}

function DailyReport() {
  const [date, setDate] = useState(dayjs());
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(await api.dailyReport(date.format("YYYY-MM-DD"))); }
    catch (e) { message.error(e.message); }
    finally { setLoading(false); }
  }, [date]);
  useEffect(() => { load(); }, [load]);

  return (
    <>
      <Space style={{ marginBottom: 12 }}>
        <DatePicker value={date} onChange={(d) => d && setDate(d)} allowClear={false} />
      </Space>
      <Table rowKey="pin" size="middle" loading={loading} dataSource={rows}
        columns={[
          { title: "PIN", dataIndex: "pin", width: 90 },
          { title: "Name", dataIndex: "name", render: (n) => n || "—" },
          { title: "First in", dataIndex: "first_in",
            render: (t) => (t ? String(t).replace("T", " ").slice(11, 19) : "—") },
          { title: "Last out", dataIndex: "last_out",
            render: (t) => (t ? String(t).replace("T", " ").slice(11, 19) : "—") },
          { title: "Punches", dataIndex: "punches", width: 90 },
          { title: "Hours", dataIndex: "hours", width: 90 },
        ]}
        pagination={{ pageSize: 20, showTotal: (t) => `${t} employees` }} />
    </>
  );
}

export default function Attendance() {
  return (
    <Card>
      <Tabs items={[
        { key: "log", label: "Punch log", children: <PunchLog /> },
        { key: "daily", label: "Daily report", children: <DailyReport /> },
      ]} />
    </Card>
  );
}
