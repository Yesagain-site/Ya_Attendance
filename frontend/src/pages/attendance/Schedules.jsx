import React, { useEffect, useState } from "react";
import {
  Card, Table, Button, Modal, Form, Select, Input, DatePicker, Space, Popconfirm, message, Tag,
} from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import { api } from "../../api.js";
import { useAuth } from "../../auth.jsx";

export default function Schedules() {
  const { isAdmin } = useAuth();
  const [rows, setRows] = useState([]);
  const [shifts, setShifts] = useState([]);
  const [depts, setDepts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState(false);
  const [form] = Form.useForm();

  const load = () => {
    setLoading(true);
    api.schedules().then(setRows).catch((e) => message.error(e.message)).finally(() => setLoading(false));
  };
  useEffect(() => {
    load();
    api.shifts().then(setShifts).catch(() => {});
    api.departments().then(setDepts).catch(() => {});
  }, []);

  const save = async () => {
    const v = await form.validateFields();
    const body = {
      emp_code: v.emp_code || null,
      department_id: v.department_id || null,
      shift_id: v.shift_id,
      start_date: v.range?.[0]?.format("YYYY-MM-DD"),
      end_date: v.range?.[1]?.format("YYYY-MM-DD"),
    };
    try { await api.createSchedule(body); message.success("Assigned"); setModal(false); load(); }
    catch (e) { message.error(e.message); }
  };

  const columns = [
    { title: "Target", render: (_, r) => r.emp_code
      ? <Tag color="blue">Employee {r.emp_code}</Tag>
      : <Tag color="purple">Dept: {r.department || r.department_id}</Tag> },
    { title: "Shift", dataIndex: "shift_name" },
    { title: "From", dataIndex: "start_date", render: (d) => d || "—" },
    { title: "To", dataIndex: "end_date", render: (d) => d || "—" },
    isAdmin && { title: "", width: 60, render: (_, r) => (
      <Popconfirm title="Remove?" onConfirm={async () => { await api.deleteSchedule(r.id); load(); }}>
        <Button size="small" danger icon={<DeleteOutlined />} />
      </Popconfirm>
    ) },
  ].filter(Boolean);

  return (
    <Card title="Schedules" extra={isAdmin &&
      <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setModal(true); }}>
        Assign shift</Button>}>
      <Table rowKey="id" size="middle" loading={loading} columns={columns} dataSource={rows}
        pagination={{ pageSize: 15 }} />
      <Modal title="Assign shift" open={modal} onOk={save} onCancel={() => setModal(false)} destroyOnClose>
        <Form form={form} layout="vertical">
          <p style={{ color: "#999" }}>Assign to an employee (by PIN) OR a whole department.</p>
          <Form.Item name="emp_code" label="Employee PIN"><Input placeholder="e.g. 1003" /></Form.Item>
          <Form.Item name="department_id" label="Department">
            <Select allowClear options={depts.map((d) => ({ value: d.id, label: d.name }))} /></Form.Item>
          <Form.Item name="shift_id" label="Shift" rules={[{ required: true }]}>
            <Select options={shifts.map((s) => ({ value: s.id, label: s.name }))} /></Form.Item>
          <Form.Item name="range" label="Effective range (optional)">
            <DatePicker.RangePicker style={{ width: "100%" }} /></Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
