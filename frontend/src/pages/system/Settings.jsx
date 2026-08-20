import React from "react";
import { Card, Form, Input, Button, message, Descriptions, Tag } from "antd";
import { api } from "../../api.js";
import { useAuth } from "../../auth.jsx";

export default function Settings() {
  const { user } = useAuth();
  const [form] = Form.useForm();

  const changePw = async () => {
    const v = await form.validateFields();
    try {
      await api.changePassword(v.current_password, v.new_password);
      message.success("Password changed");
      form.resetFields();
    } catch (e) { message.error(e.message); }
  };

  return (
    <div style={{ maxWidth: 560 }}>
      <Card title="Account" style={{ marginBottom: 16 }}>
        <Descriptions column={1} size="small">
          <Descriptions.Item label="Username">{user?.username}</Descriptions.Item>
          <Descriptions.Item label="Name">{user?.full_name || "—"}</Descriptions.Item>
          <Descriptions.Item label="Role">
            <Tag color={user?.role === "admin" ? "gold" : "blue"}>{user?.role}</Tag>
          </Descriptions.Item>
        </Descriptions>
      </Card>
      <Card title="Change password">
        <Form form={form} layout="vertical">
          <Form.Item name="current_password" label="Current password" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="new_password" label="New password" rules={[{ required: true, min: 6 }]}>
            <Input.Password />
          </Form.Item>
          <Button type="primary" onClick={changePw}>Update password</Button>
        </Form>
      </Card>
    </div>
  );
}
