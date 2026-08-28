import React, { useEffect, useState, useCallback } from "react";
import {
  Table, Input, Button, Space, Modal, Form, Select, message, Popconfirm, Tag, Card, Dropdown, Upload, Avatar,
} from "antd";
import {
  PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined, CloudUploadOutlined,
  DownloadOutlined, UploadOutlined, UserOutlined,
} from "@ant-design/icons";
import DataGrid from "../components/DataGrid.jsx";
import PhotoAvatar from "../components/PhotoAvatar.jsx";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";

export default function Employees() {
  const { isAdmin } = useAuth();
  const [data, setData] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(100);
  const [depts, setDepts] = useState([]);
  const [devices, setDevices] = useState([]);
  const [selected, setSelected] = useState([]);
  const [modal, setModal] = useState(null); // null | {} | employee
  const [form] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.employees({ search, page, page_size: pageSize });
      setData(r.data); setTotal(r.total);
    } catch (e) { message.error(e.message); }
    finally { setLoading(false); }
  }, [search, page, pageSize]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api.departments().then(setDepts).catch(() => {});
    api.employees && api.devices().then(setDevices).catch(() => {});
  }, []);

  const enrollTo = async (sn, withFace) => {
    try {
      const r = await api.enrollToDevice(sn, selected, withFace);
      message.success(`Queued ${r.users_queued} users, ${r.faces_queued} faces to ${sn}`);
      setSelected([]);
    } catch (e) { message.error(e.message); }
  };

  const openAdd = async () => {
    form.resetFields();
    setModal({});
    try {
      const r = await api.nextPin();       // auto-suggest next free ID (gap-fill)
      if (r.capacity_full)
        message.warning(`Device capacity reached — all IDs up to ${r.pin_max} are in use`);
      else form.setFieldsValue({ pin: r.next_pin });
    } catch { /* leave blank; admin can type */ }
  };
  const openEdit = (rec) => { form.setFieldsValue(rec); setModal(rec); };
  const save = async () => {
    const v = await form.validateFields();
    try {
      if (modal.pin) {
        const r = await api.updateEmployee(modal.pin, v);
        message.success(r.devices_queued ? `Saved — synced to ${r.devices_queued} device(s)` : "Saved");
      } else {
        await api.createEmployee(v);
        message.success("Employee added");
      }
      setModal(null); load();
    } catch (e) { message.error(e.message); }
  };
  const del = async (pin) => {
    try {
      const r = await api.purgeEmployee(pin);   // remove from app DB + all devices
      message.success(`Deleted ${pin} — removal queued on ${r.devices_queued} device(s)`);
      load();
    } catch (e) { message.error(e.message); }
  };

  const columns = [
    { title: "", key: "avatar", width: 48, render: (_, r) => (
      <PhotoAvatar pin={r.pin} hasPhoto={r.has_photo} name={r.name} />) },
    { title: "PIN", dataIndex: "pin", width: 90 },
    { title: "Name", dataIndex: "name" },
    { title: "Department", dataIndex: "department", render: (d) => d || "—" },
    { title: "Position", dataIndex: "position", render: (p) => p || "—" },
    { title: "Card", dataIndex: "card", render: (c) => c || "—" },
    { title: "Status", dataIndex: "active", width: 90,
      render: (a) => <Tag color={a ? "green" : "red"}>{a ? "Active" : "Inactive"}</Tag> },
    { title: "", width: 90, render: (_, r) => (
      <Space>
        <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
        {isAdmin && (
          <Popconfirm title="Delete this employee?"
            description="Removes them from the app and all connected devices."
            okText="Delete" okButtonProps={{ danger: true }} onConfirm={() => del(r.pin)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        )}
      </Space>
    ) },
  ];

  return (
    <Card>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          placeholder="Search PIN or name" allowClear enterButton={<SearchOutlined />}
          onSearch={(v) => { setSearch(v); setPage(1); }} style={{ width: 280 }}
        />
        <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>Add employee</Button>
        <Button icon={<DownloadOutlined />} onClick={() =>
          api.exportEmployees().catch((e) => message.error(e.message))}>Export</Button>
        {isAdmin && (
          <Upload accept=".xlsx" showUploadList={false} beforeUpload={(file) => {
            api.importEmployees(file).then((r) => {
              message.success(`Imported: ${r.created} new, ${r.updated} updated`); load();
            }).catch((e) => message.error(e.message));
            return false;
          }}>
            <Button icon={<UploadOutlined />}>Import</Button>
          </Upload>
        )}
        {isAdmin && (
          <Dropdown disabled={!selected.length} menu={{ items: devices.flatMap((d) => [
            { key: d.sn + "|face", label: `${d.sn} — with face`, onClick: () => enrollTo(d.sn, true) },
            { key: d.sn + "|noface", label: `${d.sn} — user only`, onClick: () => enrollTo(d.sn, false) },
          ]) }}>
            <Button icon={<CloudUploadOutlined />}>Enroll to device ({selected.length})</Button>
          </Dropdown>
        )}
      </Space>
      <DataGrid
        rowKey="pin" loading={loading} columns={columns} dataSource={data}
        rowSelection={isAdmin ? { selectedRowKeys: selected, onChange: setSelected } : undefined}
        pagination={{
          current: page, pageSize, total,
          showTotal: (t) => `${t} employees`,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
        }}
      />
      <Modal
        title={modal?.pin ? `Edit ${modal.pin}` : "Add employee"}
        open={!!modal} onOk={save} onCancel={() => setModal(null)} destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="pin" label="PIN / ID" rules={[{ required: true }]}
            tooltip="Auto-suggested (next free number, fills deleted gaps). You can change it.">
            <Input disabled={!!modal?.pin} />
          </Form.Item>
          <Form.Item name="name" label="Name"><Input /></Form.Item>
          <Form.Item name="department_id" label="Department">
            <Select allowClear options={depts.map((d) => ({ value: d.id, label: d.name }))} />
          </Form.Item>
          <Form.Item name="card" label="Card"><Input /></Form.Item>
          <Form.Item name="mobile" label="Mobile"><Input /></Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
