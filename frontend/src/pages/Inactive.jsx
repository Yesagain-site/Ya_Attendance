import React, { useEffect, useState, useCallback } from "react";
import {
  Card, Space, Select, Tag, Button, Popconfirm, message, Alert, Table,
} from "antd";
import { UserOutlined, DeleteOutlined, ReloadOutlined } from "@ant-design/icons";
import DataGrid from "../components/DataGrid.jsx";
import PhotoAvatar from "../components/PhotoAvatar.jsx";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";

export default function Inactive() {
  const { isAdmin } = useAuth();
  const [months, setMonths] = useState(3);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState([]);

  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(await api.inactiveEmployees(months)); setSelected([]); }
    catch (e) { message.error(e.message); }
    finally { setLoading(false); }
  }, [months]);
  useEffect(() => { load(); }, [load]);

  const purge = async (pin) => {
    try {
      const r = await api.purgeEmployee(pin);
      message.success(`Deleted ${pin} — removal queued on ${r.devices_queued} device(s)`);
      load();
    } catch (e) { message.error(e.message); }
  };

  const purgeSelected = async () => {
    try {
      const r = await api.purgeBulk(selected);
      message.success(`Deleted ${r.deleted} employees — removal queued on ${r.devices_queued} device(s)`);
      load();
    } catch (e) { message.error(e.message); }
  };

  const columns = [
    { title: "", key: "avatar", width: 48, render: (_, r) => (
      <PhotoAvatar pin={r.pin} hasPhoto={r.has_photo} name={r.name} />) },
    { title: "PIN", dataIndex: "pin", width: 90 },
    { title: "Name", dataIndex: "name" },
    { title: "Department", dataIndex: "department", render: (d) => d || "—" },
    { title: "Last attendance", dataIndex: "last_punch",
      render: (t) => t ? <Tag color="orange">{String(t).slice(0, 10)}</Tag>
                       : <Tag color="red">never</Tag> },
    isAdmin && { title: "Action", width: 120, render: (_, r) => (
      <Popconfirm
        title="Delete everywhere?"
        description="Removes from all devices and the app database."
        okText="Delete" okButtonProps={{ danger: true }}
        onConfirm={() => purge(r.pin)}>
        <Button size="small" danger icon={<DeleteOutlined />}>Delete</Button>
      </Popconfirm>
    ) },
  ].filter(Boolean);

  return (
    <Card
      title="Inactive Employees"
      extra={
        <Space>
          {isAdmin && selected.length > 0 && (
            <Popconfirm
              title={`Delete ${selected.length} selected employees everywhere?`}
              description="Removes them from all connected devices and the app database."
              okText="Delete" okButtonProps={{ danger: true }} onConfirm={purgeSelected}>
              <Button danger type="primary" icon={<DeleteOutlined />}>
                Delete selected ({selected.length})</Button>
            </Popconfirm>
          )}
          <span>No attendance in the last</span>
          <Select value={months} onChange={setMonths} style={{ width: 110 }}
            options={[{ value: 2, label: "2 months" }, { value: 3, label: "3 months" },
                      { value: 6, label: "6 months" }]} />
          <Button icon={<ReloadOutlined />} onClick={load}>Refresh</Button>
        </Space>}>
      <Alert style={{ marginBottom: 12 }} type="warning" showIcon
        message="Deleting an employee removes them from all connected devices and the app database (synchronized)." />
      <DataGrid rowKey="pin" loading={loading} columns={columns} dataSource={rows}
        rowSelection={isAdmin ? {
          selectedRowKeys: selected, onChange: setSelected,
          selections: [Table.SELECTION_ALL, Table.SELECTION_INVERT, Table.SELECTION_NONE],
        } : undefined}
        pagination={{ showTotal: (t) => `${t} inactive employees` }} />
    </Card>
  );
}
