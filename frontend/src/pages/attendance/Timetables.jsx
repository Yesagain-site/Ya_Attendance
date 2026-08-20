import React, { useEffect, useState } from "react";
import {
  Card, Table, Button, Modal, Form, Input, InputNumber, TimePicker, Switch,
  Space, Popconfirm, message, Tag,
} from "antd";
import { PlusOutlined, EditOutlined, DeleteOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../../api.js";
import { useAuth } from "../../auth.jsx";

const T = (s) => (s ? dayjs(s, "HH:mm:ss") : null);

export default function Timetables() {
  const { isAdmin } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState(null);
  const [form] = Form.useForm();

  const load = () => {
    setLoading(true);
    api.timetables().then(setRows).catch((e) => message.error(e.message)).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const openAdd = () => {
    form.resetFields();
    form.setFieldsValue({ in_time: T("08:00:00"), out_time: T("17:00:00"),
      grace_late_min: 10, grace_early_min: 10, break_minutes: 60, work_minutes: 480, ot_enabled: false });
    setModal({});
  };
  const openEdit = (r) => {
    form.setFieldsValue({ ...r, in_time: T(r.in_time), out_time: T(r.out_time) });
    setModal(r);
  };
  const save = async () => {
    const v = await form.validateFields();
    const body = { ...v, in_time: v.in_time.format("HH:mm"), out_time: v.out_time.format("HH:mm") };
    try {
      if (modal.id) await api.updateTimetable(modal.id, body);
      else await api.createTimetable(body);
      message.success("Saved"); setModal(null); load();
    } catch (e) { message.error(e.message); }
  };

  const columns = [
    { title: "Name", dataIndex: "name" },
    { title: "In", dataIndex: "in_time", render: (t) => String(t).slice(0, 5) },
    { title: "Out", dataIndex: "out_time", render: (t) => String(t).slice(0, 5) },
    { title: "Grace late", dataIndex: "grace_late_min", render: (m) => `${m}m` },
    { title: "Grace early", dataIndex: "grace_early_min", render: (m) => `${m}m` },
    { title: "Break", dataIndex: "break_minutes", render: (m) => `${m}m` },
    { title: "OT", dataIndex: "ot_enabled", render: (o) => o ? <Tag color="green">on</Tag> : <Tag>off</Tag> },
    isAdmin && { title: "", width: 90, render: (_, r) => (
      <Space>
        <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
        <Popconfirm title="Delete?" onConfirm={async () => { await api.deleteTimetable(r.id); load(); }}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Space>
    ) },
  ].filter(Boolean);

  return (
    <Card title="Timetables" extra={isAdmin &&
      <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>Add timetable</Button>}>
      <Table rowKey="id" size="middle" loading={loading} columns={columns} dataSource={rows}
        pagination={{ pageSize: 15 }} />
      <Modal title={modal?.id ? "Edit timetable" : "Add timetable"} open={!!modal}
        onOk={save} onCancel={() => setModal(null)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item>
          <Space>
            <Form.Item name="in_time" label="In time" rules={[{ required: true }]}>
              <TimePicker format="HH:mm" /></Form.Item>
            <Form.Item name="out_time" label="Out time" rules={[{ required: true }]}>
              <TimePicker format="HH:mm" /></Form.Item>
          </Space>
          <Space>
            <Form.Item name="grace_late_min" label="Grace late (min)"><InputNumber min={0} /></Form.Item>
            <Form.Item name="grace_early_min" label="Grace early (min)"><InputNumber min={0} /></Form.Item>
          </Space>
          <Space>
            <Form.Item name="work_minutes" label="Work minutes"><InputNumber min={0} /></Form.Item>
            <Form.Item name="break_minutes" label="Break minutes"><InputNumber min={0} /></Form.Item>
            <Form.Item name="ot_after_min" label="OT after (min)"><InputNumber min={0} /></Form.Item>
          </Space>
          <Form.Item name="ot_enabled" label="Overtime enabled" valuePropName="checked">
            <Switch /></Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
