import React, { useEffect, useState } from "react";
import { Card, Tag, Button, message } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import DataGrid from "../../components/DataGrid.jsx";
import { api } from "../../api.js";

export default function Audit() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const load = () => {
    setLoading(true);
    api.adminAudit(200).then(setRows).catch((e) => message.error(e.message)).finally(() => setLoading(false));
  };
  useEffect(load, []);

  return (
    <Card title="Audit log" extra={<Button icon={<ReloadOutlined />} onClick={load}>Refresh</Button>}>
      <DataGrid rowKey="id" size="small" loading={loading} dataSource={rows}
        columns={[
          { title: "Time", dataIndex: "ts", render: (t) => String(t).replace("T", " ").slice(0, 19) },
          { title: "User", dataIndex: "username", render: (u) => u || "—" },
          { title: "Action", dataIndex: "action", render: (a) => <Tag>{a}</Tag> },
          { title: "Entity", dataIndex: "entity" },
          { title: "Detail", dataIndex: "detail", ellipsis: true },
        ]}
        pagination={{ showTotal: (t) => `${t} events` }} />
    </Card>
  );
}
