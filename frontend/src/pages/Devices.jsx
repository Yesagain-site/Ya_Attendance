import React, { useEffect, useState } from "react";
import {
  Card, Tag, Badge, Button, Modal, Form, Input, Select, Space, message,
} from "antd";
import {
  ArrowUpOutlined, ArrowDownOutlined, EditOutlined,
} from "@ant-design/icons";
import DataGrid from "../components/DataGrid.jsx";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";

function ActivityCell({ r }) {
  if (r.activity === "upload")
    return <span style={{ color: "#22c55e" }}>
      <ArrowUpOutlined className="zkt-arrow-up" /> Uploading</span>;
  if (r.activity === "download")
    return <span style={{ color: "#3b82f6" }}>
      <ArrowDownOutlined className="zkt-arrow-down" /> Sending</span>;
  return <Badge status={r.online ? "success" : "error"} text={r.online ? "Online" : "Offline"} />;
}

export default function Devices() {
  const { isAdmin } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState(null);
  const [form] = Form.useForm();

  const load = () => {
    setLoading(true);
    api.devices().then(setRows).catch((e) => message.error(e.message)).finally(() => setLoading(false));
  };
  useEffect(() => {
    load();
    const t = setInterval(load, 5000); // catch live upload/download activity
    return () => clearInterval(t);
  }, []);

  const openEdit = (r) => { form.setFieldsValue(r); setModal(r); };
  const save = async () => {
    const v = await form.validateFields();
    try {
      await api.updateDevice(modal.sn, {
        name: v.name, ip: v.ip, direction: v.direction,
        area_id: v.area_id ? Number(v.area_id) : null,
      });
      message.success("Saved"); setModal(null); load();
    } catch (e) { message.error(e.message); }
  };

  const columns = [
    { title: "Serial", dataIndex: "sn" },
    { title: "Name", dataIndex: "name", render: (n) => n || "—" },
    { title: "IP", dataIndex: "ip", render: (i) => i || "—" },
    { title: "Status", width: 150, render: (_, r) => <ActivityCell r={r} /> },
    { title: "Direction", dataIndex: "direction", render: (d) => <Tag>{d || "both"}</Tag> },
    { title: "Users", dataIndex: "user_count" },
    { title: "Faces", dataIndex: "face_count" },
    { title: "Punches", dataIndex: "transaction_count" },
    { title: "Firmware", dataIndex: "firmware", render: (f) => f || "—" },
    { title: "Last activity", dataIndex: "last_seen",
      render: (t) => (t ? String(t).replace("T", " ").slice(0, 19) : "—") },
    isAdmin && { title: "", width: 60, render: (_, r) => (
      <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />) },
  ].filter(Boolean);

  return (
    <Card title="Devices" extra={<span style={{ color: "#999" }}>live · refresh 5s</span>}>
      <DataGrid rowKey="sn" loading={loading} columns={columns} dataSource={rows} pagination={false} />
      <Modal title={`Edit device ${modal?.sn || ""}`} open={!!modal}
        onOk={save} onCancel={() => setModal(null)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Name"><Input placeholder="e.g. Check-in / Reception" /></Form.Item>
          <Form.Item name="ip" label="IP address"><Input placeholder="128.0.128.173" /></Form.Item>
          <Form.Item name="direction" label="Punch direction">
            <Select allowClear options={[
              { value: "in", label: "Check-in only" },
              { value: "out", label: "Check-out only" },
              { value: "both", label: "Both" }]} />
          </Form.Item>
          <Form.Item name="area_id" label="Area ID"><Input /></Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
