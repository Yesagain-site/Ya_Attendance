import React from "react";
import { Layout, Menu, Dropdown, Avatar, Tag } from "antd";
import { UserOutlined, LogoutOutlined } from "@ant-design/icons";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import { SECTIONS, sectionForPath } from "../nav.jsx";

const { Header, Sider, Content } = Layout;

export default function AppLayout() {
  const nav = useNavigate();
  const loc = useLocation();
  const { user, logout, isAdmin } = useAuth();

  const sections = SECTIONS.filter((s) => !s.adminOnly || isAdmin);
  const active = sectionForPath(loc.pathname);
  const hasSidebar = active.items.length > 0;

  const topItems = sections.map((s) => ({ key: s.key, icon: s.icon, label: s.label }));
  const sideItems = active.items.map((i) => ({ key: i.path, icon: i.icon, label: i.label }));

  const onTop = (e) => {
    const s = sections.find((x) => x.key === e.key);
    if (s) nav(s.items[0]?.path || s.base);
  };

  return (
    <Layout style={{ height: "100vh", overflow: "hidden" }}>
      <Header style={{ display: "flex", alignItems: "center", padding: "0 20px", gap: 20,
        flex: "0 0 auto", zIndex: 20 }}>
        <div style={{ color: "#fff", fontWeight: 700, fontSize: 18, whiteSpace: "nowrap" }}>
          <span style={{ color: "#22c55e" }}>YA</span>-Attendance
        </div>
        <Menu theme="dark" mode="horizontal" selectedKeys={[active.key]} onClick={onTop}
          items={topItems} style={{ flex: 1, minWidth: 0 }} />
        <Dropdown menu={{ items: [
          { key: "role", disabled: true, label: <Tag color={isAdmin ? "gold" : "blue"}>{user?.role}</Tag> },
          { type: "divider" },
          { key: "logout", icon: <LogoutOutlined />, label: "Log out", onClick: logout },
        ] }}>
          <span style={{ color: "#fff", cursor: "pointer", whiteSpace: "nowrap" }}>
            <Avatar size="small" icon={<UserOutlined />} style={{ marginRight: 8 }} />
            {user?.full_name || user?.username}
          </span>
        </Dropdown>
      </Header>
      <Layout style={{ flex: 1, minHeight: 0 }}>
        {hasSidebar && (
          <Sider theme="light" width={210} breakpoint="lg" collapsedWidth={0}
            style={{ borderRight: "1px solid #f0f0f0", height: "100%", overflow: "auto" }}>
            <Menu mode="inline" selectedKeys={[loc.pathname]} items={sideItems}
              onClick={(e) => nav(e.key)} style={{ height: "100%", borderRight: 0, paddingTop: 8 }} />
          </Sider>
        )}
        <Content style={{ padding: 20, background: "#f0f2f5", height: "100%", overflow: "auto" }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
