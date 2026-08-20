import React, { useEffect, useState } from "react";
import {
  Card, Button, Modal, Form, Input, Select, Space, Popconfirm, message, Tag, Checkbox,
} from "antd";
import { PlusOutlined, EditOutlined, DeleteOutlined } from "@ant-design/icons";
import DataGrid from "../../components/DataGrid.jsx";
import { api } from "../../api.js";
import { useAuth } from "../../auth.jsx";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function Shifts() {
  const { isAdmin } = useAuth();
  const [rows, setRows] = useState([]);
  const [tts, setTts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState(null);
  const [form] = Form.useForm();

  const load = () => {
    setLoading(true);
    api.shifts().then(setRows).catch((e) => message.error(e.message)).finally(() => setLoading(false));
  };
  useEffect(() => { load(); api.timetables().then(setTts).catch(() => {}); }, []);

  const ttName = (id) => tts.find((t) => t.id === id)?.name || "—";
  const shiftTimetable = (r) => (r.details || []).find((d) => !d.is_off && d.timetable_id)?.timetable_id;
  const offDays = (r) => (r.details || []).filter((d) => d.is_off).map((d) => d.day_index);

  const openAdd = () => {
    form.resetFields();
    form.setFieldsValue({ name: "", timetable_id: undefined, off_days: [6] }); // Sun off
    setModal({});
  };
  const openEdit = (r) => {
    form.setFieldsValue({ name: r.name, timetable_id: shiftTimetable(r), off_days: offDays(r) });
    setModal(r);
  };
  const save = async () => {
    const v = await form.validateFields();
    const off = v.off_days || [];
    const details = DAYS.map((_, i) => ({
      day_index: i,
      is_off: off.includes(i),
      timetable_id: off.includes(i) ? null : v.timetable_id,
    }));
    try {
      if (modal.id) await api.updateShift(modal.id, { name: v.name, details });
      else await api.createShift({ name: v.name, details });
      message.success("Saved"); setModal(null); load();
    } catch (e) { message.error(e.message); }
  };

  const columns = [
    { title: "Shift", dataIndex: "name" },
    { title: "Timetable", render: (_, r) => {
      const tid = shiftTimetable(r);
      const t = tts.find((x) => x.id === tid);
      return t ? <Tag color="green">{t.name} ({String(t.in_time).slice(0,5)}–{String(t.out_time).slice(0,5)})</Tag> : "—";
    } },
    { title: "Working days", render: (_, r) => {
      const off = offDays(r);
      return <Space size={4} wrap>{DAYS.map((d, i) =>
        <Tag key={i} color={off.includes(i) ? "default" : "blue"}>{d}{off.includes(i) ? " (off)" : ""}</Tag>)}</Space>;
    } },
    isAdmin && { title: "", width: 90, render: (_, r) => (
      <Space>
        <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
        <Popconfirm title="Delete?" onConfirm={async () => { await api.deleteShift(r.id); load(); }}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Space>
    ) },
  ].filter(Boolean);

  return (
    <Card title="Shifts" extra={isAdmin &&
      <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>Add shift</Button>}>
      <p style={{ color: "#999", marginTop: 0 }}>
        A shift = one timetable applied to the working days. Assign a shift to a department or
        employee in <b>Schedules</b>.
      </p>
      <DataGrid rowKey="id" loading={loading} columns={columns} dataSource={rows} />
      <Modal title={modal?.id ? "Edit shift" : "Add shift"} open={!!modal}
        onOk={save} onCancel={() => setModal(null)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Shift name" rules={[{ required: true }]}>
            <Input placeholder="e.g. Sales team" />
          </Form.Item>
          <Form.Item name="timetable_id" label="Timetable (applied to all working days)"
            rules={[{ required: true, message: "Pick a timetable" }]}>
            <Select placeholder="Select timetable"
              options={tts.map((t) => ({ value: t.id,
                label: `${t.name} (${String(t.in_time).slice(0,5)}–${String(t.out_time).slice(0,5)})` }))} />
          </Form.Item>
          <Form.Item name="off_days" label="Days off">
            <Checkbox.Group options={DAYS.map((d, i) => ({ label: d, value: i }))} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
