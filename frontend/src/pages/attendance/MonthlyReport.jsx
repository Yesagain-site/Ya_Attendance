import React, { useEffect, useState, useCallback } from "react";
import { Card, DatePicker, Button, Space, message } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import DataGrid from "../../components/DataGrid.jsx";
import { api } from "../../api.js";

const hm = (min) => `${Math.floor((min || 0) / 60)}h ${(min || 0) % 60}m`;

export default function MonthlyReport() {
  const [month, setMonth] = useState(dayjs());
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(await api.monthly(month.format("YYYY-MM"))); }
    catch (e) { message.error(e.message); }
    finally { setLoading(false); }
  }, [month]);
  useEffect(() => { load(); }, [load]);

  const columns = [
    { title: "PIN", dataIndex: "emp_code", width: 80 },
    { title: "Name", dataIndex: "name", render: (n) => n || "—" },
    { title: "Department", dataIndex: "department", render: (d) => d || "—" },
    { title: "Present", dataIndex: "present_days" },
    { title: "Absent", dataIndex: "absent_days" },
    { title: "Half-day", dataIndex: "halfday_days" },
    { title: "Late days", dataIndex: "late_days" },
    { title: "Total worked", dataIndex: "worked_min", render: hm },
    { title: "Total OT", dataIndex: "ot_min", render: hm },
  ];

  return (
    <Card title="Monthly report" extra={
      <Space>
        <DatePicker picker="month" value={month} onChange={(m) => m && setMonth(m)} allowClear={false} />
        <Button type="primary" icon={<DownloadOutlined />} onClick={() =>
          api.downloadMonthly(month.format("YYYY-MM")).catch((e) => message.error(e.message))}>
          Export Excel</Button>
      </Space>}>
      <DataGrid rowKey="emp_code" loading={loading} columns={columns} dataSource={rows}
        pagination={{ showTotal: (t) => `${t} employees` }} />
    </Card>
  );
}
