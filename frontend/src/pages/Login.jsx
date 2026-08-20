import React, { useState } from "react";
import { Card, Form, Input, Button, Typography, Alert } from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function Login() {
  const { login, user } = useAuth();
  const nav = useNavigate();
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  if (user) nav("/", { replace: true });

  const onFinish = async (v) => {
    setErr(""); setLoading(true);
    try {
      await login(v.username, v.password);
      nav("/", { replace: true });
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "grid", placeItems: "center", height: "100vh",
      background: "linear-gradient(135deg,#0f172a,#1e293b)" }}>
      <Card style={{ width: 360 }}>
        <Typography.Title level={3} style={{ textAlign: "center", marginTop: 0 }}>
          <span style={{ color: "#22c55e" }}>YA</span>-Attendance
        </Typography.Title>
        {err && <Alert type="error" message={err} style={{ marginBottom: 16 }} showIcon />}
        <Form onFinish={onFinish} initialValues={{ username: "admin" }}>
          <Form.Item name="username" rules={[{ required: true }]}>
            <Input prefix={<UserOutlined />} placeholder="Username" size="large" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="Password" size="large" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block size="large" loading={loading}>
            Sign in
          </Button>
        </Form>
      </Card>
    </div>
  );
}
