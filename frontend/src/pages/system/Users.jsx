import React, { useEffect, useState } from "react";
import {
  Card, Table, Button, Modal, Form, Input, Select, Space, Popconfirm, message, Tag, Switch,
} from "antd";
import { PlusOutlined, EditOutlined, DeleteOutlined } from "@ant-design/icons";
import DataGrid from "../../components/DataGrid.jsx";
import { api } from "../../api.js";

export default function Users() {
  const [rows, setRows] = useState([]);
  const [depts, setDepts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState(null);
  const [form] = Form.useForm();

  const load = () => {
    setLoading(true);
    api.adminUsers().then(setRows).catch((e) => message.error(e.message)).finally(() => setLoading(false));
  };
  useEffect(() => { load(); api.departments().then(setDepts).catch(() => {}); }, []);

  const openAdd = () => { form.resetFields(); form.setFieldsValue({ role: "manager", active: true }); setModal({}); };
  const openEdit = (r) => { form.setFieldsValue({ ...r, password: undefined }); setModal(r); };
  const save = async () => {
    const v = await form.validateFields();
    try {
      if (modal.id) await api.updateUser(modal.id, v);
      else await api.createUser(v);
      message.success("Saved"); setModal(null); load();
    } catch (e) { message.error(e.message); }
  };

  const role = Form.useWatch("role", form);

  const columns = [
    { title: "ID", dataIndex: "id", width: 60 },
    { title: "Username", dataIndex: "username" },
    { title: "Name", dataIndex: "full_name", render: (n) => n || "—" },
    { title: "Role", dataIndex: "role", render: (r) => <Tag color={r === "admin" ? "gold" : "blue"}>{r}</Tag> },
    { title: "Departments", dataIndex: "department_ids",
      render: (ids) => ids?.length ? ids.map((i) => depts.find((d) => d.id === i)?.name || i).join(", ") : (
        <span style={{ color: "#999" }}>all / n/a</span>) },
    { title: "Status", dataIndex: "active", render: (a) => <Tag color={a ? "green" : "red"}>{a ? "Active" : "Inactive"}</Tag> },
    { title: "", width: 90, render: (_, r) => (
      <Space>
        <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
        <Popconfirm title="Delete user?" onConfirm={async () => { try { await api.deleteUser(r.id); load(); } catch (e) { message.error(e.message); } }}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Space>
    ) },
  ];

  return (
    <Card title="Users & Roles" extra={
      <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>Add user</Button>}>
      <DataGrid rowKey="id" loading={loading} columns={columns} dataSource={rows} />
      <Modal title={modal?.id ? "Edit user" : "Add user"} open={!!modal}
        onOk={save} onCancel={() => setModal(null)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="username" label="Username" rules={[{ required: !modal?.id }]}>
            <Input disabled={!!modal?.id} />
          </Form.Item>
          <Form.Item name="password" label={modal?.id ? "New password (optional)" : "Password"}
            rules={[{ required: !modal?.id }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="full_name" label="Full name"><Input /></Form.Item>
          <Form.Item name="role" label="Role">
            <Select options={[{ value: "admin", label: "Admin" }, { value: "manager", label: "Manager" }]} />
          </Form.Item>
          {role === "manager" && (
            <Form.Item name="department_ids" label="Scoped departments">
              <Select mode="multiple" allowClear
                options={depts.map((d) => ({ value: d.id, label: d.name }))} />
            </Form.Item>
          )}
          <Form.Item name="active" label="Active" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
