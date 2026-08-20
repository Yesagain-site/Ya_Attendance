import React, { useEffect, useState } from "react";
import {
  Card, Table, Button, Modal, Form, Input, InputNumber, Select, Space, Popconfirm, message, Tag,
} from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import { api } from "../../api.js";
import { useAuth } from "../../auth.jsx";

export default function Breaks() {
  const { isAdmin } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState(false);
  const [form] = Form.useForm();

  const load = () => {
    setLoading(true);
    api.breaks().then(setRows).catch((e) => message.error(e.message)).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const save = async () => {
    const v = await form.validateFields();
    try { await api.createBreak(v); message.success("Saved"); setModal(false); load(); }
    catch (e) { message.error(e.message); }
  };

  const columns = [
    { title: "Name", dataIndex: "name" },
    { title: "Minutes", dataIndex: "minutes" },
    { title: "Mode", dataIndex: "mode", render: (m) => <Tag>{m}</Tag> },
    isAdmin && { title: "", width: 60, render: (_, r) => (
      <Popconfirm title="Delete?" onConfirm={async () => { await api.deleteBreak(r.id); load(); }}>
        <Button size="small" danger icon={<DeleteOutlined />} />
      </Popconfirm>
    ) },
  ].filter(Boolean);

  return (
    <Card title="Break times" extra={isAdmin &&
      <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); form.setFieldsValue({ mode: "auto", minutes: 60 }); setModal(true); }}>
        Add break</Button>}>
      <Table rowKey="id" size="middle" loading={loading} columns={columns} dataSource={rows}
        pagination={{ pageSize: 15 }} />
      <Modal title="Add break" open={modal} onOk={save} onCancel={() => setModal(false)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="minutes" label="Minutes" rules={[{ required: true }]}><InputNumber min={0} /></Form.Item>
          <Form.Item name="mode" label="Mode">
            <Select options={[{ value: "auto", label: "Auto-deduct" }, { value: "punch", label: "Punched" }]} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
