import React, { useEffect, useState, useCallback } from "react";
import { Card, DatePicker, Button, Space, Segmented, message } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import DataGrid from "../../components/DataGrid.jsx";
import { api } from "../../api.js";

const hm = (min) => `${Math.floor((min || 0) / 60)}h ${(min || 0) % 60}m`;

export default function MonthlyReport() {
  const [mode, setMode] = useState("Month");
  const [month, setMonth] = useState(dayjs());
  const [range, setRange] = useState([dayjs().startOf("month"), dayjs()]);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);

  // Params + a filename label for the export.
  const params = () => mode === "Month"
    ? { month: month.format("YYYY-MM") }
    : { from: range[0].format("YYYY-MM-DD"), to: range[1].format("YYYY-MM-DD") };
  const label = () => mode === "Month"
    ? month.format("YYYY-MM")
    : `${range[0].format("YYYY-MM-DD")}_to_${range[1].format("YYYY-MM-DD")}`;

  const load = useCallback(async () => {
    if (mode === "Range" && (!range[0] || !range[1])) return;
    setLoading(true);
    try { setRows(await api.monthly(params())); }
    catch (e) { message.error(e.message); }
    finally { setLoading(false); }
  }, [mode, month, range]);
  useEffect(() => { load(); }, [load]);

  const columns = [
    { title: "PIN", dataIndex: "emp_code", width: 80 },
    { title: "Name", dataIndex: "name", render: (n) => n || "—" },
    { title: "Department", dataIndex: "department", render: (d) => d || "—" },
    { title: "Present", dataIndex: "present_days" },
    { title: "Absent", dataIndex: "absent_days" },
    { title: "Half-day", dataIndex: "halfday_days" },
    { title: "Late days", dataIndex: "late_days" },
    { title: "Early days", dataIndex: "early_days" },
    { title: "Total worked", dataIndex: "worked_min", render: hm },
    { title: "Total OT", dataIndex: "ot_min", render: hm },
  ];

  return (
    <Card title="Monthly report" extra={
      <Space wrap>
        <Segmented options={["Month", "Range"]} value={mode} onChange={setMode} />
        {mode === "Month"
          ? <DatePicker picker="month" value={month} onChange={(m) => m && setMonth(m)} allowClear={false} />
          : <DatePicker.RangePicker value={range} onChange={(r) => r && setRange(r)} allowClear={false} />}
        <Button type="primary" icon={<DownloadOutlined />} onClick={() =>
          api.downloadMonthly(params(), `report_${label()}.xlsx`).catch((e) => message.error(e.message))}>
          Export Excel</Button>
      </Space>}>
      <p style={{ color: "#999", marginTop: 0 }}>
        Only employees with attendance in the selected period are shown (long-absent staff are excluded).
      </p>
      <DataGrid rowKey="emp_code" loading={loading} columns={columns} dataSource={rows}
        pagination={{ showTotal: (t) => `${t} employees` }} />
    </Card>
  );
}
