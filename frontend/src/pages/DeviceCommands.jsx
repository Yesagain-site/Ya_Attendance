import React, { useEffect, useState, useCallback } from "react";
import {
  Card, Select, Space, Button, Tag, Switch, Dropdown, Popconfirm, message,
} from "antd";
import DataGrid from "../components/DataGrid.jsx";
import {
  ReloadOutlined, CloudUploadOutlined, DeleteOutlined, ControlOutlined,
} from "@ant-design/icons";
import { api } from "../api.js";

const STATUS = { pending: "gold", sent: "blue", done: "green", error: "red" };
const MENU = [
  { key: "INFO", label: "Request device info" },
  { key: "CHECK", label: "Re-sync data (CHECK)" },
  { key: "CLEAR_LOG", label: "Clear device log" },
  { key: "REBOOT", label: "Reboot device" },
];

export default function DeviceCommands() {
  const [devices, setDevices] = useState([]);
  const [sn, setSn] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [withFace, setWithFace] = useState(true);

  useEffect(() => {
    api.devices().then((d) => { setDevices(d); if (d[0]) setSn(d[0].sn); }).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    if (!sn) return;
    setLoading(true);
    try { setRows(await api.deviceCommands(sn, 100)); }
    catch (e) { message.error(e.message); }
    finally { setLoading(false); }
  }, [sn]);
  useEffect(() => { load(); }, [load]);

  const syncAll = async () => {
    try {
      const r = await api.syncAllToDevice(sn, withFace);
      message.success(`Queued ${r.users_queued} users, ${r.faces_queued} faces`);
      load();
    } catch (e) { message.error(e.message); }
  };
  const clearPending = async () => {
    try { const r = await api.clearPending(sn); message.success(`Cleared ${r.cleared}`); load(); }
    catch (e) { message.error(e.message); }
  };
  const runMenu = async (key) => {
    try { await api.deviceMenu(sn, key); message.success("Queued: " + key); load(); }
    catch (e) { message.error(e.message); }
  };

  const columns = [
    { title: "ID", dataIndex: "id", width: 70 },
    { title: "Kind", dataIndex: "kind", render: (k) => <Tag>{k}</Tag> },
    { title: "Status", dataIndex: "status", render: (s) => <Tag color={STATUS[s]}>{s}</Tag> },
    { title: "Return", dataIndex: "return_code", render: (r) => r == null ? "—" : <Tag color={r === "0" ? "green" : "red"}>{r}</Tag> },
    { title: "Command", dataIndex: "preview", ellipsis: true },
    { title: "Queued", dataIndex: "queued_at", render: (t) => String(t).replace("T", " ").slice(0, 19) },
  ];

  return (
    <Card
      title={<Space>Device Commands
        <Select value={sn} onChange={setSn} style={{ width: 220 }}
          options={devices.map((d) => ({ value: d.sn, label: `${d.sn} (${d.name || "device"})` }))} />
      </Space>}
      extra={
        <Space>
          <span>with face <Switch size="small" checked={withFace} onChange={setWithFace} /></span>
          <Popconfirm title="Queue ALL employees (+faces) to this device?" onConfirm={syncAll}>
            <Button type="primary" icon={<CloudUploadOutlined />} disabled={!sn}>Sync all</Button>
          </Popconfirm>
          <Dropdown menu={{ items: MENU.map((m) => ({ ...m, onClick: () => runMenu(m.key) })) }}>
            <Button icon={<ControlOutlined />} disabled={!sn}>Device menu</Button>
          </Dropdown>
          <Popconfirm title="Clear all pending commands?" onConfirm={clearPending}>
            <Button danger icon={<DeleteOutlined />} disabled={!sn}>Clear pending</Button>
          </Popconfirm>
          <Button icon={<ReloadOutlined />} onClick={load}>Refresh</Button>
        </Space>}
    >
      <DataGrid rowKey="id" size="small" loading={loading} columns={columns} dataSource={rows}
        pagination={{ showTotal: (t) => `${t} commands` }} />
    </Card>
  );
}
