import React, { useEffect, useState } from "react";
import { Card, message } from "antd";
import DataGrid from "../components/DataGrid.jsx";
import { api } from "../api.js";

function OrgTable({ title, fetcher }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    setLoading(true);
    fetcher().then(setRows).catch((e) => message.error(e.message)).finally(() => setLoading(false));
  }, [fetcher]);
  return (
    <Card title={title}>
      <DataGrid rowKey="id" loading={loading} dataSource={rows}
        columns={[
          { title: "ID", dataIndex: "id", width: 90 },
          { title: "Code", dataIndex: "code", render: (c) => c || "—" },
          { title: "Name", dataIndex: "name" },
        ]}
        pagination={{ showTotal: (t) => `${t} items` }} />
    </Card>
  );
}

export const Departments = () => <OrgTable title="Departments" fetcher={api.departments} />;
export const Positions = () => <OrgTable title="Positions" fetcher={api.positions} />;
export const Areas = () => <OrgTable title="Areas" fetcher={api.areas} />;
