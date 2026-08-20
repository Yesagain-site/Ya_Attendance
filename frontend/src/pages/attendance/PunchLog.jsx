import React, { useEffect, useState, useCallback } from "react";
import { Card, Input, Space, Tag, Switch, message } from "antd";
import DataGrid from "../../components/DataGrid.jsx";
import { api } from "../../api.js";

// Collapse repeated captures of the same person within N minutes into one row.
function collapse(rows, minutes = 5) {
  const byPin = {};
  const asc = [...rows].sort((a, b) => new Date(a.punch_time) - new Date(b.punch_time));
  const keep = [];
  for (const r of asc) {
    const last = byPin[r.pin];
    if (!last || (new Date(r.punch_time) - new Date(last)) >= minutes * 60000) {
      keep.push(r);
      byPin[r.pin] = r.punch_time;
    }
  }
  return keep.sort((a, b) => new Date(b.punch_time) - new Date(a.punch_time));
}

export default function PunchLog() {
  const [rows, setRows] = useState([]);
  const [pin, setPin] = useState("");
  const [loading, setLoading] = useState(false);
  const [collapsed, setCollapsed] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(await api.attendance({ pin, limit: 2000 })); }
    catch (e) { message.error(e.message); }
    finally { setLoading(false); }
  }, [pin]);
  useEffect(() => { load(); }, [load]);

  const shown = collapsed ? collapse(rows) : rows;

  return (
    <Card title="Punch log">
      <Space style={{ marginBottom: 12 }}>
        <Input.Search placeholder="Filter by PIN" allowClear onSearch={setPin}
          style={{ width: 220 }} enterButton />
        <span>Collapse duplicate captures <Switch size="small" checked={collapsed}
          onChange={setCollapsed} /></span>
        <span style={{ color: "#999" }}>{shown.length} of {rows.length}</span>
      </Space>
      <DataGrid rowKey="id" loading={loading} dataSource={shown}
        columns={[
          { title: "PIN", dataIndex: "pin", width: 90 },
          { title: "Name", dataIndex: "name", render: (n) => n || "—" },
          { title: "Time", dataIndex: "punch_time", render: (t) => String(t).replace("T", " ").slice(0, 19) },
          { title: "Punch", dataIndex: "punch_name",
            render: (p) => <Tag color={p === "Check-Out" ? "orange" : "green"}>{p}</Tag> },
          { title: "Verify", dataIndex: "verify_name" },
          { title: "Device", dataIndex: "device_sn" },
        ]}
        pagination={{ showTotal: (t) => `${t} punches` }} />
    </Card>
  );
}
